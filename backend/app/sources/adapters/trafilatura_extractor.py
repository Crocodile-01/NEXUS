import logging

import trafilatura

from app.security.target_validator import validate_url
from app.sources.base import (
    RawEvidence,
    SourceAdapter,
    SourceMetadata,
    SourceResult,
)
from app.sources.http_client import get_httpx_client

logger = logging.getLogger(__name__)


class TrafilaturaAdapter(SourceAdapter):
    """
    Adapter for retrieving web pages and extracting clean markdown/text content using Trafilatura.
    """

    @property
    def metadata(self) -> SourceMetadata:
        return SourceMetadata(
            name="trafilatura",
            category="web",
            reliability_tier="THIRD_PARTY",
            is_passive=True,
            rate_limit_per_minute=60,
            timeout_seconds=15,
        )

    async def fetch(self, target: str) -> SourceResult:
        if not validate_url(target):
            return SourceResult(
                success=False,
                source_name=self.metadata.name,
                query=target,
                error_message=f"Target URL '{target}' failed security/SSRF validation",
            )

        try:
            async with get_httpx_client(timeout_seconds=self.metadata.timeout_seconds) as client:
                response = await client.get(target)
                response.raise_for_status()
                html_content = response.text
        except Exception as exc:  # noqa: BLE001
            return SourceResult(
                success=False,
                source_name=self.metadata.name,
                query=target,
                error_message=f"Web fetch error for {target}: {exc!s}",
            )

        extracted_text = trafilatura.extract(
            html_content,
            include_links=True,
            include_comments=False,
            output_format="txt",
        )

        if not extracted_text:
            return SourceResult(
                success=False,
                source_name=self.metadata.name,
                query=target,
                error_message="Trafilatura failed to extract meaningful text content from HTML",
            )

        snippet = extracted_text[:1000].strip().replace("\n", " ")

        return SourceResult(
            success=True,
            source_name=self.metadata.name,
            query=target,
            evidence=[
                RawEvidence(
                    source_name=self.metadata.name,
                    url=target,
                    extracted_snippet=snippet,
                    raw_content=extracted_text,
                    metadata={"content_length": len(extracted_text)},
                )
            ],
            entities=[],
            relationships=[],
        )

    async def search(self, query: str, limit: int = 5) -> SourceResult:
        if query.startswith(("http://", "https://")):
            return await self.fetch(query)
        return SourceResult(
            success=False,
            source_name=self.metadata.name,
            query=query,
            error_message="Trafilatura adapter search requires a valid URL target",
        )
