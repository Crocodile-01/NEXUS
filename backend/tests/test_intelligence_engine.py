from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from app.agents.schemas import FindingClassification
from app.models.agent_run import AgentRun
from app.models.finding import Finding
from app.models.investigation import Investigation
from app.models.task import InvestigationTask
from app.security.execution_scope import ExecutionScope
from app.services.intelligence_engine.corroboration import CorroborationEngine
from app.services.intelligence_engine.expander import EntityExpander
from app.services.intelligence_engine.planner import ResearchPlanner
from app.services.intelligence_engine.schemas import (
    EntityExpansionLead,
    IntelligenceInvestigationRequest,
    PlannerLimits,
    ResearchCategory,
    TypedRelationship,
)
from app.services.intelligence_engine.service import IntelligenceEngineService
from app.services.intelligence_engine.source_orchestrator import MultiSourceOrchestrator
from app.services.website_intelligence.crawler import CrawledPage
from app.sources.base import (
    ExtractedEntity,
    ExtractedRelationship,
    RawEvidence,
    SourceResult,
)
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

# ---------------------------------------------------------------------------
# 1. Research Planner Tests
# ---------------------------------------------------------------------------

def test_research_planner_generates_all_categories():
    """Verify that initial research plan covers all intelligence dimensions."""
    plan = ResearchPlanner.generate_initial_plan(
        target="https://nexustech.io",
        target_type="domain",
        objective="Analyze enterprise AI stack and leadership",
    )

    categories = {q.category for q in plan.questions}
    assert ResearchCategory.IDENTITY in categories
    assert ResearchCategory.ORGANIZATION in categories
    assert ResearchCategory.PEOPLE in categories
    assert ResearchCategory.TECHNOLOGY in categories
    assert ResearchCategory.INFRASTRUCTURE in categories
    assert ResearchCategory.RESEARCH in categories
    assert ResearchCategory.EXTERNAL_INTELLIGENCE in categories
    assert ResearchCategory.TEMPORAL in categories

    # Verify objective prioritization boost
    tech_q = next(q for q in plan.questions if q.category == ResearchCategory.TECHNOLOGY)
    people_q = next(q for q in plan.questions if q.category == ResearchCategory.PEOPLE)
    assert tech_q.priority >= 0.95
    assert people_q.priority >= 0.95


def test_research_planner_expansion_limits():
    """Verify that expansion questions respect depth and query limits."""
    limits = PlannerLimits(max_depth=2, max_source_queries=5, max_expansions_per_entity=1)
    plan = ResearchPlanner.generate_initial_plan(
        target="Django Software Foundation",
        target_type="organization",
        limits=limits,
    )

    # Lead at max depth should NOT spawn expansion questions
    lead_at_max = EntityExpansionLead(
        entity_name="django/django",
        entity_type="REPOSITORY",
        discovered_via="web_page",
        depth=2,  # equals max_depth
        relevance_score=0.9,
    )
    assert ResearchPlanner.generate_expansion_questions(lead_at_max, plan) == []

    # Lead at depth 1 should spawn expansion question
    lead_at_1 = EntityExpansionLead(
        entity_name="django/django",
        entity_type="REPOSITORY",
        discovered_via="web_page",
        depth=1,
        relevance_score=0.9,
    )
    expanded = ResearchPlanner.generate_expansion_questions(lead_at_1, plan)
    assert len(expanded) == 1
    assert expanded[0].category == ResearchCategory.TECHNOLOGY
    assert "django/django" in expanded[0].question


# ---------------------------------------------------------------------------
# 2. Entity Expander & Relationship Chains Tests
# ---------------------------------------------------------------------------

def test_entity_expander_filters_stop_words_and_ranks():
    """Verify that stop words are ignored and high-relevance entities are prioritized."""
    entities = [
        ExtractedEntity(name="Privacy Policy", entity_type="GENERAL", confidence=1.0),
        ExtractedEntity(name="About Us", entity_type="GENERAL", confidence=1.0),
        ExtractedEntity(name="fastapi/fastapi", entity_type="REPOSITORY", confidence=0.95),
        ExtractedEntity(name="Sebastian Ramirez", entity_type="PERSON", confidence=0.90),
    ]
    relationships = [
        ExtractedRelationship(
            source_entity="FastAPI",
            source_entity_type="PROJECT",
            target_entity="fastapi/fastapi",
            target_entity_type="REPOSITORY",
            relationship_type="maintains_repository",
            confidence=0.95,
        )
    ]

    leads = EntityExpander.evaluate_expansion_leads(
        entities=entities,
        relationships=relationships,
        current_depth=0,
        limits=PlannerLimits(),
        visited={"fastapi"},
    )

    lead_names = [l.entity_name for l in leads]
    assert "Privacy Policy" not in lead_names
    assert "About Us" not in lead_names
    assert "fastapi/fastapi" in lead_names
    assert "Sebastian Ramirez" in lead_names


