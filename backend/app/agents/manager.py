from __future__ import annotations

import json
import logging
import time
from datetime import UTC, datetime

from agents import Agent, function_tool
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.schemas import AgentFinding, AgentRunResult, FindingClassification
from app.models.agent_run import AgentRun
from app.models.finding import Finding
from app.models.investigation import Investigation
from app.models.task import InvestigationTask
from app.security.execution_scope import DEFAULT_SCOPE, ExecutionScope
from app.tools.base import RegisteredTool, ToolRequest, ToolResult
from app.tools.boundary import ToolExecutionBoundary
from app.tools.registry import tool_registry

logger = logging.getLogger(__name__)


def create_sdk_tool_for_registered_tool(
    tool: RegisteredTool,
    scope: ExecutionScope,
    db: AsyncSession | None = None,
    task_id: str | None = None,
):
    """
    Wrap a NEXUS RegisteredTool into an OpenAI Agents SDK function_tool.
    Guarantees that when the agent invokes the tool, execution routes
    exclusively through ToolExecutionBoundary.
    """

    async def _tool_callable(target: str, target_type: str = "general", limit: int = 10) -> str:
        req = ToolRequest(target=target, target_type=target_type, limit=limit)
        res = await ToolExecutionBoundary.execute(
            tool_name=tool.name,
            request=req,
            scope=scope,
            db=db,
            task_id=task_id,
        )
        if not res.success:
            return f"Error executing {tool.name}: {res.error_message}"
        return json.dumps(res.output_data)

    return function_tool(
        func=_tool_callable,
        name_override=tool.name,
        description_override=tool.description,
    )


