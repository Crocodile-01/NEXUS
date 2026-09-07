from __future__ import annotations

import asyncio
import logging
import time
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.guardrails.tool_guardrails import GuardrailViolationError, validate_tool_call
from app.models.tool_execution import ToolExecution
from app.security.execution_scope import DEFAULT_SCOPE, ExecutionScope
from app.services.evidence_engine import persist_source_result
from app.tools.base import RegisteredTool, ToolRequest, ToolResult
from app.tools.registry import tool_registry

logger = logging.getLogger(__name__)


class ToolExecutionBoundary:
    """
    Centralized execution boundary for all NEXUS tool invocations.

    Guarantees that no tool execution can bypass:
      - Tool enablement checks
      - Guardrails (target validation, SSRF checks, private IP rejections)
      - ExecutionScope & authorization verification
      - Strict timeouts
      - Evidence persistence & deduplication
      - Audit logging in tool_executions database table
    """

    @classmethod
    async def execute(
        cls,
        tool_name: str,
        request: ToolRequest,
        scope: ExecutionScope = DEFAULT_SCOPE,
        db: AsyncSession | None = None,
        task_id: str | None = None,
    ) -> ToolResult:
        """
        Execute a registered tool through the centralized security boundary.
        """
        start_time = time.perf_counter()

        # 1. Tool Lookup
        tool: RegisteredTool | None = tool_registry.get(tool_name)
        if not tool:
            err_msg = f"Tool '{tool_name}' not found in registry."
            logger.warning(err_msg)
            return ToolResult(
                success=False,
                tool_name=tool_name,
                target=request.target,
                error_message=err_msg,
                execution_time_ms=0,
            )

        if not tool.enabled:
            err_msg = f"Tool '{tool_name}' is currently disabled."
            logger.warning(err_msg)
            return ToolResult(
                success=False,
                tool_name=tool_name,
                target=request.target,
                error_message=err_msg,
                execution_time_ms=0,
            )

        # 2. Guardrail & Policy Check
        try:
            validate_tool_call(tool=tool, request=request, scope=scope)
        except GuardrailViolationError as gve:
            elapsed_ms = int((time.perf_counter() - start_time) * 1000)
            err_msg = f"Guardrail violation: {gve}"
            logger.warning("Tool '%s' blocked by guardrail: %s", tool_name, gve)

            # Persist failed tool execution audit record if DB session is available
            if db:
                await cls._persist_audit_log(
                    db=db,
                    task_id=task_id,
                    tool_name=tool_name,
                    execution_mode=scope.mode,
                    input_params=request.model_dump(),
                    output_result={"error": err_msg},
                    status="blocked_by_guardrail",
                    execution_time_ms=elapsed_ms,
                )

            return ToolResult(
                success=False,
                tool_name=tool_name,
                target=request.target,
                error_message=err_msg,
                execution_time_ms=elapsed_ms,
            )

        # 3. Execution with Timeout
        try:
            result = await asyncio.wait_for(
                tool.func(request),
                timeout=tool.timeout,
            )
            elapsed_ms = int((time.perf_counter() - start_time) * 1000)
            result.execution_time_ms = elapsed_ms
        except TimeoutError:
            elapsed_ms = int((time.perf_counter() - start_time) * 1000)
            err_msg = f"Tool '{tool_name}' timed out after {tool.timeout}s."
            logger.error(err_msg)
            result = ToolResult(
                success=False,
                tool_name=tool_name,
                target=request.target,
                error_message=err_msg,
                execution_time_ms=elapsed_ms,
            )
        except Exception as exc:
            elapsed_ms = int((time.perf_counter() - start_time) * 1000)
            err_msg = f"Tool '{tool_name}' execution error: {exc}"
            logger.exception(err_msg)
            result = ToolResult(
                success=False,
                tool_name=tool_name,
                target=request.target,
                error_message=err_msg,
                execution_time_ms=elapsed_ms,
            )

        # 4. Evidence Persistence
        if db and result.source_result and result.source_result.success:
            try:
                await persist_source_result(db=db, result=result.source_result)
            except Exception as e:  # noqa: BLE001
                logger.error("Failed persisting evidence for tool '%s': %s", tool_name, e)

        # 5. ToolExecution DB Logging
        if db:
            await cls._persist_audit_log(
                db=db,
                task_id=task_id,
                tool_name=tool_name,
                execution_mode=scope.mode,
                input_params=request.model_dump(),
                output_result=result.output_data or {"success": result.success, "error": result.error_message},
                status="success" if result.success else "failed",
                execution_time_ms=result.execution_time_ms,
            )

        return result

    @staticmethod
    async def _persist_audit_log(
        db: AsyncSession,
        task_id: str | None,
        tool_name: str,
        execution_mode: str,
        input_params: dict,
        output_result: dict,
        status: str,
        execution_time_ms: int,
    ) -> None:
        """Record tool execution audit record in database."""
        try:
            tool_exec = ToolExecution(
                task_id=task_id,
                tool_name=tool_name,
                execution_mode=execution_mode,
                input_params=input_params,
                output_result=output_result,
                status=status,
                execution_time_ms=execution_time_ms,
                executed_at=datetime.now(UTC),
            )
            db.add(tool_exec)
            await db.commit()
        except Exception as e:  # noqa: BLE001
            logger.error("Failed recording tool_execution audit log: %s", e)
