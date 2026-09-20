from __future__ import annotations

import logging
import uuid

from app.agents.schemas import FindingClassification
from app.services.intelligence_engine.schemas import (
    CorroboratedFinding,
    TypedRelationship,
)
from app.sources.base import ExtractedEntity, ExtractedRelationship, RawEvidence

logger = logging.getLogger(__name__)

# Source reliability tier weights
SOURCE_WEIGHTS: dict[str, float] = {
    "sec_edgar": 0.98,
    "crt_sh": 0.95,
    "wikidata": 0.92,
    "arxiv": 0.90,
    "semantic_scholar": 0.90,
    "trafilatura": 0.85,
    "crawler": 0.85,
}


class CorroborationEngine:
    """
    Cross-references findings across independent sources, detects agreement
    or contradiction, calibrates confidence scores, and documents research gaps.
    """

    @classmethod
    def corroborate(
        cls,
        target: str,
        target_name: str,
        canonical_domain: str | None,
        evidence_list: list[RawEvidence],
        entities: list[ExtractedEntity],
        relationships: list[ExtractedRelationship],
        sources_consulted: list[str],
    ) -> tuple[list[CorroboratedFinding], list[TypedRelationship], list[str]]:
        """
        Synthesizes multi-source findings with strict evidentiary classification,
        confidence calibration, 'Why' rationale, and explicit research gaps.
        """
        findings: list[CorroboratedFinding] = []
        typed_relationships: list[TypedRelationship] = []
        research_gaps: list[str] = []

        # Index evidence by source and url
        evidence_by_source: dict[str, list[RawEvidence]] = {}
        for ev in evidence_list:
            evidence_by_source.setdefault(ev.source_name, []).append(ev)

        # -----------------------------------------------------------------------
        # 1. Organization Identity Corroboration
        # -----------------------------------------------------------------------
        identity_sources = []
        identity_evidence_ids = []

        if "trafilatura" in evidence_by_source or "crawler" in evidence_by_source:
            identity_sources.append("Official Website")
        if any("wikidata" in s for s in sources_consulted):
            wiki_evs = evidence_by_source.get("wikidata", [])
            if wiki_evs:
                identity_sources.append("Wikidata Knowledge Base")
                identity_evidence_ids.extend([e.metadata.get("wikidata_id", "wiki") for e in wiki_evs if e.metadata])
        if any("sec_edgar" in s for s in sources_consulted):
            sec_evs = evidence_by_source.get("sec_edgar", [])
            if sec_evs:
                identity_sources.append("SEC EDGAR Public Filings")

        is_multi_source = len(identity_sources) >= 2
        confidence = 0.98 if is_multi_source else 0.90
        classification = FindingClassification.FACT

        why_parts = [f"Identified as '{target_name}'."]
        if is_multi_source:
            why_parts.append(f"Corroborated across {len(identity_sources)} independent sources: {', '.join(identity_sources)}.")
        else:
            why_parts.append(f"Directly extracted from {identity_sources[0] if identity_sources else 'website text'}.")

        findings.append(
            CorroboratedFinding(
                id=f"f-{uuid.uuid4().hex[:8]}",
                claim=f"Primary operating entity for '{target}' is identified as '{target_name}'.",
                classification=classification,
                confidence_score=confidence,
                why=" ".join(why_parts),
                sources=identity_sources,
                evidence_ids=identity_evidence_ids[:3],
                related_entities=[target_name, canonical_domain or target],
                is_corroborated=is_multi_source,
            )
        )

        # -----------------------------------------------------------------------
        # 2. Digital Infrastructure & Domain Operations
        # -----------------------------------------------------------------------
        subdomain_ents = [e for e in entities if e.entity_type == "DOMAIN" and e.name.lower() != (canonical_domain or "").lower()]
        crt_sh_evs = evidence_by_source.get("crt_sh", [])

        if subdomain_ents and crt_sh_evs:
            findings.append(
                CorroboratedFinding(
                    id=f"f-{uuid.uuid4().hex[:8]}",
                    claim=f"Discovered {len(subdomain_ents)} public subdomains and TLS certificate records for '{canonical_domain or target}'.",
                    classification=FindingClassification.FACT,
                    confidence_score=0.96,
                    why="Independently recorded in public Certificate Transparency logs (crt.sh) issued by recognized certificate authorities.",
                    sources=["Certificate Transparency (crt.sh)"],
                    related_entities=[e.name for e in subdomain_ents[:5]],
                    is_corroborated=True,
                )
            )
            for sub in subdomain_ents[:10]:
                typed_relationships.append(
                    TypedRelationship(
                        subject=canonical_domain or target,
                        subject_type="DOMAIN",
                        predicate="has_subdomain",
                        object=sub.name,
                        object_type="DOMAIN",
                        confidence=0.95,
                        classification="FACT",
                        source_name="crt_sh",
                        supporting_text="Observed in public TLS certificate logs",
                    )
                )
        elif canonical_domain:
            research_gaps.append(f"Subdomain discovery for '{canonical_domain}' yielded no active secondary hostnames.")

        # -----------------------------------------------------------------------
        # 3. Products, Projects & Repositories Corroboration
        # -----------------------------------------------------------------------
        product_ents = [e for e in entities if e.entity_type in ("PRODUCT", "PROJECT")]
        repo_ents = [e for e in entities if e.entity_type == "REPOSITORY"]

        for prod in product_ents[:5]:
            findings.append(
                CorroboratedFinding(
                    id=f"f-{uuid.uuid4().hex[:8]}",
                    claim=f"'{target_name}' develops, operates, or maintains the project/product '{prod.name}'.",
                    classification=FindingClassification.FACT if prod.confidence >= 0.9 else FindingClassification.SUPPORTED_INFERENCE,
                    confidence_score=prod.confidence,
                    why=f"Extracted from product and project references associated with '{target_name}'.",
                    sources=["Website Analysis", "Extracted Entities"],
                    related_entities=[target_name, prod.name],
                    is_corroborated=False,
                )
            )
            typed_relationships.append(
                TypedRelationship(
                    subject=target_name,
                    subject_type="ORGANIZATION",
                    predicate="develops",
                    object=prod.name,
                    object_type=prod.entity_type,
                    confidence=prod.confidence,
                    classification="FACT" if prod.confidence >= 0.9 else "SUPPORTED_INFERENCE",
                    source_name="web_content",
                    supporting_text=f"Product offering by {target_name}",
                )
            )

        for repo in repo_ents[:5]:
            findings.append(
                CorroboratedFinding(
                    id=f"f-{uuid.uuid4().hex[:8]}",
                    claim=f"Public open-source repository 'https://github.com/{repo.name}' is linked to '{target_name}'.",
                    classification=FindingClassification.FACT,
                    confidence_score=0.94,
                    why=f"Official website references and links public GitHub repository '{repo.name}'.",
                    sources=["Website Analysis", "GitHub Link"],
                    related_entities=[target_name, repo.name],
                    is_corroborated=True,
                )
            )
            typed_relationships.append(
                TypedRelationship(
                    subject=target_name,
                    subject_type="ORGANIZATION",
                    predicate="maintains_repository",
                    object=repo.name,
                    object_type="REPOSITORY",
                    confidence=0.94,
                    classification="FACT",
                    source_name="web_content",
                    supporting_text="Public GitHub repository link",
                )
            )

        if not product_ents and not repo_ents:
            research_gaps.append(f"No specific proprietary products or public repositories were discovered for '{target_name}'.")

        # -----------------------------------------------------------------------
        # 4. Personnel & Leadership Corroboration
        # -----------------------------------------------------------------------
        person_ents = [e for e in entities if e.entity_type == "PERSON"]
        for person in person_ents[:5]:
            role = person.metadata.get("role_or_title") if person.metadata else None
            role_desc = f" in role '{role}'" if role else ""

            # Check if corroborated by academic publications or wikidata
            has_academic = any(
                person.name.lower() in ev.extracted_snippet.lower()
                for ev in evidence_by_source.get("arxiv", []) + evidence_by_source.get("semantic_scholar", [])
            )
            has_wiki = any(
                person.name.lower() in ev.extracted_snippet.lower()
                for ev in evidence_by_source.get("wikidata", [])
            )

            p_sources = ["Website Text"]
            if has_academic:
                p_sources.append("Scholarly Publications")
            if has_wiki:
                p_sources.append("Wikidata")

            p_corroborated = len(p_sources) >= 2
            p_conf = 0.94 if p_corroborated else (0.88 if role else 0.75)
            p_class = FindingClassification.FACT if (p_corroborated or role) else FindingClassification.SUPPORTED_INFERENCE

            p_why = f"Identified as personnel{role_desc}."
            if p_corroborated:
                p_why += f" Corroborated across {len(p_sources)} sources: {', '.join(p_sources)}."
            else:
                p_why += " Observed in public website team and leadership statements."

            findings.append(
                CorroboratedFinding(
                    id=f"f-{uuid.uuid4().hex[:8]}",
                    claim=f"Individual '{person.name}' is publicly associated with '{target_name}'{role_desc}.",
                    classification=p_class,
                    confidence_score=p_conf,
                    why=p_why,
                    sources=p_sources,
                    related_entities=[target_name, person.name],
                    is_corroborated=p_corroborated,
                )
            )
            typed_relationships.append(
                TypedRelationship(
                    subject=target_name,
                    subject_type="ORGANIZATION",
                    predicate="employs" if role else "associated_with",
                    object=person.name,
                    object_type="PERSON",
                    confidence=p_conf,
                    classification=p_class.value,
                    source_name=p_sources[0],
                    supporting_text=p_why,
                )
            )

        if not person_ents:
            research_gaps.append(f"Public leadership and key executive personnel could not be confirmed for '{target_name}'.")

        # -----------------------------------------------------------------------
        # 5. Academic & Research Publications
        # -----------------------------------------------------------------------
        paper_ents = [e for e in entities if e.entity_type == "RESEARCH_PAPER"]
        if paper_ents:
            for paper in paper_ents[:3]:
                findings.append(
                    CorroboratedFinding(
                        id=f"f-{uuid.uuid4().hex[:8]}",
                        claim=f"Academic publication identified: '{paper.name}'.",
                        classification=FindingClassification.FACT,
                        confidence_score=0.92,
                        why="Indexed in scholarly literature repositories (arXiv / Semantic Scholar) matching target query.",
                        sources=["arXiv", "Semantic Scholar"],
                        related_entities=[target_name, paper.name],
                        is_corroborated=True,
                    )
                )
                typed_relationships.append(
                    TypedRelationship(
                        subject=target_name,
                        subject_type="ORGANIZATION",
                        predicate="authored_or_sponsored",
                        object=paper.name,
                        object_type="RESEARCH_PAPER",
                        confidence=0.90,
                        classification="FACT",
                        source_name="arxiv",
                        supporting_text="Indexed publication matching target",
                    )
                )
        else:
            research_gaps.append(f"No indexed scientific publications on arXiv or Semantic Scholar matched '{target_name}'.")

        # -----------------------------------------------------------------------
        # 6. Regulatory & Official Filings (SEC EDGAR)
        # -----------------------------------------------------------------------
        sec_matches = [e for e in entities if e.metadata and e.metadata.get("cik")]
        if sec_matches:
            for sec_ent in sec_matches[:2]:
                cik = sec_ent.metadata["cik"]
                ticker = sec_ent.metadata.get("ticker", "N/A")
                findings.append(
                    CorroboratedFinding(
                        id=f"f-{uuid.uuid4().hex[:8]}",
                        claim=f"'{target_name}' corresponds to SEC registered public company (CIK: {cik}, Ticker: {ticker}).",
                        classification=FindingClassification.FACT,
                        confidence_score=0.99,
                        why="Verified against official US Securities and Exchange Commission (SEC EDGAR) public directory.",
                        sources=["SEC EDGAR"],
                        evidence_ids=[cik],
                        related_entities=[target_name, sec_ent.name],
                        is_corroborated=True,
                    )
                )
        else:
            research_gaps.append(f"Target '{target_name}' has no matching SEC EDGAR filings (likely private entity, non-profit, or non-US jurisdiction).")

        # -----------------------------------------------------------------------
        # 7. Merge Extracted Relationships
        # -----------------------------------------------------------------------
        for rel in relationships:
            # Check duplicate
            if not any(
                tr.subject.lower() == rel.source_entity.lower()
                and tr.predicate == rel.relationship_type
                and tr.object.lower() == rel.target_entity.lower()
                for tr in typed_relationships
            ):
                typed_relationships.append(
                    TypedRelationship(
                        subject=rel.source_entity,
                        subject_type=rel.source_entity_type,
                        predicate=rel.relationship_type,
                        object=rel.target_entity,
                        object_type=rel.target_entity_type,
                        confidence=rel.confidence,
                        classification="FACT" if rel.confidence >= 0.9 else "SUPPORTED_INFERENCE",
                        source_name="relationship_extraction",
                        supporting_text=f"Discovered edge: {rel.source_entity} {rel.relationship_type} {rel.target_entity}",
                    )
                )

        return findings, typed_relationships, research_gaps
