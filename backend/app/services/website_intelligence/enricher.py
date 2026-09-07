from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from app.security.execution_scope import DEFAULT_SCOPE, ExecutionScope
from app.services.website_intelligence.schemas import (
    IdentifiedEntity,
    ReportRelationship,
)
from app.tools.base import ToolRequest, ToolResult
from app.tools.boundary import ToolExecutionBoundary

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class WebsiteEnricher:
    """
    Selective public-source enricher executing bounded secondary lookups
    (crt.sh, Wikidata, SEC EDGAR, arXiv) strictly through ToolExecutionBoundary.
    """

    @classmethod
    async def enrich(
        cls,
        org_name: str,
        canonical_domain: str,
        has_research_signals: bool = False,
        scope: ExecutionScope = DEFAULT_SCOPE,
        db: AsyncSession | None = None,
        task_id: str | None = None,
    ) -> dict[str, Any]:
        """
        Execute bounded enrichment. Degrades gracefully if individual sources fail.
        """
        subdomains: list[str] = []
        additional_entities: list[IdentifiedEntity] = []
        additional_relationships: list[ReportRelationship] = []
        sources_consulted: list[str] = []
        wikidata_info: dict[str, Any] = {}
        sec_info: dict[str, Any] = {}
        research_papers: list[str] = []

        # 1. Certificate Transparency Lookup (crt.sh)
        try:
            crt_req = ToolRequest(target=canonical_domain, target_type="domain")
            crt_res: ToolResult = await ToolExecutionBoundary.execute(
                tool_name="lookup_certificate_transparency",
                request=crt_req,
                scope=scope,
                db=db,
                task_id=task_id,
            )
            sources_consulted.append("crt.sh")
            if crt_res.success and crt_res.source_result:
                for ent in crt_res.source_result.entities:
                    if ent.entity_type == "DOMAIN" and ent.name.lower() != canonical_domain:
                        subdomains.append(ent.name)
                        additional_entities.append(
                            IdentifiedEntity(
                                name=ent.name,
                                entity_type="DOMAIN",
                                source_url="https://crt.sh",
                                evidence_snippet=f"TLS certificate entry for {canonical_domain}",
                                confidence=0.95,
                            )
                        )
                        additional_relationships.append(
                            ReportRelationship(
                                source_entity=canonical_domain,
                                source_entity_type="DOMAIN",
                                relationship_type="has_subdomain",
                                target_entity=ent.name,
                                target_entity_type="DOMAIN",
                                confidence=0.95,
                                supporting_evidence="Discovered in Certificate Transparency logs",
                            )
                        )
        except Exception as exc:  # noqa: BLE001
            logger.warning("crt.sh enrichment failed: %s", exc)

        # 2. Wikidata Lookup
        if org_name and len(org_name) >= 2:
            try:
                wiki_req = ToolRequest(target=org_name, target_type="company")
                wiki_res: ToolResult = await ToolExecutionBoundary.execute(
                    tool_name="search_wikidata",
                    request=wiki_req,
                    scope=scope,
                    db=db,
                    task_id=task_id,
                )
                sources_consulted.append("wikidata")
                if wiki_res.success and wiki_res.source_result:
                    for ent in wiki_res.source_result.entities:
                        if ent.aliases:
                            wikidata_info["aliases"] = ent.aliases
                        if ent.metadata.get("description"):
                            wikidata_info["wikidata_description"] = ent.metadata.get("description")

                        additional_entities.append(
                            IdentifiedEntity(
                                name=ent.name,
                                entity_type=ent.entity_type,
                                source_url="https://www.wikidata.org",
                                evidence_snippet=f"Wikidata entity match for {org_name}",
                                confidence=0.90,
                            )
                        )
                    for rel in wiki_res.source_result.relationships:
                        additional_relationships.append(
                            ReportRelationship(
                                source_entity=rel.source_entity,
                                source_entity_type=rel.source_entity_type,
                                relationship_type=rel.relationship_type,
                                target_entity=rel.target_entity,
                                target_entity_type=rel.target_entity_type,
                                confidence=rel.confidence,
                                supporting_evidence="Verified Wikidata statement",
                            )
                        )
            except Exception as exc:  # noqa: BLE001
                logger.warning("Wikidata enrichment failed: %s", exc)

        # 3. SEC EDGAR Lookup
        if org_name and len(org_name) >= 2:
            try:
                sec_req = ToolRequest(target=org_name, target_type="company")
                sec_res: ToolResult = await ToolExecutionBoundary.execute(
                    tool_name="lookup_sec_company",
                    request=sec_req,
                    scope=scope,
                    db=db,
                    task_id=task_id,
                )
                sources_consulted.append("sec_edgar")
                if sec_res.success and sec_res.source_result:
                    for ent in sec_res.source_result.entities:
                        if ent.metadata.get("cik"):
                            sec_info["cik"] = ent.metadata.get("cik")
                            additional_entities.append(
                                IdentifiedEntity(
                                    name=f"{ent.name} (CIK: {ent.metadata['cik']})",
                                    entity_type="COMPANY",
                                    source_url="https://www.sec.gov/edgar",
                                    evidence_snippet=f"SEC EDGAR CIK record {ent.metadata['cik']}",
                                    confidence=0.98,
                                )
                            )
            except Exception as exc:  # noqa: BLE001
                logger.warning("SEC EDGAR enrichment failed: %s", exc)

        # 4. arXiv Academic Lookup (only if research signals are present)
        if has_research_signals and org_name:
            try:
                arxiv_req = ToolRequest(target=org_name, target_type="academic_query", limit=3)
                arxiv_res: ToolResult = await ToolExecutionBoundary.execute(
                    tool_name="search_arxiv",
                    request=arxiv_req,
                    scope=scope,
                    db=db,
                    task_id=task_id,
                )
                sources_consulted.append("arxiv")
                if arxiv_res.success and arxiv_res.source_result:
                    for ent in arxiv_res.source_result.entities:
                        if ent.entity_type == "RESEARCH_PAPER":
                            research_papers.append(ent.name)
                            additional_entities.append(
                                IdentifiedEntity(
                                    name=ent.name,
                                    entity_type="RESEARCH_PAPER",
                                    source_url="https://arxiv.org",
                                    evidence_snippet=f"arXiv paper associated with {org_name}",
                                    confidence=0.85,
                                )
                            )
            except Exception as exc:  # noqa: BLE001
                logger.warning("arXiv enrichment failed: %s", exc)

        return {
            "subdomains": list(set(subdomains))[:10],
            "wikidata_info": wikidata_info,
            "sec_info": sec_info,
            "research_papers": research_papers[:5],
            "additional_entities": additional_entities,
            "additional_relationships": additional_relationships,
            "sources_consulted": sources_consulted,
        }
