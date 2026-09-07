from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent_run import AgentRun
from app.models.finding import Finding
from app.models.investigation import Investigation
from app.models.task import InvestigationTask
from app.services.website_intelligence.crawler import CrawledPage, WebsiteCrawler
from app.services.website_intelligence.extractor import WebsiteEntityExtractor
from app.services.website_intelligence.schemas import TechClassification
from app.services.website_intelligence.service import WebsiteIntelligenceService
from app.services.website_intelligence.tech_detector import TechDetector
from app.sources.base import (
    ExtractedEntity,
    SourceResult,
)

HTML_SAMPLE_HOMEPAGE = """
<!DOCTYPE html>
<html>
<head>
    <title>NexusTech Solutions - Enterprise Intelligence Platform</title>
    <meta name="description" content="NexusTech delivers cutting-edge autonomous intelligence solutions for enterprise teams.">
    <meta name="generator" content="WordPress 6.4">
    <script src="/_next/static/chunks/main.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/react/18.2.0/react.production.min.js"></script>
</head>
<body>
    <h1>Empowering Global Decisions</h1>
    <p>NexusTech Solutions develops NexusBrain, our flagship autonomous platform. Built with Python and PyTorch.</p>
    <p>Sarah Connor is the Chief Executive Officer leading our strategic mission.</p>
    <a href="/about">About NexusTech</a>
    <a href="/products">Our Enterprise Products</a>
    <a href="https://github.com/nexustech/nexus-core">Open Source Repository</a>
    <footer>
        <p>© 2021-2026 NexusTech Solutions. All rights reserved.</p>
    </footer>
</body>
</html>
"""

HTML_SAMPLE_ABOUT = """
<!DOCTYPE html>
<html>
<head>
    <title>About NexusTech - Leadership</title>
</head>
<body>
    <h1>About Our Team</h1>
    <p>Founded in 2021, NexusTech has grown to support global operations.</p>
    <p>John Matrix is the Chief Technology Officer overseeing engineering architecture.</p>
</body>
</html>
"""


@pytest.mark.asyncio
async def test_crawler_bounded_and_prioritized():
    """Verify that crawler extracts homepage and follows prioritized internal links up to max_pages."""
    crawler = WebsiteCrawler(timeout_seconds=5)

    async def mock_fetch_page(url: str) -> CrawledPage | None:
        if "about" in url:
            return CrawledPage(
                url=url,
                status_code=200,
                title="About NexusTech",
                description="About page",
                extracted_text="Founded in 2021. John Matrix is the Chief Technology Officer.",
            )
        return CrawledPage(
            url=url,
            status_code=200,
            title="NexusTech Solutions",
            description="Autonomous intelligence solutions.",
            meta_generator="WordPress 6.4",
            extracted_text="NexusTech Solutions develops NexusBrain. Sarah Connor is the Chief Executive Officer.",
            script_srcs=["/_next/static/chunks/main.js"],
            internal_links=["https://nexustech.io/about", "https://nexustech.io/products"],
            external_links=["https://github.com/nexustech/nexus-core"],
        )

    with patch.object(crawler, "_fetch_page", side_effect=mock_fetch_page):
        pages = await crawler.crawl("https://nexustech.io", max_pages=2)
        assert len(pages) == 2
        assert pages[0].url == "https://nexustech.io"
        assert pages[1].url == "https://nexustech.io/about"


def test_tech_detector_classifications():
    """Verify passive technology detection covering DETECTED, EXPLICIT, and INFERRED."""
    page = CrawledPage(
        url="https://nexustech.io",
        status_code=200,
        title="NexusTech",
        meta_generator="WordPress 6.4",
        extracted_text="Our platform is built with Python and utilizes PyTorch for inference.",
        headers={"server": "cloudflare", "x-powered-by": "Express"},
        script_srcs=["/_next/static/chunks/main.js", "/static/js/react.js"],
        raw_html="<div id='__next'></div><div class='wp-content'></div>",
    )

    technologies = TechDetector.detect_technologies([page])
    tech_names = {t.name for t in technologies}

    # DETECTED from generator / scripts / headers
    assert "WordPress" in tech_names
    assert "Next.js" in tech_names
    assert "Cloudflare" in tech_names
    assert "Express.js" in tech_names

    # EXPLICIT from text
    assert "Python" in tech_names
    assert "PyTorch" in tech_names
    python_tech = next(t for t in technologies if t.name == "Python")
    assert python_tech.classification == TechClassification.EXPLICIT

    # INFERRED from WordPress (implies PHP) or Next.js (implies React)
    assert "PHP" in tech_names or "React" in tech_names


