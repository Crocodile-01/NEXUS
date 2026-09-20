from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from app.security.execution_scope import DEFAULT_SCOPE, ExecutionScope
from app.services.intelligence_engine.schemas import ResearchCategory, ResearchQuestion
from app.sources.base import (
    ExtractedEntity,
    ExtractedRelationship,
    RawEvidence,
)
from app.tools.base import ToolRequest, ToolResult
from app.tools.boundary import ToolExecutionBoundary

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class MultiSourceOrchestrator:
    """
    Coordinates multi-source data collection across NEXUS source adapters
    strictly routed through ToolExecutionBoundary with budget limits.
    """

    @classmethod
    async def execute_question_research(
        cls,
        question: ResearchQuestion,
        scope: ExecutionScope = DEFAULT_SCOPE,
        db: AsyncSession | None = None,
        task_id: str | None = None,
        max_source_queries_remaining: int = 5,
    ) -> tuple[list[RawEvidence], list[ExtractedEntity], list[ExtractedRelationship], list[str]]:
        """
        Executes external source queries appropriate for a given ResearchQuestion.
        Returns aggregated raw evidence, extracted entities, extracted relationships,
        and list of consulted source names.
        """
        all_evidence: list[RawEvidence] = []
        all_entities: list[ExtractedEntity] = []
        all_relationships: list[ExtractedRelationship] = []
        sources_consulted: list[str] = []

        if max_source_queries_remaining <= 0:
            logger.info("Source query budget exhausted for question %s", question.id)
            return all_evidence, all_entities, all_relationships, sources_consulted

        # Select tools to query based on suggested_sources and category
        tools_to_run = cls._resolve_tools_for_question(question)
        queries_run = 0

        for tool_name, resolved_target, req_type in tools_to_run:
            if queries_run >= max_source_queries_remaining:
                break

            try:
                req = ToolRequest(target=resolved_target, target_type=req_type, limit=5)
                tool_res: ToolResult = await ToolExecutionBoundary.execute(
                    tool_name=tool_name,
                    request=req,
                    scope=scope,
                    db=db,
                    task_id=task_id,
                )
                queries_run += 1
                sources_consulted.append(tool_name)

                if tool_res.success and tool_res.source_result:
                    s_res = tool_res.source_result
                    all_evidence.extend(s_res.evidence)
                    all_entities.extend(s_res.entities)
                    all_relationships.extend(s_res.relationships)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Tool execution error for %s on %s: %s", tool_name, resolved_target, exc)

        question.sources_queried = sources_consulted
        question.findings_count = len(all_entities) + len(all_relationships)
        question.status = "answered" if (all_evidence or all_entities) else "unanswerable"

        return all_evidence, all_entities, all_relationships, sources_consulted

    @classmethod
    def _resolve_tools_for_question(
        cls,
        question: ResearchQuestion,
    ) -> list[tuple[str, str, str]]:
        """
        Determines the list of (tool_name, target, target_type) to execute
        for a specific research question.
        """
        tools: list[tuple[str, str, str]] = []
        cat = question.category
        target = question.target_entity
        target_type = question.target_entity_type

        # Normalize target for domain/company lookups
        clean_target = target.strip().removeprefix("https://").removeprefix("http://").split("/")[0]

        if cat == ResearchCategory.IDENTITY:
            if target_type in ("domain", "url"):
                # Query crt.sh for domain and wikidata for cleaned domain/name
                domain_base = clean_target.removeprefix("www.").split(".")[0]
                tools.append(("search_wikidata", domain_base, "company"))
                tools.append(("lookup_sec_company", domain_base, "company"))
            elif target_type in ("company", "organization"):
                tools.append(("search_wikidata", target, "company"))
                tools.append(("lookup_sec_company", target, "company"))

        elif cat == ResearchCategory.INFRASTRUCTURE:
            if target_type in ("domain", "url"):
                tools.append(("lookup_certificate_transparency", clean_target, "domain"))

        elif cat == ResearchCategory.RESEARCH:
            # Query arXiv and Semantic Scholar
            query_term = target
            if target_type in ("domain", "url"):
                query_term = clean_target.removeprefix("www.").split(".")[0]
            tools.append(("search_arxiv", query_term, "academic_query"))
            tools.append(("search_semantic_scholar", query_term, "academic_query"))

        elif cat == ResearchCategory.EXTERNAL_INTELLIGENCE:
            query_term = clean_target.removeprefix("www.").split(".")[0] if target_type in ("domain", "url") else target
            tools.append(("search_wikidata", query_term, "company"))

        elif cat == ResearchCategory.TECHNOLOGY and target_type == "url":
            tools.append(("fetch_webpage", target, "url"))

        elif cat == ResearchCategory.PEOPLE:
            tools.append(("search_wikidata", target, "person"))
            tools.append(("search_arxiv", target, "academic_query"))

        elif cat == ResearchCategory.ORGANIZATION and target_type in ("project", "product"):
            tools.append(("search_wikidata", target, "project"))

        # Fallback if no specific tools matched
        if not tools:
            if "wikidata" in question.suggested_sources:
                tools.append(("search_wikidata", target, target_type))
            elif "crt_sh" in question.suggested_sources:
                tools.append(("lookup_certificate_transparency", clean_target, "domain"))
            elif "sec_edgar" in question.suggested_sources:
                tools.append(("lookup_sec_company", target, "company"))

        return tools