def test_discover_relationship_chains():
    """Verify multi-hop relationship chain discovery."""
    relationships = [
        TypedRelationship(
            subject="Company A",
            subject_type="COMPANY",
            predicate="develops",
            object="Project B",
            object_type="PROJECT",
            confidence=0.95,
        ),
        TypedRelationship(
            subject="Project B",
            subject_type="PROJECT",
            predicate="uses",
            object="Technology C",
            object_type="TECHNOLOGY",
            confidence=0.90,
        ),
        TypedRelationship(
            subject="Technology C",
            subject_type="TECHNOLOGY",
            predicate="maintained_by",
            object="Org D",
            object_type="ORGANIZATION",
            confidence=0.88,
        ),
    ]

    chains = EntityExpander.discover_relationship_chains(relationships)
    assert len(chains) >= 1
    # First chain should be 3 hops: Company A -> develops -> Project B -> uses -> Technology C -> maintained_by -> Org D
    longest_chain = chains[0]
    assert "Company A" in longest_chain
    assert "Project B" in longest_chain
    assert "Technology C" in longest_chain
    assert "Org D" in longest_chain


# ---------------------------------------------------------------------------
# 3. Corroboration Engine Tests
# ---------------------------------------------------------------------------

def test_corroboration_engine_multi_source_fact():
    """Verify that claims corroborated across 2+ independent sources receive FACT rating."""
    evidence = [
        RawEvidence(
            source_name="trafilatura",
            url="https://psf.org",
            extracted_snippet="The Python Software Foundation is an open-source non-profit.",
        ),
        RawEvidence(
            source_name="wikidata",
            url="https://www.wikidata.org/wiki/Q12345",
            extracted_snippet="Python Software Foundation: Non-profit organization dedicated to Python.",
            metadata={"wikidata_id": "Q12345"},
        ),
    ]
    entities = [
        ExtractedEntity(name="Python Software Foundation", entity_type="ORGANIZATION", confidence=1.0),
        ExtractedEntity(name="psf.org", entity_type="DOMAIN", confidence=1.0),
    ]
    relationships = [
        ExtractedRelationship(
            source_entity="Python Software Foundation",
            source_entity_type="ORGANIZATION",
            target_entity="psf.org",
            target_entity_type="DOMAIN",
            relationship_type="operates",
            confidence=0.99,
        )
    ]

    findings, _rels, _gaps = CorroborationEngine.corroborate(
        target="https://psf.org",
        target_name="Python Software Foundation",
        canonical_domain="psf.org",
        evidence_list=evidence,
        entities=entities,
        relationships=relationships,
        sources_consulted=["trafilatura", "wikidata"],
    )

    assert len(findings) >= 1
    identity_finding = findings[0]
    assert identity_finding.classification == FindingClassification.FACT
    assert identity_finding.confidence_score >= 0.95
    assert identity_finding.is_corroborated is True
    assert "Corroborated across 2 independent sources" in identity_finding.why


def test_corroboration_engine_explicit_research_gaps():
    """Verify that unverified dimensions produce explicit research gaps."""
    _findings, _rels, gaps = CorroborationEngine.corroborate(
        target="https://stealth-startup.io",
        target_name="Stealth Startup",
        canonical_domain="stealth-startup.io",
        evidence_list=[],
        entities=[],
        relationships=[],
        sources_consulted=["trafilatura"],
    )

    # Leadership, SEC filings, and products were absent -> should be recorded as research gaps
    assert any("leadership" in g.lower() for g in gaps)
    assert any("sec edgar" in g.lower() for g in gaps)
    assert any("products" in g.lower() for g in gaps)


# ---------------------------------------------------------------------------
# 4. Multi-Source Orchestrator & Graceful Degradation
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_multi_source_orchestrator_graceful_degradation():
    """Verify orchestrator handles tool failures without crashing."""
    plan = ResearchPlanner.generate_initial_plan("https://failing-target.com", "domain")
    q = plan.questions[0]

    with patch("app.tools.boundary.ToolExecutionBoundary.execute", side_effect=RuntimeError("Network timeout")):
        ev, ents, _rels, _sources = await MultiSourceOrchestrator.execute_question_research(
            question=q,
            scope=ExecutionScope.passive_public(),
            max_source_queries_remaining=5,
        )
        assert ev == []
        assert ents == []
        assert q.status == "unanswerable"