class InvestigationManager:
    """
    Manager Agent coordinating investigation execution.
    Controls tool selection, enforces guardrails through ToolExecutionBoundary,
    and returns verified, structured findings.
    """

    @classmethod
    def build_sdk_agent(
        cls,
        scope: ExecutionScope = DEFAULT_SCOPE,
        db: AsyncSession | None = None,
        task_id: str | None = None,
        model_name: str = "gpt-4o-mini",
    ) -> Agent:
        """
        Construct an OpenAI Agents SDK Agent populated with all enabled
        NEXUS registered tools routed through the security boundary.
        """
        registered_tools = tool_registry.list_tools(enabled_only=True)
        sdk_tools = [
            create_sdk_tool_for_registered_tool(tool=t, scope=scope, db=db, task_id=task_id)
            for t in registered_tools
        ]

        instructions = (
            "You are the NEXUS Autonomous Investigation Manager.\n"
            "Your objective is to coordinate public, evidence-based research on targets.\n"
            "Rules:\n"
            "1. You must only gather information through provided registered tools.\n"
            "2. Never assert speculation as verified facts.\n"
            "3. Distinguish FACT (backed directly by evidence), SUPPORTED_INFERENCE "
            "(deductions logically following from facts), and UNVERIFIED (leads/claims needing corroboration).\n"
            "4. Adhere strictly to the active execution scope."
        )

        return Agent(
            name="NEXUS_Investigation_Manager",
            instructions=instructions,
            tools=sdk_tools,
            model=model_name,
        )

    @classmethod
    def select_appropriate_tool(cls, target_type: str) -> str:
        """
        Deterministic tool selection heuristic mapping target types to primary source tools.
        """
        target_type_clean = target_type.strip().lower()
        if target_type_clean == "domain":
            return "lookup_certificate_transparency"
        elif target_type_clean in ("company", "organization"):
            return "search_wikidata"
        elif target_type_clean in ("technology", "project", "academic_query"):
            return "search_arxiv"
        elif target_type_clean == "url":
            return "fetch_webpage"
        elif target_type_clean in ("person", "username"):
            return "search_wikidata"
        return "search_wikidata"

    @classmethod
    async def run_step(
        cls,
        investigation_id: str,
        target: str,
        target_type: str,
        objective: str = "",
        scope: ExecutionScope = DEFAULT_SCOPE,
        db: AsyncSession | None = None,
        task_id: str | None = None,
        model_name: str = "gpt-4o-mini",
    ) -> AgentRunResult:
        """
        Execute an investigation step: select tool, invoke through ToolExecutionBoundary,
        extract structured findings (FACT / SUPPORTED_INFERENCE / UNVERIFIED),
        and persist AgentRun + Findings if db session is provided.
        """
        start_time = time.perf_counter()
        tools_executed: list[str] = []
        findings: list[AgentFinding] = []

        # 1. Select tool appropriate for target_type
        tool_name = cls.select_appropriate_tool(target_type)
        tools_executed.append(tool_name)

        # 2. Execute tool through boundary
        req = ToolRequest(target=target, target_type=target_type, limit=10)
        tool_result: ToolResult = await ToolExecutionBoundary.execute(
            tool_name=tool_name,
            request=req,
            scope=scope,
            db=db,
            task_id=task_id,
        )

        # 3. Formulate structured findings
        if tool_result.success and tool_result.source_result:
            s_res = tool_result.source_result

            # Extract facts directly supported by evidence
            for ev in s_res.evidence:
                snippet = ev.extracted_snippet
                findings.append(
                    AgentFinding(
                        claim=f"Discovered evidence for '{target}' via {s_res.source_name}: {snippet[:200]}",
                        classification=FindingClassification.FACT,
                        confidence_score=0.95,
                        source_url=ev.url,
                        supporting_snippet=snippet,
                    )
                )

            # Extract supported inferences from relationships
            for rel in s_res.relationships:
                findings.append(
                    AgentFinding(
                        claim=f"Inferred relationship: '{rel.source_entity}' {rel.relationship_type} '{rel.target_entity}'",
                        classification=FindingClassification.SUPPORTED_INFERENCE,
                        confidence_score=rel.confidence,
                        supporting_snippet=f"Derived from {s_res.source_name} record",
                    )
                )

            # Extracted entities as unverified leads or facts
            for ent in s_res.entities:
                findings.append(
                    AgentFinding(
                        claim=f"Identified associated entity '{ent.name}' of type {ent.entity_type}",
                        classification=FindingClassification.FACT if ent.confidence >= 0.9 else FindingClassification.SUPPORTED_INFERENCE,
                        confidence_score=ent.confidence,
                    )
                )
        else:
            # Unsuccessful execution or no evidence
            error_reason = tool_result.error_message or "No corroborating evidence discovered"
            findings.append(
                AgentFinding(
                    claim=f"Unable to verify target '{target}': {error_reason}",
                    classification=FindingClassification.UNVERIFIED,
                    confidence_score=0.1,
                )
            )

        elapsed_ms = int((time.perf_counter() - start_time) * 1000)

        # 4. Database Persistence (AgentRun, Findings, Task update)
        if db:
            try:
                # Update task status if task_id provided
                if task_id:
                    task_stmt = select(InvestigationTask).where(InvestigationTask.id == task_id)
                    task_obj = (await db.execute(task_stmt)).scalar_one_or_none()
                    if task_obj:
                        task_obj.status = "completed" if tool_result.success else "failed"
                        task_obj.completed_at = datetime.now(UTC)
                        task_obj.output_data = {
                            "findings_count": len(findings),
                            "tools_executed": tools_executed,
                        }

                # Update investigation status
                inv_stmt = select(Investigation).where(Investigation.id == investigation_id)
                inv_obj = (await db.execute(inv_stmt)).scalar_one_or_none()
                if inv_obj and inv_obj.status == "created":
                    inv_obj.status = "in_progress"

                # Persist AgentRun record
                agent_run = AgentRun(
                    investigation_id=investigation_id,
                    agent_role="InvestigationManager",
                    model_name=model_name,
                    started_at=datetime.now(UTC),
                    ended_at=datetime.now(UTC),
                )
                db.add(agent_run)

                # Persist Finding records
                for f in findings:
                    db_finding = Finding(
                        investigation_id=investigation_id,
                        claim=f.claim,
                        classification=f.classification.value,
                        confidence_score=f.confidence_score,
                        created_at=datetime.now(UTC),
                    )
                    db.add(db_finding)

                await db.commit()
            except Exception as e:  # noqa: BLE001
                logger.error("Failed persisting AgentRun/Findings: %s", e)

        return AgentRunResult(
            investigation_id=investigation_id,
            agent_role="InvestigationManager",
            model_name=model_name,
            objective=objective or f"Investigate target {target}",
            status="completed" if tool_result.success else "failed",
            findings=findings,
            tools_executed=tools_executed,
            summary=f"Executed {len(tools_executed)} tool(s), extracted {len(findings)} findings.",
            execution_time_ms=elapsed_ms,
        )
