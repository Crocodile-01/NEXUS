from __future__ import annotations

import re
from typing import TYPE_CHECKING

from app.services.website_intelligence.schemas import (
    DetectedTechnology,
    TechClassification,
)

if TYPE_CHECKING:
    from app.services.website_intelligence.crawler import CrawledPage

# Script substring mappings: (pattern, name, category)
SCRIPT_SIGNATURES: list[tuple[str, str, str]] = [
    ("react", "React", "JavaScript Framework"),
    ("vue", "Vue.js", "JavaScript Framework"),
    ("angular", "Angular", "JavaScript Framework"),
    ("_next", "Next.js", "React Framework"),
    ("next.js", "Next.js", "React Framework"),
    ("_nuxt", "Nuxt.js", "Vue Framework"),
    ("nuxt.js", "Nuxt.js", "Vue Framework"),
    ("jquery", "jQuery", "JavaScript Library"),
    ("bootstrap", "Bootstrap", "CSS Framework"),
    ("tailwind", "Tailwind CSS", "CSS Framework"),
    ("alpine", "Alpine.js", "JavaScript Framework"),
    ("htmx", "htmx", "JavaScript Library"),
    ("gtag", "Google Analytics", "Analytics"),
    ("google-analytics", "Google Analytics", "Analytics"),
    ("cloudflare", "Cloudflare", "CDN / Security"),
]

# Explicit text tech keyword mentions
EXPLICIT_TECH_KEYWORDS: list[tuple[str, str, str]] = [
    ("python", "Python", "Programming Language"),
    ("pytorch", "PyTorch", "Machine Learning Framework"),
    ("tensorflow", "TensorFlow", "Machine Learning Framework"),
    ("fastapi", "FastAPI", "Web Framework"),
    ("docker", "Docker", "Containerization"),
    ("kubernetes", "Kubernetes", "Container Orchestration"),
    ("aws", "Amazon Web Services (AWS)", "Cloud Infrastructure"),
    ("azure", "Microsoft Azure", "Cloud Infrastructure"),
    ("google cloud", "Google Cloud Platform (GCP)", "Cloud Infrastructure"),
    ("postgresql", "PostgreSQL", "Database"),
    ("graphql", "GraphQL", "API Technology"),
    ("rust", "Rust", "Programming Language"),
    ("golang", "Go", "Programming Language"),
]


