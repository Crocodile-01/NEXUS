from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.evidence import Evidence
from app.models.investigation import Investigation
from app.models.task import InvestigationTask
from app.models.tool_execution import ToolExecution
from app.security.execution_scope import ExecutionScope
from app.sources.base import ExtractedEntity, RawEvidence, SourceResult
from app.tools.base import RegisteredTool, ToolRequest, ToolResult
from app.tools.boundary import ToolExecutionBoundary
from app.tools.registry import tool_registry


@pytest.mark.asyncio
async def test_tool_boundary_successful_execution(test_db_session: AsyncSession):
    # Setup test investigation and task
    inv = Investigation(target="nvidia.com", target_type="domain", status="created")
    test_db_session.add(inv)
    await test_db_session.commit()
    await test_db_session.refresh(inv)

    task = InvestigationTask(
        investigation_id=inv.id,
        name="Test Task",
        task_type="recon",
        status="pending",
    )
    test_db_session.add(task)
    await test_db_session.commit()
    await test_db_session.refresh(task)

    # Mock CrtShAdapter response
    mock_result = SourceResult(
        success=True,
        source_name="crt_sh",
        query="nvidia.com",
        evidence=[
            RawEvidence(
                source_name="crt_sh",
                url="https://crt.sh/?q=nvidia.com",
                extracted_snippet="Found subdomain api.nvidia.com",
            )
        ],
        entities=[
            ExtractedEntity(name="api.nvidia.com", entity_type="DOMAIN"),
        ],
    )

    with patch("app.sources.adapters.crt_sh.CrtShAdapter.search", new_callable=AsyncMock) as mock_search:
        mock_search.return_value = mock_result

        req = ToolRequest(target="nvidia.com", target_type="domain")
        result = await ToolExecutionBoundary.execute(
            tool_name="lookup_certificate_transparency",
            request=req,
            scope=ExecutionScope.passive_public(),
            db=test_db_session,
            task_id=task.id,
        )

        assert result.success is True
        assert result.tool_name == "lookup_certificate_transparency"
        assert result.execution_time_ms >= 0

        # Verify ToolExecution record was persisted
        stmt = select(ToolExecution).where(ToolExecution.task_id == task.id)
        db_exec = (await test_db_session.execute(stmt)).scalar_one_or_none()
        assert db_exec is not None
        assert db_exec.tool_name == "lookup_certificate_transparency"
        assert db_exec.status == "success"

        # Verify Evidence record was persisted
        ev_stmt = select(Evidence)
        db_evidence = (await test_db_session.execute(ev_stmt)).scalars().all()
        assert len(db_evidence) == 1
        assert "api.nvidia.com" in db_evidence[0].extracted_snippet


@pytest.mark.asyncio
async def test_tool_boundary_timeout_handling():
    async def slow_func(request: ToolRequest) -> ToolResult:
        await asyncio.sleep(0.5)
        return ToolResult(success=True, tool_name="slow_tool", target=request.target)

    slow_tool = RegisteredTool(
        name="slow_tool",
        description="Slow test tool",
        category="test",
        func=slow_func,
        timeout=1,  # 1 second timeout
    )
    # Register temporarily
    tool_registry.register(slow_tool)

    try:
        # Patch timeout to tiny value
        slow_tool.timeout = 0  # Should timeout immediately
        req = ToolRequest(target="example.com", target_type="domain")
        res = await ToolExecutionBoundary.execute(
            tool_name="slow_tool",
            request=req,
            scope=ExecutionScope.passive_public(),
        )
        assert res.success is False
        assert "timed out" in res.error_message
    finally:
        tool_registry.unregister("slow_tool")


@pytest.mark.asyncio
async def test_tool_boundary_failure_handling(test_db_session: AsyncSession):
    async def failing_func(request: ToolRequest) -> ToolResult:
        raise RuntimeError("Service temporarily unavailable")

    failing_tool = RegisteredTool(
        name="failing_tool",
        description="Failing test tool",
        category="test",
        func=failing_func,
    )
    tool_registry.register(failing_tool)

    try:
        req = ToolRequest(target="example.com", target_type="domain")
        res = await ToolExecutionBoundary.execute(
            tool_name="failing_tool",
            request=req,
            scope=ExecutionScope.passive_public(),
            db=test_db_session,
        )
        assert res.success is False
        assert "Service temporarily unavailable" in res.error_message

        # Verify audit record persisted as failed
        stmt = select(ToolExecution).where(ToolExecution.tool_name == "failing_tool")
        db_exec = (await test_db_session.execute(stmt)).scalar_one_or_none()
        assert db_exec is not None
        assert db_exec.status == "failed"
    finally:
        tool_registry.unregister("failing_tool")


@pytest.mark.asyncio
async def test_tool_boundary_blocks_guardrail_violation(test_db_session: AsyncSession):
    # Attempting to query private IP
    req = ToolRequest(target="127.0.0.1", target_type="ip")
    res = await ToolExecutionBoundary.execute(
        tool_name="lookup_certificate_transparency",
        request=req,
        scope=ExecutionScope.passive_public(),
        db=test_db_session,
    )
    assert res.success is False
    assert "Guardrail violation" in res.error_message

    # Verify audit log captured the guardrail block
    stmt = select(ToolExecution).where(ToolExecution.status == "blocked_by_guardrail")
    db_exec = (await test_db_session.execute(stmt)).scalar_one_or_none()
    assert db_exec is not None