# ---------------------------------------------------------------------------
# 5. Full Service Integration Test with DB
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_intelligence_engine_service_full_workflow(test_db_session: AsyncSession):
    """End-to-end integration test of IntelligenceEngineService."""
    mock_crawled_pages = [
        CrawledPage(
            url="https://nexustech.io",
            status_code=200,
            title="NexusTech Solutions - Enterprise Intelligence",
            description="NexusTech builds autonomous knowledge systems.",
            meta_generator="WordPress 6.4",
            extracted_text="NexusTech Solutions develops NexusBrain. Sarah Connor is the Chief Executive Officer.",
            external_links=["https://github.com/nexustech/nexus-core"],
        )
    ]

    mock_crt_res = SourceResult(
        success=True,
        source_name="crt_sh",
        query="nexustech.io",
        evidence=[RawEvidence(source_name="crt_sh", url="https://crt.sh", extracted_snippet="Cert for api.nexustech.io")],
        entities=[
            ExtractedEntity(name="nexustech.io", entity_type="DOMAIN", confidence=1.0),
            ExtractedEntity(name="api.nexustech.io", entity_type="DOMAIN", confidence=0.95),
        ],
        relationships=[
            ExtractedRelationship(
                source_entity="nexustech.io",
                source_entity_type="DOMAIN",
                target_entity="api.nexustech.io",
                target_entity_type="DOMAIN",
                relationship_type="has_subdomain",
                confidence=0.95,
            )
        ],
    )

    mock_wiki_res = SourceResult(
        success=True,
        source_name="wikidata",
        query="NexusTech Solutions",
        evidence=[RawEvidence(source_name="wikidata", url="https://wikidata.org", extracted_snippet="NexusTech: Software enterprise")],
        entities=[
            ExtractedEntity(
                name="NexusTech Solutions",
                entity_type="COMPANY",
                aliases=["NexusTech", "Nexus Corp"],
                confidence=0.95,
                metadata={"description": "Software enterprise"},
            )
        ],
        relationships=[],
    )

    with (
        patch("app.services.website_intelligence.crawler.WebsiteCrawler.crawl", new_callable=AsyncMock) as mock_crawl,
        patch("app.sources.adapters.crt_sh.CrtShAdapter.search", new_callable=AsyncMock) as mock_crt,
        patch("app.sources.adapters.wikidata.WikidataAdapter.search", new_callable=AsyncMock) as mock_wiki,
    ):
        mock_crawl.return_value = mock_crawled_pages
        mock_crt.return_value = mock_crt_res
        mock_wiki.return_value = mock_wiki_res

        req = IntelligenceInvestigationRequest(
            target="https://nexustech.io",
            target_type="domain",
            objective="Comprehensive intelligence investigation",
            max_depth=2,
            max_source_queries=10,
            allow_expansion=True,
        )

        response = await IntelligenceEngineService.investigate(
            request=req,
            db=test_db_session,
        )

        assert response.status == "completed"
        assert response.canonical_domain == "nexustech.io"
        assert response.findings_count >= 3
        assert response.report is not None
        assert "NexusTech Solutions" in response.report.target_profile["name"]
        assert len(response.report.technology_intelligence) >= 1

        # Check DB records
        inv_stmt = select(Investigation).where(Investigation.id == response.investigation_id)
        db_inv = (await test_db_session.execute(inv_stmt)).scalar_one_or_none()
        assert db_inv is not None
        assert db_inv.status == "completed"

        task_stmt = select(InvestigationTask).where(InvestigationTask.investigation_id == response.investigation_id)
        db_tasks = (await test_db_session.execute(task_stmt)).scalars().all()
        assert len(db_tasks) >= 2

        finding_stmt = select(Finding).where(Finding.investigation_id == response.investigation_id)
        db_findings = (await test_db_session.execute(finding_stmt)).scalars().all()
        assert len(db_findings) >= 3

        agent_stmt = select(AgentRun).where(AgentRun.investigation_id == response.investigation_id)
        db_agent = (await test_db_session.execute(agent_stmt)).scalar_one_or_none()
        assert db_agent is not None
        assert db_agent.agent_role == "NEXUS-Intelligence-Engine-1.0"


# ---------------------------------------------------------------------------
# 6. REST API Endpoint Test
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_intelligence_engine_api_endpoint(async_client: AsyncClient, test_db_session: AsyncSession):
    """Verify POST /api/v1/investigations/intelligence endpoint."""
    mock_crawled_pages = [
        CrawledPage(
            url="https://nexustech.io",
            status_code=200,
            title="NexusTech Solutions",
            description="Autonomous intelligence.",
            extracted_text="NexusTech Solutions develops NexusBrain.",
        )
    ]

    with patch("app.services.website_intelligence.crawler.WebsiteCrawler.crawl", new_callable=AsyncMock) as mock_crawl:
        mock_crawl.return_value = mock_crawled_pages

        resp = await async_client.post(
            "/api/v1/investigations/intelligence",
            json={
                "target": "https://nexustech.io",
                "target_type": "domain",
                "max_depth": 1,
                "max_source_queries": 5,
                "allow_expansion": False,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "completed"
        assert data["canonical_domain"] == "nexustech.io"
        assert "report" in data
        assert "executive_intelligence" in data["report"]


# ---------------------------------------------------------------------------
# 7. SSRF and Validation Guardrail Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_intelligence_engine_ssrf_protection():
    """Verify SSRF and loopback targets are rejected by intelligence service."""
    # Private IP
    with pytest.raises(ValueError, match="SSRF"):
        await IntelligenceEngineService.investigate(
            IntelligenceInvestigationRequest(target="http://192.168.1.10", target_type="domain")
        )

    # Localhost
    with pytest.raises(ValueError, match="SSRF"):
        await IntelligenceEngineService.investigate(
            IntelligenceInvestigationRequest(target="http://localhost:8000", target_type="domain")
        )