class TechDetector:
    """
    Passive technology identifier analyzing HTML metadata, script assets, HTTP headers,
    and explicit text disclosures. Strictly adheres to PASSIVE_PUBLIC observation.
    """

    @classmethod
    def detect_technologies(cls, pages: list[CrawledPage]) -> list[DetectedTechnology]:
        """
        Analyze crawled pages and return deduplicated list of detected technologies.
        """
        detected: dict[str, DetectedTechnology] = {}

        for page in pages:
            # 1. Check Generator Tag
            if page.meta_generator:
                gen_lower = page.meta_generator.lower()
                if "wordpress" in gen_lower:
                    detected["WordPress"] = DetectedTechnology(
                        name="WordPress",
                        category="CMS",
                        classification=TechClassification.DETECTED,
                        evidence_snippet=f"meta generator='{page.meta_generator}'",
                        confidence=0.98,
                    )
                elif "gatsby" in gen_lower:
                    detected["Gatsby"] = DetectedTechnology(
                        name="Gatsby",
                        category="Static Site Generator",
                        classification=TechClassification.DETECTED,
                        evidence_snippet=f"meta generator='{page.meta_generator}'",
                        confidence=0.98,
                    )
                elif "hugo" in gen_lower:
                    detected["Hugo"] = DetectedTechnology(
                        name="Hugo",
                        category="Static Site Generator",
                        classification=TechClassification.DETECTED,
                        evidence_snippet=f"meta generator='{page.meta_generator}'",
                        confidence=0.98,
                    )
                elif "shopify" in gen_lower:
                    detected["Shopify"] = DetectedTechnology(
                        name="Shopify",
                        category="E-commerce",
                        classification=TechClassification.DETECTED,
                        evidence_snippet=f"meta generator='{page.meta_generator}'",
                        confidence=0.98,
                    )
                elif "webflow" in gen_lower:
                    detected["Webflow"] = DetectedTechnology(
                        name="Webflow",
                        category="Website Builder",
                        classification=TechClassification.DETECTED,
                        evidence_snippet=f"meta generator='{page.meta_generator}'",
                        confidence=0.98,
                    )
                else:
                    detected[page.meta_generator] = DetectedTechnology(
                        name=page.meta_generator,
                        category="Web Platform",
                        classification=TechClassification.DETECTED,
                        evidence_snippet=f"meta generator='{page.meta_generator}'",
                        confidence=0.95,
                    )

            # 2. Check Script Sources
            for src in page.script_srcs:
                src_lower = src.lower()
                for pattern, name, cat in SCRIPT_SIGNATURES:
                    if pattern in src_lower and name not in detected:
                        detected[name] = DetectedTechnology(
                            name=name,
                            category=cat,
                            classification=TechClassification.DETECTED,
                            evidence_snippet=f"script src='{src[:150]}'",
                            confidence=0.92,
                        )

            # 3. Check Response Headers
            server = page.headers.get("server", "").lower()
            if server:
                if "cloudflare" in server and "Cloudflare" not in detected:
                    detected["Cloudflare"] = DetectedTechnology(
                        name="Cloudflare",
                        category="CDN / Security",
                        classification=TechClassification.DETECTED,
                        evidence_snippet=f"Server: {page.headers.get('server')}",
                        confidence=0.95,
                    )
                elif "nginx" in server and "Nginx" not in detected:
                    detected["Nginx"] = DetectedTechnology(
                        name="Nginx",
                        category="Web Server",
                        classification=TechClassification.DETECTED,
                        evidence_snippet=f"Server: {page.headers.get('server')}",
                        confidence=0.95,
                    )
                elif "apache" in server and "Apache" not in detected:
                    detected["Apache"] = DetectedTechnology(
                        name="Apache",
                        category="Web Server",
                        classification=TechClassification.DETECTED,
                        evidence_snippet=f"Server: {page.headers.get('server')}",
                        confidence=0.95,
                    )

            powered_by = page.headers.get("x-powered-by", "").lower()
            if powered_by:
                if "express" in powered_by and "Express.js" not in detected:
                    detected["Express.js"] = DetectedTechnology(
                        name="Express.js",
                        category="Web Framework",
                        classification=TechClassification.DETECTED,
                        evidence_snippet=f"X-Powered-By: {page.headers.get('x-powered-by')}",
                        confidence=0.95,
                    )
                elif "php" in powered_by and "PHP" not in detected:
                    detected["PHP"] = DetectedTechnology(
                        name="PHP",
                        category="Programming Language",
                        classification=TechClassification.DETECTED,
                        evidence_snippet=f"X-Powered-By: {page.headers.get('x-powered-by')}",
                        confidence=0.95,
                    )

            # 4. Check Raw HTML DOM Signatures
            raw_html = page.raw_html.lower()
            if "__next" in raw_html and "Next.js" not in detected:
                detected["Next.js"] = DetectedTechnology(
                    name="Next.js",
                    category="React Framework",
                    classification=TechClassification.DETECTED,
                    evidence_snippet="Found '__next' container id in DOM",
                    confidence=0.95,
                )
            if "wp-content" in raw_html and "WordPress" not in detected:
                detected["WordPress"] = DetectedTechnology(
                    name="WordPress",
                    category="CMS",
                    classification=TechClassification.DETECTED,
                    evidence_snippet="Found 'wp-content' asset path in DOM",
                    confidence=0.95,
                )

            # 5. Check Explicit Text Mentions
            text_lower = page.extracted_text.lower()
            for kw, name, cat in EXPLICIT_TECH_KEYWORDS:
                if name in detected:
                    continue
                # Match patterns like "powered by [kw]", "built with [kw]", "developed in [kw]", "utilizes [kw]"
                pattern = rf"\b(powered by|built with|developed in|written in|stack includes|integrates with|utilizes|uses|runs on|leverages)\s+{kw}\b"
                match = re.search(pattern, text_lower)
                if match:
                    snippet_start = max(0, match.start() - 30)
                    snippet_end = min(len(page.extracted_text), match.end() + 50)
                    detected[name] = DetectedTechnology(
                        name=name,
                        category=cat,
                        classification=TechClassification.EXPLICIT,
                        evidence_snippet=page.extracted_text[snippet_start:snippet_end].strip(),
                        confidence=0.90,
                    )

        # 6. Inferred Technologies based on detected core platforms
        if "Next.js" in detected and "React" not in detected:
            detected["React"] = DetectedTechnology(
                name="React",
                category="JavaScript Framework",
                classification=TechClassification.INFERRED,
                evidence_snippet="Inferred from detected Next.js framework",
                confidence=0.85,
            )
        if "WordPress" in detected and "PHP" not in detected:
            detected["PHP"] = DetectedTechnology(
                name="PHP",
                category="Programming Language",
                classification=TechClassification.INFERRED,
                evidence_snippet="Inferred from detected WordPress CMS",
                confidence=0.85,
            )

        return list(detected.values())
