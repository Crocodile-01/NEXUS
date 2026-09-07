from __future__ import annotations

import re
from datetime import UTC, datetime

from app.agents.schemas import AgentFinding, FindingClassification
from app.services.website_intelligence.crawler import CrawledPage
from app.services.website_intelligence.schemas import (
    DetectedTechnology,
    IdentifiedEntity,
    IdentifiedProduct,
    OrganizationProfile,
    ReportRelationship,
    TimelineEvent,
    WebsiteIntelligenceReport,
)


class ReportBuilder:
    """
    Constructs the final structured WebsiteIntelligenceReport adhering to
    strict evidence-first principles and tiered confidence classifications.
    """

    @classmethod
    def build_report(
        cls,
        target_url: str,
        canonical_domain: str,
        investigation_id: str,
        pages: list[CrawledPage],
        org_profile: OrganizationProfile,
        entities: list[IdentifiedEntity],
        products: list[IdentifiedProduct],
        relationships: list[ReportRelationship],
        technologies: list[DetectedTechnology],
        enrichment_data: dict,
    ) -> WebsiteIntelligenceReport:
        """
        Synthesize crawled data, extractions, and enrichment into a comprehensive intelligence report.
        """
        now = datetime.now(UTC)

        # Merge additional entities and relationships from enrichment
        all_entities = list({e.name: e for e in entities + enrichment_data.get("additional_entities", [])}.values())
        all_relationships = relationships + enrichment_data.get("additional_relationships", [])
        sources_consulted = list(set(["trafilatura"] + enrichment_data.get("sources_consulted", [])))
        subdomains = enrichment_data.get("subdomains", [])
        if subdomains:
            org_profile.domains = list(set(org_profile.domains + subdomains))[:10]

        # 1. Timeline Events
        timeline: list[TimelineEvent] = []
        for page in pages:
            # Check copyright years in footer/text: e.g. "© 2018-2026"
            matches = re.findall(r"(?:©|\bCopyright\b)\s*(?:(\d{4})\s*[-–—]\s*)?(\d{4})", page.extracted_text)
            for m in matches:
                start_yr, end_yr = m[0], m[1]
                if start_yr:
                    timeline.append(
                        TimelineEvent(
                            date_or_year=start_yr,
                            event_description=f"Earliest copyright year observed on {page.url}",
                            source_ref=page.url,
                        )
                    )
                if end_yr:
                    timeline.append(
                        TimelineEvent(
                            date_or_year=end_yr,
                            event_description=f"Latest copyright notice year on {page.url}",
                            source_ref=page.url,
                        )
                    )
                break

        # 2. Evidence-First Findings Formulation
        findings: list[AgentFinding] = []

        # Organization Identity (FACT)
        findings.append(
            AgentFinding(
                claim=f"Website '{canonical_domain}' is operated by organization '{org_profile.name}'.",
                classification=FindingClassification.FACT,
                confidence_score=0.98,
                source_url=target_url,
                supporting_snippet=org_profile.description or f"Official website for {org_profile.name}",
            )
        )

        # Products (FACT)
        for prod in products[:3]:
            findings.append(
                AgentFinding(
                    claim=f"{org_profile.name} develops and offers the product '{prod.name}'.",
                    classification=FindingClassification.FACT,
                    confidence_score=prod.confidence,
                    source_url=prod.source_url,
                    supporting_snippet=prod.evidence_snippet,
                )
            )

        # People (SUPPORTED_INFERENCE / FACT)
        for ent in [e for e in all_entities if e.entity_type == "PERSON"][:3]:
            role_desc = f" as {ent.role_or_title}" if ent.role_or_title else ""
            findings.append(
                AgentFinding(
                    claim=f"Identified public personnel '{ent.name}' associated with {org_profile.name}{role_desc}.",
                    classification=FindingClassification.FACT if ent.role_or_title else FindingClassification.SUPPORTED_INFERENCE,
                    confidence_score=ent.confidence,
                    source_url=ent.source_url,
                    supporting_snippet=ent.evidence_snippet,
                )
            )

        # Technologies (FACT if detected, INFERRED if deduced)
        for tech in technologies[:5]:
            findings.append(
                AgentFinding(
                    claim=f"Website '{canonical_domain}' utilizes {tech.name} ({tech.category}).",
                    classification=FindingClassification.FACT if tech.classification.value != "INFERRED" else FindingClassification.SUPPORTED_INFERENCE,
                    confidence_score=tech.confidence,
                    source_url=target_url,
                    supporting_snippet=tech.evidence_snippet,
                )
            )

        # Subdomains (FACT from crt.sh)
        if subdomains:
            findings.append(
                AgentFinding(
                    claim=f"Discovered {len(subdomains)} public subdomains for '{canonical_domain}' in Certificate Transparency logs.",
                    classification=FindingClassification.FACT,
                    confidence_score=0.95,
                    source_url="https://crt.sh",
                    supporting_snippet=f"Subdomains: {', '.join(subdomains[:5])}",
                )
            )

        # Average Confidence
        avg_conf = sum(f.confidence_score for f in findings) / len(findings) if findings else 0.0

        # 3. Research Gaps
        research_gaps: list[str] = []
        if not any(e.entity_type == "PERSON" for e in all_entities):
            research_gaps.append("Executive leadership and key personnel could not be confirmed from public website text.")
        if not products:
            research_gaps.append("Specific proprietary products or services were not explicitly detailed in public crawl.")
        if not enrichment_data.get("sec_info", {}).get("cik"):
            research_gaps.append("Entity has no matching US SEC EDGAR filings (likely private or non-US entity).")
        if not technologies:
            research_gaps.append("Client-side technology signatures were masked or obfuscated behind edge proxies.")

        # 4. Executive Summary Synthesis
        summary_parts: list[str] = [
            f"Passive reconnaissance of '{canonical_domain}' identified organization '{org_profile.name}'."
        ]
        if org_profile.description:
            summary_parts.append(f"Profile: {org_profile.description}")
        if products:
            summary_parts.append(f"Identified products/offerings include: {', '.join(p.name for p in products)}.")
        if technologies:
            tech_summary = ", ".join(t.name for t in technologies[:4])
            summary_parts.append(f"Detected web technology stack: {tech_summary}.")
        if subdomains:
            summary_parts.append(f"Observed {len(subdomains)} active public subdomains via certificate transparency.")
        summary_parts.append(f"Investigation completed across {len(pages)} web page(s) and {len(sources_consulted)} source adapter(s).")
        executive_summary = " ".join(summary_parts)

        return WebsiteIntelligenceReport(
            target_url=target_url,
            canonical_domain=canonical_domain,
            investigation_id=investigation_id,
            generated_at=now,
            executive_summary=executive_summary,
            organization_profile=org_profile,
            people_and_organizations=all_entities,
            technologies=technologies,
            projects_and_products=products,
            relationships=all_relationships,
            sources_consulted=sources_consulted,
            evidence_count=len(pages),
            findings=findings,
            average_confidence=round(avg_conf, 3),
            timeline=timeline,
            research_gaps=research_gaps,
        )
