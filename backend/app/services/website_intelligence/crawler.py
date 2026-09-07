from __future__ import annotations

import logging
from dataclasses import dataclass, field
from urllib.parse import urljoin, urlparse

import lxml.html
import trafilatura
from trafilatura.metadata import extract_metadata

from app.security.execution_scope import DEFAULT_SCOPE, ExecutionScope
from app.security.target_validator import validate_url
from app.sources.http_client import get_safe_client

logger = logging.getLogger(__name__)

HIGH_VALUE_KEYWORDS: tuple[str, ...] = (
    "about",
    "company",
    "product",
    "service",
    "solution",
    "project",
    "research",
    "team",
    "leadership",
    "technology",
    "blog",
    "docs",
)


MAX_RESPONSE_BYTES: int = 5 * 1024 * 1024  # 5 MB maximum response body size
MAX_CRAWL_PAGES: int = 10


@dataclass
class CrawledPage:
    """Representation of an ingested and processed webpage."""

    url: str
    status_code: int
    title: str | None = None
    description: str | None = None
    meta_generator: str | None = None
    extracted_text: str = ""
    raw_html: str = ""
    headers: dict[str, str] = field(default_factory=dict)
    script_srcs: list[str] = field(default_factory=list)
    internal_links: list[str] = field(default_factory=list)
    external_links: list[str] = field(default_factory=list)


class WebsiteCrawler:
    """
    Bounded, SSRF-safe website crawler adhering strictly to PASSIVE_PUBLIC bounds.
    Fetches the homepage and selectively follows prioritized high-value internal links.
    """

    def __init__(self, timeout_seconds: int = 15) -> None:
        self.timeout_seconds = timeout_seconds

    @staticmethod
    def normalize_url(target: str) -> str:
        """Ensure target has an http/https scheme and stripped whitespace."""
        target = target.strip()
        if not target.startswith(("http://", "https://")):
            return f"https://{target}"
        return target

    async def crawl(
        self,
        target_url: str,
        max_pages: int = 3,
        scope: ExecutionScope = DEFAULT_SCOPE,
    ) -> list[CrawledPage]:
        """
        Execute bounded crawl starting from target_url.
        """
        # Enforce bounded page count limit
        effective_max_pages = min(max(1, max_pages), MAX_CRAWL_PAGES)

        start_url = self.normalize_url(target_url)
        if not validate_url(start_url, allow_private=scope.allows_private_ip()):
            raise ValueError(f"Target URL '{start_url}' failed security or SSRF validation.")

        base_parsed = urlparse(start_url)
        base_domain = base_parsed.netloc.lower()

        visited_urls: set[str] = set()
        crawled_pages: list[CrawledPage] = []

        # 1. Fetch Homepage
        homepage = await self._fetch_page(start_url)
        if not homepage:
            return []

        crawled_pages.append(homepage)
        visited_urls.add(self._canonicalize_url(start_url))

        if effective_max_pages <= 1 or not homepage.internal_links:
            return crawled_pages

        # 2. Prioritize High-Value Internal Links
        candidate_links = self._prioritize_links(homepage.internal_links, base_domain)

        for link in candidate_links:
            if len(crawled_pages) >= effective_max_pages:
                break
            canonical = self._canonicalize_url(link)
            if canonical in visited_urls:
                continue

            visited_urls.add(canonical)
            subpage = await self._fetch_page(link)
            if subpage and subpage.extracted_text:
                crawled_pages.append(subpage)

        return crawled_pages

    async def _fetch_page(self, url: str) -> CrawledPage | None:
        """Safely fetch a single URL using NEXUS safe HTTP client with size limits."""
        try:
            async with get_safe_client(timeout_seconds=self.timeout_seconds) as client:
                response = await client.get(url)
                response.raise_for_status()

                # Enforce response body size limit
                content_length = response.headers.get("content-length")
                if content_length and int(content_length) > MAX_RESPONSE_BYTES:
                    logger.warning(
                        "Skipping '%s': Content-Length %s exceeds limit %d bytes",
                        url,
                        content_length,
                        MAX_RESPONSE_BYTES,
                    )
                    return None

                html = response.text[:MAX_RESPONSE_BYTES]
                status_code = response.status_code
                headers = dict(response.headers)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed fetching '%s': %s", url, exc)
            return None

        # Extract text via Trafilatura
        extracted_text = trafilatura.extract(
            html,
            include_links=True,
            include_comments=False,
            output_format="txt",
        ) or ""

        # Extract Metadata via Trafilatura
        meta = extract_metadata(html)
        title = meta.title if meta and meta.title else None
        description = meta.description if meta and meta.description else None

        # Parse HTML DOM with lxml for scripts, generators, and links
        meta_generator = None
        script_srcs: list[str] = []
        internal_links: list[str] = []
        external_links: list[str] = []

        try:
            tree = lxml.html.fromstring(html)

            # Fallback title if trafilatura missed it
            if not title:
                title_elements = tree.xpath("//title/text()")
                if title_elements:
                    title = str(title_elements[0]).strip()

            # Generator tag
            gen_elements = tree.xpath("//meta[@name='generator']/@content")
            if gen_elements:
                meta_generator = str(gen_elements[0]).strip()

            # Description fallback
            if not description:
                desc_elements = tree.xpath("//meta[@name='description']/@content")
                if desc_elements:
                    description = str(desc_elements[0]).strip()

            # Scripts
            for src in tree.xpath("//script/@src"):
                if src:
                    script_srcs.append(str(src).strip())

            # Links
            base_parsed = urlparse(url)
            for href in tree.xpath("//a/@href"):
                if not href:
                    continue
                href_str = str(href).strip()
                if href_str.startswith(("#", "mailto:", "tel:", "javascript:")):
                    continue

                full_url = urljoin(url, href_str)
                parsed = urlparse(full_url)
                if parsed.scheme not in ("http", "https"):
                    continue

                if parsed.netloc.lower() == base_parsed.netloc.lower():
                    internal_links.append(full_url)
                else:
                    external_links.append(full_url)

        except Exception as e:  # noqa: BLE001
            logger.debug("HTML parsing exception for '%s': %s", url, e)

        return CrawledPage(
            url=url,
            status_code=status_code,
            title=title,
            description=description,
            meta_generator=meta_generator,
            extracted_text=extracted_text,
            raw_html=html[:5000],  # Bounded sample for inspection
            headers=headers,
            script_srcs=script_srcs,
            internal_links=list(set(internal_links)),
            external_links=list(set(external_links)),
        )

    def _prioritize_links(self, links: list[str], base_domain: str) -> list[str]:
        """Rank internal links by likely intelligence value."""
        scored: list[tuple[int, str]] = []
        seen: set[str] = set()

        for link in links:
            canonical = self._canonicalize_url(link)
            if canonical in seen:
                continue
            seen.add(canonical)

            parsed = urlparse(link)
            path_lower = parsed.path.lower()
            score = 0
            for kw in HIGH_VALUE_KEYWORDS:
                if kw in path_lower:
                    score += 10

            # Penalize excessively deep paths
            segments = [s for s in path_lower.split("/") if s]
            score -= len(segments)

            scored.append((score, link))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [link for _, link in scored]

    @staticmethod
    def _canonicalize_url(url: str) -> str:
        """Strip trailing slash and fragments for deduplication."""
        parsed = urlparse(url)
        path = parsed.path.rstrip("/")
        return f"{parsed.scheme}://{parsed.netloc}{path}"
