from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.agents.manager import InvestigationManager
from app.agents.schemas import AgentRunResult
from app.core.database import get_db
from app.models.investigation import Investigation
from app.models.task import InvestigationTask
from app.schemas.investigation import (
    InvestigationCreate,
    InvestigationRead,
)
from app.security.execution_scope import ExecutionMode, ExecutionScope

router = APIRouter(prefix="/investigations", tags=["Investigations"])


@router.post("", response_model=InvestigationRead, status_code=status.HTTP_201_CREATED, summary="Create a new investigation")
async def create_investigation(
    payload: InvestigationCreate,
    execute: bool = Query(default=False, description="Automatically trigger manager execution step upon creation"),
    db: AsyncSession = Depends(get_db),  # noqa: B008
):
    investigation = Investigation(
        target=payload.target,
        target_type=payload.target_type,
        objective=payload.objective,
        max_depth=payload.max_depth,
        max_tasks=payload.max_tasks,
        mode=payload.mode,
        status="created",
    )

    task_id = str(uuid.uuid4())
    initial_task = InvestigationTask(
        id=task_id,
        investigation_id=investigation.id,
        name=f"Identify target: {payload.target}",
        task_type="target_classification",
        depth_level=0,
        status="pending",
        input_data={"target": payload.target, "target_type": payload.target_type},
    )
    investigation.tasks.append(initial_task)

    db.add(investigation)
    await db.commit()
    await db.refresh(investigation)

    # Automatically execute initial manager step if requested
    if payload.auto_execute or execute:
        scope = ExecutionScope(mode=ExecutionMode(investigation.mode))
        await InvestigationManager.run_step(
            investigation_id=investigation.id,
            target=investigation.target,
            target_type=investigation.target_type,
            objective=investigation.objective or "",
            scope=scope,
            db=db,
            task_id=task_id,
        )

    # Reload with tasks
    result = await db.execute(
        select(Investigation)
        .options(selectinload(Investigation.tasks))
        .where(Investigation.id == investigation.id)
    )
    return result.scalar_one()


@router.post("/{investigation_id}/execute", response_model=AgentRunResult, summary="Execute manager step on an investigation")
async def execute_investigation(
    investigation_id: str,
    db: AsyncSession = Depends(get_db),  # noqa: B008
):
    result = await db.execute(
        select(Investigation)
        .options(selectinload(Investigation.tasks))
        .where(Investigation.id == investigation_id)
    )
    investigation = result.scalar_one_or_none()
    if not investigation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Investigation {investigation_id} not found",
        )

    # Find pending or latest task
    pending_tasks = [t for t in investigation.tasks if t.status == "pending"]
    active_task = pending_tasks[0] if pending_tasks else (investigation.tasks[0] if investigation.tasks else None)

    scope = ExecutionScope(mode=ExecutionMode(investigation.mode))
    run_result = await InvestigationManager.run_step(
        investigation_id=investigation.id,
        target=investigation.target,
        target_type=investigation.target_type,
        objective=investigation.objective or "",
        scope=scope,
        db=db,
        task_id=active_task.id if active_task else None,
    )
    return run_result


@router.get("", response_model=list[InvestigationRead], summary="List all investigations")
async def list_investigations(
    skip: int = 0,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),  # noqa: B008
):
    result = await db.execute(
        select(Investigation)
        .options(selectinload(Investigation.tasks))
        .offset(skip)
        .limit(limit)
        .order_by(Investigation.created_at.desc())
    )
    return result.scalars().all()


@router.get("/{investigation_id}", response_model=InvestigationRead, summary="Get investigation by ID")
async def get_investigation(
    investigation_id: str,
    db: AsyncSession = Depends(get_db),  # noqa: B008
):
    result = await db.execute(
        select(Investigation)
        .options(selectinload(Investigation.tasks))
        .where(Investigation.id == investigation_id)
    )
    investigation = result.scalar_one_or_none()
    if not investigation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Investigation {investigation_id} not found",
        )
    return investigation
