from __future__ import annotations

import logging
import re
import time
import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING
from urllib.parse import urlparse

from app.models.agent_run import AgentRun
from app.models.finding import Finding
from app.models.investigation import Investigation
from app.models.task import InvestigationTask
from app.security.execution_scope import DEFAULT_SCOPE, ExecutionScope
from app.security.target_validator import validate_domain, validate_target, validate_url
from app.services.evidence_engine import persist_source_result
from app.services.intelligence_engine.corroboration import CorroborationEngine
from app.services.intelligence_engine.expander import EntityExpander
from app.services.intelligence_engine.planner import ResearchPlanner
from app.services.intelligence_engine.report_builder import IntelligenceReportBuilder
from app.services.intelligence_engine.schemas import (
    IntelligenceInvestigationRequest,
    IntelligenceInvestigationResponse,
    PlannerLimits,
    ResearchCategory,
)
from app.services.intelligence_engine.source_orchestrator import MultiSourceOrchestrator
from app.services.website_intelligence.crawler import CrawledPage, WebsiteCrawler
from app.services.website_intelligence.extractor import WebsiteEntityExtractor
from app.services.website_intelligence.schemas import DetectedTechnology, TimelineEvent
from app.services.website_intelligence.tech_detector import TechDetector
from app.sources.base import (
    ExtractedEntity,
    ExtractedRelationship,
    RawEvidence,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class IntelligenceEngineService:
    """
    Core orchestrator executing the complete, bounded NEXUS Intelligence Engine 1.0 workflow.
    """

    @classmethod
    async def investigate(
        cls,
        request: IntelligenceInvestigationRequest,
        db: AsyncSession | None = None,
        scope: ExecutionScope = DEFAULT_SCOPE,
    ) -> IntelligenceInvestigationResponse:
        """
        Executes bounded, multi-source intelligence investigation on a given target.
        """
        t0 = time.perf_counter()
        investigation_id = str(uuid.uuid4())
        raw_target = request.target.strip()
        target_type = request.target_type.strip().lower()

        # -----------------------------------------------------------------------
        # 1. Target Validation & Normalization
        # -----------------------------------------------------------------------
        clean_target = raw_target
        canonical_domain: str | None = None

        if target_type in ("domain", "url"):
            if not clean_target.startswith(("http://", "https://")):
                clean_target = f"https://{clean_target}"

            if not validate_url(clean_target, allow_private=scope.allows_private_ip()):
                raise ValueError(
                    f"Target '{raw_target}' failed security / SSRF validation policy. Only valid public HTTP/HTTPS URLs are allowed."
                )

            parsed_url = urlparse(clean_target)
            canonical_domain = parsed_url.netloc.lower().removeprefix("www.")
            if not validate_domain(canonical_domain):
                raise ValueError(f"Target '{canonical_domain}' is not a valid fully-qualified domain name (FQDN).")
        else:
            if not validate_target(clean_target, target_type, scope=scope):
                raise ValueError(f"Target '{raw_target}' of type '{target_type}' failed validation policy.")

        # -----------------------------------------------------------------------
        # 2. Database Investigation Setup
        # -----------------------------------------------------------------------
        db_inv: Investigation | None = None
        if db:
            db_inv = Investigation(
                id=investigation_id,
                target=clean_target,
                target_type=target_type,
                objective=request.objective or f"Multi-source intelligence investigation of {clean_target}",
                status="in_progress",
                mode=scope.mode,
            )
            db.add(db_inv)
            await db.commit()
            await db.refresh(db_inv)

        # -----------------------------------------------------------------------
        # 3. Formulate Bounded Research Plan
        # -----------------------------------------------------------------------
        limits = PlannerLimits(
            max_depth=request.max_depth,
            max_source_queries=request.max_source_queries,
        )
        plan = ResearchPlanner.generate_initial_plan(
            target=clean_target,
            target_type=target_type,
            objective=request.objective,
            limits=limits,
            investigation_id=investigation_id,
        )

        all_evidence: list[RawEvidence] = []
        all_entities: list[ExtractedEntity] = []
        all_relationships: list[ExtractedRelationship] = []
        sources_consulted: set[str] = set()
        detected_technologies: list[DetectedTechnology] = []
        timeline_events: list[TimelineEvent] = []
        visited_entities: set[str] = {clean_target.lower()}
        if canonical_domain:
            visited_entities.add(canonical_domain.lower())

        target_profile: dict = {
            "name": clean_target,
            "target": clean_target,
            "canonical_domain": canonical_domain,
            "website_url": clean_target if target_type in ("domain", "url") else None,
            "aliases": [],
        }

        # -----------------------------------------------------------------------
        # 4. Primary Target Exploration (Website Crawl if URL/Domain)
        # -----------------------------------------------------------------------
        crawled_pages: list[CrawledPage] = []
        if target_type in ("domain", "url"):
            crawl_task_id = str(uuid.uuid4())
            if db:
                crawl_task = InvestigationTask(
                    id=crawl_task_id,
                    investigation_id=investigation_id,
                    name=f"Primary Web Reconnaissance: {clean_target}",
                    task_type="primary_crawl",
                    status="in_progress",
                    started_at=datetime.now(UTC),
                    input_data={"target": clean_target},
                )
                db.add(crawl_task)
                await db.commit()

            crawler = WebsiteCrawler(timeout_seconds=10)
            crawled_pages = await crawler.crawl(target_url=clean_target, max_pages=3, scope=scope)

            if crawled_pages and any(p.extracted_text for p in crawled_pages):
                # Passive tech detection
                detected_technologies = TechDetector.detect_technologies(crawled_pages)

                # Entity & relationship extraction from crawl
                org_prof = WebsiteEntityExtractor.extract_organization_profile(crawled_pages, clean_target)
                target_profile["name"] = org_prof.name
                target_profile["description"] = org_prof.description
                target_profile["social_links"] = org_prof.social_links
                target_profile["products_services"] = org_prof.products_services

                extracted_ents, _extracted_prods, extracted_rels = WebsiteEntityExtractor.extract_entities_and_relationships(
                    crawled_pages, org_prof
                )

                # Evidence result for database
                crawl_source_result = WebsiteEntityExtractor.to_source_result(
                    crawled_pages, org_prof, extracted_ents, extracted_rels
                )
                all_evidence.extend(crawl_source_result.evidence)
                all_entities.extend(crawl_source_result.entities)
                all_relationships.extend(crawl_source_result.relationships)
                sources_consulted.add("trafilatura")

                # Ingest into DB
                if db:
                    try:
                        await persist_source_result(db=db, result=crawl_source_result)
                        await cls._mark_task_completed(db, crawl_task_id, {"pages": len(crawled_pages)})
                    except Exception as exc:  # noqa: BLE001
                        logger.error("Error persisting crawl source result: %s", exc)

                # Extract timeline hints from pages
                for page in crawled_pages:
                    matches = re.findall(r"(?:©|\bCopyright\b)\s*(?:(\d{4})\s*[-–—]\s*)?(\d{4})", page.extracted_text)
                    for m in matches:
                        if m[0]:
                            timeline_events.append(TimelineEvent(date_or_year=m[0], event_description=f"Earliest copyright notice on {page.url}", source_ref=page.url))
                        if m[1]:
                            timeline_events.append(TimelineEvent(date_or_year=m[1], event_description=f"Latest copyright notice on {page.url}", source_ref=page.url))
                        break

        # -----------------------------------------------------------------------
        # 5. Multi-Source Question Research
        # -----------------------------------------------------------------------
        prioritized_questions = ResearchPlanner.prioritize_questions(plan)

        for q in prioritized_questions:
            queries_remaining = plan.limits.max_source_queries - plan.total_queries_executed
            if queries_remaining <= 0:
                break

            # If question is about organization name, update target entity to extracted name if available
            if (
                target_profile.get("name")
                and q.category in (ResearchCategory.IDENTITY, ResearchCategory.ORGANIZATION, ResearchCategory.PEOPLE, ResearchCategory.EXTERNAL_INTELLIGENCE)
                and q.target_entity_type in ("domain", "url")
            ):
                q.target_entity = target_profile["name"]
                q.target_entity_type = "company"

            q_task_id = str(uuid.uuid4())
            if db:
                q_task = InvestigationTask(
                    id=q_task_id,
                    investigation_id=investigation_id,
                    name=f"Research [{q.category.value}]: {q.question[:120]}",
                    task_type=f"research_{q.category.value}",
                    depth_level=q.depth,
                    status="in_progress",
                    started_at=datetime.now(UTC),
                    input_data={"question": q.question, "target_entity": q.target_entity},
                )
                db.add(q_task)
                await db.commit()

            q_ev, q_ent, q_rel, q_sources = await MultiSourceOrchestrator.execute_question_research(
                question=q,
                scope=scope,
                db=db,
                task_id=q_task_id if db else None,
                max_source_queries_remaining=queries_remaining,
            )

            all_evidence.extend(q_ev)
            all_entities.extend(q_ent)
            all_relationships.extend(q_rel)
            sources_consulted.update(q_sources)
            plan.total_queries_executed += len(q_sources)

            if db:
                await cls._mark_task_completed(
                    db,
                    q_task_id,
                    {"sources_consulted": q_sources, "evidence_count": len(q_ev), "entities_count": len(q_ent)},
                )

        # -----------------------------------------------------------------------
        # 6. Bounded Entity Expansion
        # -----------------------------------------------------------------------
        if request.allow_expansion and plan.limits.max_depth > 1:
            expansion_leads = EntityExpander.evaluate_expansion_leads(
                entities=all_entities,
                relationships=all_relationships,
                current_depth=1,
                limits=plan.limits,
                visited=visited_entities,
            )

            for lead in expansion_leads:
                queries_remaining = plan.limits.max_source_queries - plan.total_queries_executed
                if queries_remaining <= 0:
                    break

                visited_entities.add(lead.entity_name.lower())
                expansion_questions = ResearchPlanner.generate_expansion_questions(lead, plan)

                for eq in expansion_questions:
                    queries_remaining = plan.limits.max_source_queries - plan.total_queries_executed
                    if queries_remaining <= 0:
                        break

                    eq_task_id = str(uuid.uuid4())
                    if db:
                        eq_task = InvestigationTask(
                            id=eq_task_id,
                            investigation_id=investigation_id,
                            name=f"Entity Expansion [{lead.entity_type}]: {lead.entity_name}",
                            task_type="entity_expansion",
                            depth_level=lead.depth,
                            status="in_progress",
                            started_at=datetime.now(UTC),
                            input_data={"lead": lead.entity_name, "lead_type": lead.entity_type},
                        )
                        db.add(eq_task)
                        await db.commit()

                    e_ev, e_ent, e_rel, e_sources = await MultiSourceOrchestrator.execute_question_research(
                        question=eq,
                        scope=scope,
                        db=db,
                        task_id=eq_task_id if db else None,
                        max_source_queries_remaining=queries_remaining,
                    )

                    all_evidence.extend(e_ev)
                    all_entities.extend(e_ent)
                    all_relationships.extend(e_rel)
                    sources_consulted.update(e_sources)
                    plan.total_queries_executed += len(e_sources)

                    if db:
                        await cls._mark_task_completed(
                            db,
                            eq_task_id,
                            {"expanded_lead": lead.entity_name, "sources": e_sources},
                        )

        # -----------------------------------------------------------------------
        # 7. Cross-Source Corroboration & Confidence Verification
        # -----------------------------------------------------------------------
        # Extract Wikidata aliases or description if present
        for ent in all_entities:
            if ent.aliases:
                target_profile["aliases"] = list(set(target_profile.get("aliases", []) + ent.aliases))
            if ent.metadata and ent.metadata.get("description") and not target_profile.get("description"):
                target_profile["description"] = ent.metadata.get("description")

        key_findings, typed_relationships, research_gaps = CorroborationEngine.corroborate(
            target=clean_target,
            target_name=target_profile.get("name", clean_target),
            canonical_domain=canonical_domain,
            evidence_list=all_evidence,
            entities=all_entities,
            relationships=all_relationships,
            sources_consulted=list(sources_consulted),
        )

        # -----------------------------------------------------------------------
        # 8. Report Synthesis
        # -----------------------------------------------------------------------
        elapsed_ms = round((time.perf_counter() - t0) * 1000, 2)
        metrics = {
            "execution_time_ms": elapsed_ms,
            "total_queries_executed": plan.total_queries_executed,
            "sources_consulted": list(sources_consulted),
            "entities_discovered": len(all_entities),
            "relationships_discovered": len(typed_relationships),
            "evidence_count": len(all_evidence),
            "corroborated_findings": sum(1 for f in key_findings if f.is_corroborated),
        }

        report = IntelligenceReportBuilder.build_report(
            target=clean_target,
            target_type=target_type,
            canonical_domain=canonical_domain,
            investigation_id=investigation_id,
            target_profile=target_profile,
            key_findings=key_findings,
            relationships=typed_relationships,
            technologies=detected_technologies,
            timeline=timeline_events,
            research_gaps=research_gaps,
            evidence_list=all_evidence,
            sources_consulted=list(sources_consulted),
            metrics=metrics,
        )

        # -----------------------------------------------------------------------
        # 9. Database Finalization (Findings, AgentRun, Investigation Status)
        # -----------------------------------------------------------------------
        if db:
            try:
                for f in key_findings:
                    db_finding = Finding(
                        investigation_id=investigation_id,
                        claim=f.claim,
                        classification=f.classification.value,
                        confidence_score=f.confidence_score,
                        created_at=datetime.now(UTC),
                    )
                    db.add(db_finding)

                agent_run = AgentRun(
                    investigation_id=investigation_id,
                    agent_role="NEXUS-Intelligence-Engine-1.0",
                    model_name="NEXUS-Deterministic-V1",
                    started_at=datetime.now(UTC),
                    ended_at=datetime.now(UTC),
                )
                db.add(agent_run)

                if db_inv:
                    db_inv.status = "completed"

                await db.commit()
            except Exception as exc:  # noqa: BLE001
                logger.error("Failed persisting final findings/agent_run: %s", exc)

        # Calculate tasks count
        tasks_count = len(plan.questions) + (1 if target_type in ("domain", "url") else 0)

        return IntelligenceInvestigationResponse(
            investigation_id=investigation_id,
            status="completed",
            target=clean_target,
            target_type=target_type,
            canonical_domain=canonical_domain,
            tasks_count=tasks_count,
            findings_count=len(key_findings),
            corroborated_findings_count=metrics["corroborated_findings"],
            entities_count=len(all_entities),
            relationships_count=len(typed_relationships),
            evidence_count=len(all_evidence),
            sources_consulted=list(sources_consulted),
            metrics=metrics,
            report=report,
        )

    @staticmethod
    async def _mark_task_completed(db: AsyncSession, task_id: str, output_data: dict) -> None:
        from sqlalchemy import select

        stmt = select(InvestigationTask).where(InvestigationTask.id == task_id)
        task = (await db.execute(stmt)).scalar_one_or_none()
        if task:
            task.status = "completed"
            task.completed_at = datetime.now(UTC)
            task.output_data = output_data
            await db.commit()