def test_entity_and_relationship_extractor():
    """Verify entity, product, repository, and relationship extraction."""
    page = CrawledPage(
        url="https://nexustech.io",
        status_code=200,
        title="NexusTech Solutions - Enterprise Intelligence",
        description="Autonomous intelligence solutions.",
        extracted_text="NexusTech Solutions develops NexusBrain, our flagship autonomous platform. Sarah Connor is the Chief Executive Officer.",
        external_links=["https://github.com/nexustech/nexus-core"],
    )

    org_profile = WebsiteEntityExtractor.extract_organization_profile([page], "https://nexustech.io")
    assert org_profile.name == "NexusTech Solutions"
    assert org_profile.canonical_domain == "nexustech.io"

    entities, products, relationships = WebsiteEntityExtractor.extract_entities_and_relationships([page], org_profile)
    assert any(p.name == "NexusBrain" for p in products)
    entity_names = {e.name for e in entities}
    assert "NexusTech Solutions" in entity_names
    assert "nexustech.io" in entity_names
    assert "Sarah Connor" in entity_names
    assert "NexusBrain" in entity_names
    assert "nexustech/nexus-core" in entity_names

    rel_types = {r.relationship_type for r in relationships}
    assert "operates" in rel_types
    assert "employs" in rel_types
    assert "develops" in rel_types
    assert "maintains_repository" in rel_types


@pytest.mark.asyncio
async def test_website_intelligence_e2e_mocked(test_db_session: AsyncSession):
    """End-to-end test of the entire website intelligence pipeline with persistence."""
    # 1. Mock Crawler
    mock_crawled_pages = [
        CrawledPage(
            url="https://nexustech.io",
            status_code=200,
            title="NexusTech Solutions",
            description="Autonomous intelligence solutions.",
            extracted_text="NexusTech Solutions develops NexusBrain. Sarah Connor is the Chief Executive Officer.",
            headers={"server": "nginx"},
            script_srcs=["/static/js/vue.js"],
            external_links=["https://github.com/nexustech/nexus-core"],
        )
    ]

    # 2. Mock crt.sh
    mock_crt_res = SourceResult(
        success=True,
        source_name="crt_sh",
        query="nexustech.io",
        entities=[
            ExtractedEntity(name="api.nexustech.io", entity_type="DOMAIN"),
            ExtractedEntity(name="vpn.nexustech.io", entity_type="DOMAIN"),
        ],
    )

    # 3. Mock Wikidata
    mock_wiki_res = SourceResult(
        success=True,
        source_name="wikidata",
        query="NexusTech Solutions",
        entities=[
            ExtractedEntity(
                name="NexusTech Solutions",
                entity_type="COMPANY",
                aliases=["NexusTech Inc."],
                metadata={"description": "Global enterprise software provider"},
            )
        ],
    )

    with (
        patch("app.services.website_intelligence.crawler.WebsiteCrawler.crawl", new_callable=AsyncMock) as mock_crawl,
        patch("app.sources.adapters.crt_sh.CrtShAdapter.search", new_callable=AsyncMock) as mock_crt,
        patch("app.sources.adapters.wikidata.WikidataAdapter.search", new_callable=AsyncMock) as mock_wiki,
    ):
        mock_crawl.return_value = mock_crawled_pages
        mock_crt.return_value = mock_crt_res
        mock_wiki.return_value = mock_wiki_res

        response = await WebsiteIntelligenceService.investigate_website(
            target="https://nexustech.io",
            objective="Comprehensive reconnaissance",
            max_pages=2,
            enrich=True,
            db=test_db_session,
        )

        assert response.status == "completed"
        assert response.canonical_domain == "nexustech.io"
        assert response.report is not None
        assert response.report.organization_profile.name == "NexusTech Solutions"
        assert len(response.report.findings) >= 3
        assert response.report.average_confidence > 0.8
        assert "Passive reconnaissance" in response.report.executive_summary

        # Verify DB records
        inv_stmt = select(Investigation).where(Investigation.id == response.investigation_id)
        db_inv = (await test_db_session.execute(inv_stmt)).scalar_one_or_none()
        assert db_inv is not None
        assert db_inv.status == "completed"

        task_stmt = select(InvestigationTask).where(InvestigationTask.investigation_id == response.investigation_id)
        db_tasks = (await test_db_session.execute(task_stmt)).scalars().all()
        assert len(db_tasks) >= 2
        assert all(t.status == "completed" for t in db_tasks)

        findings_stmt = select(Finding).where(Finding.investigation_id == response.investigation_id)
        db_findings = (await test_db_session.execute(findings_stmt)).scalars().all()
        assert len(db_findings) >= 3

        ar_stmt = select(AgentRun).where(AgentRun.investigation_id == response.investigation_id)
        db_ar = (await test_db_session.execute(ar_stmt)).scalar_one_or_none()
        assert db_ar is not None
        assert db_ar.agent_role == "WebsiteResearchManager"


