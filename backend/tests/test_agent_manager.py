from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.manager import InvestigationManager
from app.agents.schemas import FindingClassification
from app.models.agent_run import AgentRun
from app.models.finding import Finding
from app.models.investigation import Investigation
from app.models.task import InvestigationTask
from app.security.execution_scope import ExecutionScope
from app.sources.base import (
    ExtractedEntity,
    ExtractedRelationship,
    RawEvidence,
    SourceResult,
)


@pytest.mark.asyncio
async def test_manager_run_step_success(test_db_session: AsyncSession):
    # Create investigation and task
    inv = Investigation(
        target="Wikidata Corp",
        target_type="company",
        objective="Research corporate profile",
        status="created",
    )
    test_db_session.add(inv)
    await test_db_session.commit()
    await test_db_session.refresh(inv)

    task = InvestigationTask(
        investigation_id=inv.id,
        name="Initial classification",
        task_type="company",
        status="pending",
    )
    test_db_session.add(task)
    await test_db_session.commit()
    await test_db_session.refresh(task)

    mock_wikidata_result = SourceResult(
        success=True,
        source_name="wikidata",
        query="Wikidata Corp",
        evidence=[
            RawEvidence(
                source_name="wikidata",
                url="https://www.wikidata.org/wiki/Q12345",
                extracted_snippet="Wikidata Corp is a multinational technology enterprise.",
            )
        ],
        entities=[
            ExtractedEntity(name="Wikidata Corp", entity_type="COMPANY", confidence=1.0),
            ExtractedEntity(name="Jane Doe", entity_type="PERSON", confidence=0.8),
        ],
        relationships=[
            ExtractedRelationship(
                source_entity="Jane Doe",
                source_entity_type="PERSON",
                target_entity="Wikidata Corp",
                target_entity_type="COMPANY",
                relationship_type="ceo_of",
                confidence=0.9,
            )
        ],
    )

    with patch("app.sources.adapters.wikidata.WikidataAdapter.search", new_callable=AsyncMock) as mock_search:
        mock_search.return_value = mock_wikidata_result

        result = await InvestigationManager.run_step(
            investigation_id=inv.id,
            target=inv.target,
            target_type=inv.target_type,
            objective=inv.objective,
            scope=ExecutionScope.passive_public(),
            db=test_db_session,
            task_id=task.id,
        )

        assert result.status == "completed"
        assert result.investigation_id == inv.id
        assert len(result.findings) >= 3

        # Verify classifications: FACT, SUPPORTED_INFERENCE
        classifications = [f.classification for f in result.findings]
        assert FindingClassification.FACT in classifications
        assert FindingClassification.SUPPORTED_INFERENCE in classifications

        # Verify DB records
        ar_stmt = select(AgentRun).where(AgentRun.investigation_id == inv.id)
        db_agent_run = (await test_db_session.execute(ar_stmt)).scalar_one_or_none()
        assert db_agent_run is not None
        assert db_agent_run.agent_role == "InvestigationManager"

        findings_stmt = select(Finding).where(Finding.investigation_id == inv.id)
        db_findings = (await test_db_session.execute(findings_stmt)).scalars().all()
        assert len(db_findings) >= 3

        # Task should be marked completed
        task_stmt = select(InvestigationTask).where(InvestigationTask.id == task.id)
        updated_task = (await test_db_session.execute(task_stmt)).scalar_one()
        assert updated_task.status == "completed"


@pytest.mark.asyncio
async def test_manager_run_step_unverified_fallback(test_db_session: AsyncSession):
    inv = Investigation(target="Unknown Corp", target_type="company", status="created")
    test_db_session.add(inv)
    await test_db_session.commit()
    await test_db_session.refresh(inv)

    mock_failed_result = SourceResult(
        success=False,
        source_name="wikidata",
        query="Unknown Corp",
        error_message="No matching Wikidata entity found",
    )

    with patch("app.sources.adapters.wikidata.WikidataAdapter.search", new_callable=AsyncMock) as mock_search:
        mock_search.return_value = mock_failed_result

        result = await InvestigationManager.run_step(
            investigation_id=inv.id,
            target=inv.target,
            target_type=inv.target_type,
            scope=ExecutionScope.passive_public(),
            db=test_db_session,
        )

        assert result.status == "failed"
        assert len(result.findings) == 1
        assert result.findings[0].classification == FindingClassification.UNVERIFIED


@pytest.mark.asyncio
async def test_manager_sdk_agent_build():
    """Verify that OpenAI Agents SDK Agent builds successfully with all registered tools."""
    agent = InvestigationManager.build_sdk_agent(
        scope=ExecutionScope.passive_public(),
        model_name="gpt-4o-mini",
    )
    assert agent.name == "NEXUS_Investigation_Manager"
    assert len(agent.tools) >= 6
    tool_names = [t.name for t in agent.tools]
    assert "search_wikidata" in tool_names
    assert "lookup_certificate_transparency" in tool_names


@pytest.mark.asyncio
async def test_investigation_execute_endpoint(async_client: AsyncClient, test_db_session: AsyncSession):
    """End-to-end test of POST /investigations with execute=true query parameter."""
    mock_wikidata_result = SourceResult(
        success=True,
        source_name="wikidata",
        query="NVIDIA",
        evidence=[
            RawEvidence(
                source_name="wikidata",
                url="https://www.wikidata.org/wiki/Q182477",
                extracted_snippet="Nvidia is an American technology company.",
            )
        ],
        entities=[
            ExtractedEntity(name="NVIDIA", entity_type="COMPANY"),
        ],
    )

    with patch("app.sources.adapters.wikidata.WikidataAdapter.search", new_callable=AsyncMock) as mock_search:
        mock_search.return_value = mock_wikidata_result

        # 1. Create with execute=true
        resp = await async_client.post(
            "/api/v1/investigations?execute=true",
            json={
                "target": "NVIDIA",
                "target_type": "company",
                "objective": "Identify technology focus",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        inv_id = data["id"]
        assert len(data["tasks"]) == 1

        # Verify task is completed
        assert data["tasks"][0]["status"] == "completed"

        # 2. Test explicit execute endpoint POST /investigations/{id}/execute
        exec_resp = await async_client.post(f"/api/v1/investigations/{inv_id}/execute")
        assert exec_resp.status_code == 200
        exec_data = exec_resp.json()
        assert exec_data["status"] == "completed"
        assert len(exec_data["findings"]) >= 1
        assert exec_data["findings"][0]["classification"] == "FACT"
