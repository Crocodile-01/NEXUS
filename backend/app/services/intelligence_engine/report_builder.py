from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from app.services.intelligence_engine.expander import EntityExpander
from app.services.intelligence_engine.schemas import (
    CorroboratedFinding,
    IntelligenceReport,
    TypedRelationship,
)
from app.services.website_intelligence.schemas import DetectedTechnology, TimelineEvent
from app.sources.base import RawEvidence

logger = logging.getLogger(__name__)


class IntelligenceReportBuilder:
    """
    Builds the executive-grade, evidence-backed IntelligenceReport.
    Maximizes signal-over-noise and explicitly details research gaps.
    """

    @classmethod
    def build_report(
        cls,
        target: str,
        target_type: str,
        canonical_domain: str | None,
        investigation_id: str,
        target_profile: dict[str, Any],
        key_findings: list[CorroboratedFinding],
        relationships: list[TypedRelationship],
        technologies: list[DetectedTechnology],
        timeline: list[TimelineEvent],
        research_gaps: list[str],
        evidence_list: list[RawEvidence],
        sources_consulted: list[str],
        metrics: dict[str, Any],
    ) -> IntelligenceReport:
        """
        Synthesizes all corroborated intelligence into the final structured report.
        """
        now = datetime.now(UTC)
        org_name = target_profile.get("name", target)

        # 1. Discover multi-hop relationship chains
        chains = EntityExpander.discover_relationship_chains(relationships)
        target_profile["discovered_relationship_chains"] = [" -> ".join(c) for c in chains[:5]]

        # 2. Extract People & Leadership list
        people_list = []
        for rel in relationships:
            if rel.predicate in ("employs", "associated_with", "founded_by", "ceo_of", "cto_of") and rel.object_type == "PERSON":
                people_list.append({
                    "name": rel.object,
                    "relationship": rel.predicate,
                    "confidence": rel.confidence,
                    "classification": rel.classification,
                    "supporting_evidence": rel.supporting_text,
                })

        # 3. Extract Products & Repositories list
        products_and_projects = []
        for rel in relationships:
            if rel.predicate in ("develops", "maintains_repository", "operates") and rel.object_type in ("PRODUCT", "PROJECT", "REPOSITORY"):
                products_and_projects.append({
                    "name": rel.object,
                    "type": rel.object_type,
                    "relationship": rel.predicate,
                    "confidence": rel.confidence,
                    "classification": rel.classification,
                    "supporting_evidence": rel.supporting_text,
                })

        # 4. Extract Digital Infrastructure
        subdomains = [rel.object for rel in relationships if rel.predicate == "has_subdomain"]
        digital_infrastructure = {
            "canonical_domain": canonical_domain,
            "subdomains": subdomains[:15],
            "subdomains_count": len(subdomains),
            "certificate_transparency_source": "crt.sh" if any("crt_sh" in s for s in sources_consulted) else None,
        }

        # 5. Extract Academic Research & Publications
        publications = []
        for rel in relationships:
            if rel.object_type == "RESEARCH_PAPER":
                publications.append({
                    "title": rel.object,
                    "relationship": rel.predicate,
                    "confidence": rel.confidence,
                    "source": rel.source_name,
                })

        # 6. Technology Intelligence
        tech_list = [
            {
                "name": t.name,
                "category": t.category,
                "classification": t.classification.value,
                "confidence": t.confidence,
                "evidence_snippet": t.evidence_snippet,
            }
            for t in technologies
        ]

        # 7. Evidence Catalog
        evidence_catalog = [
            {
                "source_name": ev.source_name,
                "url": ev.url,
                "extracted_snippet": ev.extracted_snippet[:250],
                "publication_date": ev.publication_date,
                "content_hash": ev.content_hash,
            }
            for ev in evidence_list[:25]
        ]

        # 8. Formulate Executive Intelligence Summary
        executive_summary = cls._generate_executive_summary(
            org_name=org_name,
            target=target,
            canonical_domain=canonical_domain,
            key_findings=key_findings,
            sources_consulted=sources_consulted,
            products=products_and_projects,
            people=people_list,
            technologies=technologies,
            subdomains=subdomains,
            chains=chains,
        )

        return IntelligenceReport(
            target=target,
            target_type=target_type,
            canonical_domain=canonical_domain,
            investigation_id=investigation_id,
            generated_at=now,
            executive_intelligence=executive_summary,
            target_profile=target_profile,
            organization={
                "name": org_name,
                "description": target_profile.get("description"),
                "aliases": target_profile.get("aliases", []),
                "website_url": target_profile.get("website_url"),
            },
            products_and_projects=products_and_projects,
            people_and_leadership=people_list,
            technology_intelligence=tech_list,
            digital_infrastructure=digital_infrastructure,
            research_and_publications=publications,
            relationship_intelligence=relationships,
            key_findings=key_findings,
            timeline=timeline,
            research_gaps=research_gaps,
            evidence_catalog=evidence_catalog,
            metrics=metrics,
        )

    @classmethod
    def _generate_executive_summary(
        cls,
        org_name: str,
        target: str,
        canonical_domain: str | None,
        key_findings: list[CorroboratedFinding],
        sources_consulted: list[str],
        products: list[dict],
        people: list[dict],
        technologies: list[DetectedTechnology],
        subdomains: list[str],
        chains: list[list[str]],
    ) -> str:
        """
        Synthesizes a succinct, authoritative executive summary.
        """
        corroborated_count = sum(1 for f in key_findings if f.is_corroborated)
        facts_count = sum(1 for f in key_findings if f.classification.value == "FACT")

        parts = [
            f"NEXUS Intelligence Engine conducted a bounded, multi-source investigation of '{target}' identifying organization '{org_name}'."
        ]

        if canonical_domain:
            parts.append(f"Operating domain: '{canonical_domain}'.")

        if products:
            prod_names = ", ".join(p["name"] for p in products[:3])
            parts.append(f"Key products/projects include: {prod_names}.")

        if people:
            people_names = ", ".join(p["name"] for p in people[:3])
            parts.append(f"Public leadership/personnel identified: {people_names}.")

        if technologies:
            tech_names = ", ".join(t.name for t in technologies[:4])
            parts.append(f"Detected technology stack: {tech_names}.")

        if subdomains:
            parts.append(f"Discovered {len(subdomains)} public subdomains via certificate transparency.")

        if chains:
            sample_chain = " -> ".join(chains[0])
            parts.append(f"Discovered relationship chain: {sample_chain}.")

        parts.append(
            f"Investigation synthesized {len(key_findings)} core findings ({facts_count} FACTs, "
            f"{corroborated_count} cross-corroborated) across {len(sources_consulted)} source adapters."
        )

        return " ".join(parts)