@pytest.mark.asyncio
async def test_website_intelligence_api_endpoint(async_client: AsyncClient, test_db_session: AsyncSession):
    """Test POST /api/v1/investigations/website endpoint."""
    mock_crawled_pages = [
        CrawledPage(
            url="https://nexustech.io",
            status_code=200,
            title="NexusTech Solutions",
            description="Autonomous intelligence solutions.",
            extracted_text="NexusTech Solutions develops NexusBrain.",
        )
    ]

    with patch("app.services.website_intelligence.crawler.WebsiteCrawler.crawl", new_callable=AsyncMock) as mock_crawl:
        mock_crawl.return_value = mock_crawled_pages

        resp = await async_client.post(
            "/api/v1/investigations/website",
            json={
                "target": "https://nexustech.io",
                "max_pages": 1,
                "enrich": False,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "completed"
        assert data["canonical_domain"] == "nexustech.io"
        assert "NexusTech Solutions" in data["report"]["organization_profile"]["name"]


@pytest.mark.asyncio
async def test_negative_target_validation_and_ssrf():
    """Negative tests: loopback, private IP, and invalid domains must be rejected immediately."""
    # Loopback IP URL
    with pytest.raises(ValueError, match="security / SSRF validation"):
        await WebsiteIntelligenceService.investigate_website("http://127.0.0.1:8080")

    # Private RFC 1918 URL
    with pytest.raises(ValueError, match="security / SSRF validation"):
        await WebsiteIntelligenceService.investigate_website("http://192.168.1.50/admin")

    # Localhost
    with pytest.raises(ValueError, match="security / SSRF validation"):
        await WebsiteIntelligenceService.investigate_website("http://localhost:3000")

    # Invalid FQDN domain
    with pytest.raises(ValueError, match="validation"):
        await WebsiteIntelligenceService.investigate_website("invalid_domain!@#")


@pytest.mark.asyncio
async def test_negative_unreachable_target(test_db_session: AsyncSession):
    """When a website is completely unreachable, the service returns a graceful failed report."""
    with patch("app.services.website_intelligence.crawler.WebsiteCrawler.crawl", new_callable=AsyncMock) as mock_crawl:
        mock_crawl.return_value = []  # Unreachable / empty

        response = await WebsiteIntelligenceService.investigate_website(
            target="https://unreachable-site.com",
            db=test_db_session,
        )
        assert response.status == "failed"
        assert len(response.report.research_gaps) >= 1
        assert "unreachable" in response.report.research_gaps[0].lower()


@pytest.mark.asyncio
async def test_enrichment_failure_graceful_degradation(test_db_session: AsyncSession):
    """When external enrichment sources fail, the investigation degrades gracefully and returns crawl results."""
    mock_crawled_pages = [
        CrawledPage(
            url="https://resilient.com",
            status_code=200,
            title="Resilient Systems",
            extracted_text="Resilient Systems produces security tools.",
        )
    ]

    with (
        patch("app.services.website_intelligence.crawler.WebsiteCrawler.crawl", new_callable=AsyncMock) as mock_crawl,
        patch("app.sources.adapters.crt_sh.CrtShAdapter.search", side_effect=RuntimeError("crt.sh timeout")),
        patch("app.sources.adapters.wikidata.WikidataAdapter.search", side_effect=RuntimeError("Wikidata unavailable")),
    ):
        mock_crawl.return_value = mock_crawled_pages

        response = await WebsiteIntelligenceService.investigate_website(
            target="https://resilient.com",
            enrich=True,
            db=test_db_session,
        )
        assert response.status == "completed"
        assert response.report.organization_profile.name == "Resilient Systems"
        assert len(response.report.findings) >= 1
