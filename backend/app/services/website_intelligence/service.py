from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING
from urllib.parse import urlparse

from app.models.agent_run import AgentRun
from app.models.finding import Finding
from app.models.investigation import Investigation
from app.models.task import InvestigationTask
from app.security.execution_scope import DEFAULT_SCOPE, ExecutionScope
from app.security.target_validator import validate_domain, validate_url
from app.services.evidence_engine import persist_source_result
from app.services.website_intelligence.crawler import CrawledPage, WebsiteCrawler
from app.services.website_intelligence.enricher import WebsiteEnricher
from app.services.website_intelligence.extractor import WebsiteEntityExtractor
from app.services.website_intelligence.report import ReportBuilder
from app.services.website_intelligence.schemas import (
    WebsiteIntelligenceReport,
    WebsiteInvestigationResponse,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class WebsiteIntelligenceService:
    """
    Orchestration service executing the complete, bounded Website / Domain
    Intelligence Research vertical slice.
    """

    @classmethod
    async def investigate_website(
        cls,
        target: str,
        objective: str | None = None,
        max_pages: int = 3,
        enrich: bool = True,
        db: AsyncSession | None = None,
        scope: ExecutionScope = DEFAULT_SCOPE,
    ) -> WebsiteInvestigationResponse:
        """
        Execute bounded website intelligence workflow:
          TARGET -> VALIDATE -> FETCH -> EXTRACT -> ANALYZE -> ENRICH -> VERIFY -> REPORT
        """
        # 1. Target Validation & Normalization
        clean_target = target.strip()
        if not clean_target.startswith(("http://", "https://")):
            clean_target = f"https://{clean_target}"

        if not validate_url(clean_target, allow_private=scope.allows_private_ip()):
            raise ValueError(f"Target '{target}' failed security / SSRF validation policy.")

        parsed_url = urlparse(clean_target)
        canonical_domain = parsed_url.netloc.lower()
        canonical_domain = canonical_domain.removeprefix("www.")

        if not validate_domain(canonical_domain):
            raise ValueError(f"Domain '{canonical_domain}' is not a valid FQDN domain name.")

        investigation_id = str(uuid.uuid4())

        # 2. Database Investigation Setup (if session provided)
        db_inv: Investigation | None = None
        if db:
            db_inv = Investigation(
                id=investigation_id,
                target=clean_target,
                target_type="domain",
                objective=objective or f"Website intelligence research on {canonical_domain}",
                status="in_progress",
                mode=scope.mode,
            )
            db.add(db_inv)
            await db.commit()
            await db.refresh(db_inv)

        # 3. Phase 1: Bounded Web Crawl & Content Extraction
        crawl_task_id = str(uuid.uuid4())
        if db:
            crawl_task = InvestigationTask(
                id=crawl_task_id,
                investigation_id=investigation_id,
                name="Web Crawl & Content Extraction",
                task_type="web_crawl",
                status="in_progress",
                started_at=datetime.now(UTC),
                input_data={"target_url": clean_target, "max_pages": max_pages},
            )
            db.add(crawl_task)
            await db.commit()

        crawler = WebsiteCrawler()
        crawled_pages: list[CrawledPage] = await crawler.crawl(
            target_url=clean_target,
            max_pages=max_pages,
            scope=scope,
        )

        # Handle crawl failure / unreachable target
        if not crawled_pages or not any(p.extracted_text for p in crawled_pages):
            if db:
                await cls._mark_task_failed(db, crawl_task_id, "Target unreachable or no readable content extracted")
                if db_inv:
                    db_inv.status = "failed"
                    await db.commit()

            empty_report = WebsiteIntelligenceReport(
                target_url=clean_target,
                canonical_domain=canonical_domain,
                investigation_id=investigation_id,
                generated_at=datetime.now(UTC),
                executive_summary=f"Investigation failed: could not retrieve readable text content from '{clean_target}'.",
                organization_profile=WebsiteEntityExtractor.extract_organization_profile([], clean_target),
                research_gaps=["Target website was unreachable or returned empty / unparseable content."],
            )
            return WebsiteInvestigationResponse(
                investigation_id=investigation_id,
                status="failed",
                target=clean_target,
                canonical_domain=canonical_domain,
                tasks_count=1,
                findings_count=0,
                evidence_count=0,
                entities_count=0,
                relationships_count=0,
                report=empty_report,
            )

        # 4. Phase 2: Passive Technology Detection
        from app.services.website_intelligence.tech_detector import TechDetector

        detected_technologies = TechDetector.detect_technologies(crawled_pages)

        # 5. Phase 3: Entity & Relationship Extraction
        org_profile = WebsiteEntityExtractor.extract_organization_profile(crawled_pages, clean_target)
        entities, products, relationships = WebsiteEntityExtractor.extract_entities_and_relationships(
            crawled_pages, org_profile
        )

        # Ingest into Evidence Engine
        source_result = WebsiteEntityExtractor.to_source_result(
            crawled_pages, org_profile, entities, relationships
        )
        if db:
            try:
                await persist_source_result(db=db, result=source_result)
                await cls._mark_task_completed(
                    db,
                    crawl_task_id,
                    {"pages_crawled": len(crawled_pages), "entities_extracted": len(entities)},
                )
            except Exception as exc:  # noqa: BLE001
                logger.error("Evidence persistence error: %s", exc)

        # 6. Phase 4: Public OSINT Enrichment
        enrichment_data: dict = {}
        if enrich:
            enrich_task_id = str(uuid.uuid4())
            if db:
                enrich_task = InvestigationTask(
                    id=enrich_task_id,
                    investigation_id=investigation_id,
                    name="Public OSINT Enrichment",
                    task_type="enrichment",
                    status="in_progress",
                    started_at=datetime.now(UTC),
                    input_data={"org_name": org_profile.name, "domain": canonical_domain},
                )
                db.add(enrich_task)
                await db.commit()

            has_research_signals = any("research" in p.url.lower() for p in crawled_pages)
            enrichment_data = await WebsiteEnricher.enrich(
                org_name=org_profile.name,
                canonical_domain=canonical_domain,
                has_research_signals=has_research_signals,
                scope=scope,
                db=db,
                task_id=enrich_task_id if db else None,
            )

            if db:
                await cls._mark_task_completed(
                    db,
                    enrich_task_id,
                    {"sources_consulted": enrichment_data.get("sources_consulted", [])},
                )

        # 7. Phase 5: Report Synthesis & Confidence Verification
        report = ReportBuilder.build_report(
            target_url=clean_target,
            canonical_domain=canonical_domain,
            investigation_id=investigation_id,
            pages=crawled_pages,
            org_profile=org_profile,
            entities=entities,
            products=products,
            relationships=relationships,
            technologies=detected_technologies,
            enrichment_data=enrichment_data,
        )

        # 8. Persist Findings & AgentRun in DB
        if db:
            try:
                # Add findings to findings table
                for f in report.findings:
                    db_finding = Finding(
                        investigation_id=investigation_id,
                        claim=f.claim,
                        classification=f.classification.value,
                        confidence_score=f.confidence_score,
                        created_at=datetime.now(UTC),
                    )
                    db.add(db_finding)

                # Add AgentRun record
                agent_run = AgentRun(
                    investigation_id=investigation_id,
                    agent_role="WebsiteResearchManager",
                    model_name="NEXUS-Deterministic-V1",
                    started_at=datetime.now(UTC),
                    ended_at=datetime.now(UTC),
                )
                db.add(agent_run)

                # Mark investigation completed
                if db_inv:
                    db_inv.status = "completed"

                await db.commit()
            except Exception as exc:  # noqa: BLE001
                logger.error("DB commit error for findings/agent_run: %s", exc)

        tasks_count = 2 if enrich else 1
        return WebsiteInvestigationResponse(
            investigation_id=investigation_id,
            status="completed",
            target=clean_target,
            canonical_domain=canonical_domain,
            tasks_count=tasks_count,
            findings_count=len(report.findings),
            evidence_count=len(crawled_pages),
            entities_count=len(report.people_and_organizations),
            relationships_count=len(report.relationships),
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

    @staticmethod
    async def _mark_task_failed(db: AsyncSession, task_id: str, error_msg: str) -> None:
        from sqlalchemy import select

        stmt = select(InvestigationTask).where(InvestigationTask.id == task_id)
        task = (await db.execute(stmt)).scalar_one_or_none()
        if task:
            task.status = "failed"
            task.completed_at = datetime.now(UTC)
            task.output_data = {"error": error_msg}
            await db.commit()
