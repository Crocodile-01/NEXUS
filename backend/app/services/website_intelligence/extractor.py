from __future__ import annotations

import re
from urllib.parse import urlparse

from app.services.website_intelligence.crawler import CrawledPage
from app.services.website_intelligence.schemas import (
    IdentifiedEntity,
    IdentifiedProduct,
    OrganizationProfile,
    ReportRelationship,
)
from app.sources.base import (
    ExtractedEntity,
    ExtractedRelationship,
    RawEvidence,
    SourceResult,
)

ROLE_PATTERNS: list[str] = [
    r"\b([A-Z][a-z]+ [A-Z][a-z]+),?\s+(?:is the\s+)?(CEO|Chief Executive Officer|CTO|Chief Technology Officer|COO|CFO|Founder|Co-Founder|President|Director|VP|Head of [A-Za-z]+)\b",
    r"\b(CEO|Chief Executive Officer|CTO|Founder|Co-Founder|President)\s+([A-Z][a-z]+ [A-Z][a-z]+)\b",
]

PRODUCT_PATTERNS: list[str] = [
    r"\b(?:offers|develops|builds|delivers|provides)\s+([A-Z][A-Za-z0-9]+(?:\s+[A-Z][A-Za-z0-9]+)?),?\s+(?:our|the|a)\s+(?:flagship|platform|solution|product|service|tool|software|engine)\b",
    r"\b([A-Z][A-Za-z0-9]+(?:\s+[A-Z][A-Za-z0-9]+)?)\s+is\s+(?:our|the)\s+(?:flagship|primary|core)\s+(?:product|platform|solution|service|tool)\b",
]


class WebsiteEntityExtractor:
    """
    Deterministic entity, relationship, and organization profile extractor
    from crawled website pages with strict evidentiary provenance.
    """

    @classmethod
    def extract_organization_profile(
        cls,
        pages: list[CrawledPage],
        target_url: str,
    ) -> OrganizationProfile:
        """Derive organization name, description, domains, and social links."""
        parsed = urlparse(target_url)
        canonical_domain = parsed.netloc.lower()
        canonical_domain = canonical_domain.removeprefix("www.")

        homepage = pages[0] if pages else None

        # 1. Name Derivation
        org_name = cls._extract_org_name(homepage, canonical_domain)

        # 2. Description
        description = None
        if homepage and homepage.description:
            description = homepage.description
        elif homepage and homepage.extracted_text:
            lines = [line.strip() for line in homepage.extracted_text.splitlines() if len(line.strip()) > 30]
            if lines:
                description = lines[0]

        # 3. Social links from external links
        social_links: list[str] = []
        if homepage:
            for link in homepage.external_links:
                link_lower = link.lower()
                if any(p in link_lower for p in ("twitter.com", "x.com", "linkedin.com", "github.com", "youtube.com")):
                    social_links.append(link)

        # 4. Products / Services from pages
        products_services: list[str] = []
        for p in pages:
            if any(k in p.url.lower() for k in ("product", "service", "solution")) and p.title and p.title not in products_services:
                products_services.append(p.title)

        return OrganizationProfile(
            name=org_name,
            legal_name=None,
            description=description,
            headquarters=None,
            website_url=target_url,
            canonical_domain=canonical_domain,
            domains=[canonical_domain],
            products_services=products_services[:5],
            social_links=social_links[:5],
        )

    @classmethod
    def extract_entities_and_relationships(
        cls,
        pages: list[CrawledPage],
        org_profile: OrganizationProfile,
    ) -> tuple[list[IdentifiedEntity], list[IdentifiedProduct], list[ReportRelationship]]:
        """
        Extract named entities, products, and evidentiary relationships from all crawled pages.
        """
        entities: dict[str, IdentifiedEntity] = {}
        products: dict[str, IdentifiedProduct] = {}
        relationships: list[ReportRelationship] = []

        # 1. Primary Organization & Domain Entity
        entities[org_profile.name] = IdentifiedEntity(
            name=org_profile.name,
            entity_type="COMPANY",
            source_url=org_profile.website_url,
            evidence_snippet=org_profile.description or f"Primary organization operating {org_profile.canonical_domain}",
            confidence=0.98,
        )

        entities[org_profile.canonical_domain] = IdentifiedEntity(
            name=org_profile.canonical_domain,
            entity_type="DOMAIN",
            source_url=org_profile.website_url,
            evidence_snippet=f"Canonical web domain for {org_profile.name}",
            confidence=1.0,
        )

        relationships.append(
            ReportRelationship(
                source_entity=org_profile.name,
                source_entity_type="COMPANY",
                relationship_type="operates",
                target_entity=org_profile.canonical_domain,
                target_entity_type="DOMAIN",
                confidence=0.99,
                supporting_evidence=f"{org_profile.name} is the primary entity operating {org_profile.canonical_domain}",
            )
        )

        # 2. Process Page Texts for People, Products, Repositories
        for page in pages:
            text = page.extracted_text
            if not text:
                continue

            # People & Roles
            for pattern in ROLE_PATTERNS:
                for match in re.finditer(pattern, text):
                    groups = match.groups()
                    if len(groups) == 2:
                        # Check which group is name vs role
                        if any(r in groups[0] for r in ("CEO", "CTO", "Founder", "President")):
                            role, name = groups[0], groups[1]
                        else:
                            name, role = groups[0], groups[1]

                        name = name.strip()
                        if name not in entities and len(name.split()) >= 2:
                            snippet_start = max(0, match.start() - 20)
                            snippet_end = min(len(text), match.end() + 30)
                            snippet = text[snippet_start:snippet_end].strip()

                            entities[name] = IdentifiedEntity(
                                name=name,
                                entity_type="PERSON",
                                role_or_title=role,
                                source_url=page.url,
                                evidence_snippet=snippet,
                                confidence=0.88,
                            )

                            relationships.append(
                                ReportRelationship(
                                    source_entity=org_profile.name,
                                    source_entity_type="COMPANY",
                                    relationship_type="employs",
                                    target_entity=name,
                                    target_entity_type="PERSON",
                                    confidence=0.88,
                                    supporting_evidence=snippet,
                                )
                            )

            # Products
            for pattern in PRODUCT_PATTERNS:
                for match in re.finditer(pattern, text):
                    prod_name = match.group(1).strip()
                    if prod_name not in products and len(prod_name) > 2 and prod_name.lower() != org_profile.name.lower():
                        snippet_start = max(0, match.start() - 20)
                        snippet_end = min(len(text), match.end() + 30)
                        snippet = text[snippet_start:snippet_end].strip()

                        products[prod_name] = IdentifiedProduct(
                            name=prod_name,
                            description=snippet,
                            product_type="PRODUCT",
                            source_url=page.url,
                            evidence_snippet=snippet,
                            confidence=0.85,
                        )

                        entities[prod_name] = IdentifiedEntity(
                            name=prod_name,
                            entity_type="PRODUCT",
                            source_url=page.url,
                            evidence_snippet=snippet,
                            confidence=0.85,
                        )

                        relationships.append(
                            ReportRelationship(
                                source_entity=org_profile.name,
                                source_entity_type="COMPANY",
                                relationship_type="develops",
                                target_entity=prod_name,
                                target_entity_type="PRODUCT",
                                confidence=0.88,
                                supporting_evidence=snippet,
                            )
                        )

            # GitHub Repositories
            for ext_link in page.external_links:
                if "github.com/" in ext_link:
                    parsed_gh = urlparse(ext_link)
                    parts = [p for p in parsed_gh.path.split("/") if p]
                    if len(parts) >= 2:
                        repo_name = f"{parts[0]}/{parts[1]}"
                        if repo_name not in entities:
                            entities[repo_name] = IdentifiedEntity(
                                name=repo_name,
                                entity_type="REPOSITORY",
                                source_url=page.url,
                                evidence_snippet=f"Linked GitHub repository: {ext_link}",
                                confidence=0.92,
                            )
                            relationships.append(
                                ReportRelationship(
                                    source_entity=org_profile.name,
                                    source_entity_type="COMPANY",
                                    relationship_type="maintains_repository",
                                    target_entity=repo_name,
                                    target_entity_type="REPOSITORY",
                                    confidence=0.90,
                                    supporting_evidence=f"Public repository linked from {page.url}",
                                )
                            )

        return list(entities.values()), list(products.values()), relationships

    @classmethod
    def to_source_result(
        cls,
        pages: list[CrawledPage],
        org_profile: OrganizationProfile,
        entities: list[IdentifiedEntity],
        relationships: list[ReportRelationship],
    ) -> SourceResult:
        """Convert crawled pages and extracted items into standard NEXUS SourceResult for evidence engine."""
        evidence_list: list[RawEvidence] = []
        for p in pages:
            if not p.extracted_text:
                continue
            evidence_list.append(
                RawEvidence(
                    source_name="trafilatura",
                    url=p.url,
                    extracted_snippet=p.extracted_text[:1000].replace("\n", " ").strip(),
                    raw_content=p.extracted_text,
                    metadata={"title": p.title, "status_code": p.status_code},
                )
            )

        extracted_entities = [
            ExtractedEntity(
                name=e.name,
                entity_type=e.entity_type,
                confidence=e.confidence,
                metadata={"source_url": e.source_url},
            )
            for e in entities
        ]

        extracted_relationships = [
            ExtractedRelationship(
                source_entity=r.source_entity,
                source_entity_type=r.source_entity_type,
                target_entity=r.target_entity,
                target_entity_type=r.target_entity_type,
                relationship_type=r.relationship_type,
                confidence=r.confidence,
            )
            for r in relationships
        ]

        return SourceResult(
            success=True,
            source_name="trafilatura",
            query=org_profile.website_url,
            evidence=evidence_list,
            entities=extracted_entities,
            relationships=extracted_relationships,
        )

    @classmethod
    def _extract_org_name(cls, homepage: CrawledPage | None, canonical_domain: str) -> str:
        """Extract organization name from title, copyright, or domain."""
        if not homepage:
            return canonical_domain.split(".")[0].capitalize()

        # Check copyright notice in extracted text: e.g. "© 2026 Example Corp"
        cp_match = re.search(r"(?:©|\bCopyright\b)\s*(?:\d{4})?\s*([A-Z][A-Za-z0-9\s,.\-&]+?)(?:\.|\bAll rights\b|\n|$)", homepage.extracted_text)
        if cp_match:
            candidate = cp_match.group(1).strip()
            if 2 <= len(candidate) <= 50 and not any(w in candidate.lower() for w in ("all rights", "reserved", "the")):
                return candidate

        # Check title tag: e.g. "Example Corp - Cloud Solutions" -> "Example Corp"
        if homepage.title:
            parts = re.split(r"[\-|–|—|:\|•]", homepage.title)
            if parts:
                candidate = parts[0].strip()
                if 2 <= len(candidate) <= 40:
                    return candidate

        # Fallback to domain name
        domain_parts = canonical_domain.split(".")
        return domain_parts[0].capitalize()
