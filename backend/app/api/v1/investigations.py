from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.models.investigation import Investigation
from app.models.task import InvestigationTask
from app.schemas.investigation import (
    InvestigationCreate,
    InvestigationRead,
)

router = APIRouter(prefix="/investigations", tags=["Investigations"])


@router.post("", response_model=InvestigationRead, status_code=status.HTTP_201_CREATED, summary="Create a new investigation")
async def create_investigation(
    payload: InvestigationCreate,
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

    # Initialize default initial task
    initial_task = InvestigationTask(
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

    # Reload with tasks
    result = await db.execute(
        select(Investigation)
        .options(selectinload(Investigation.tasks))
        .where(Investigation.id == investigation.id)
    )
    return result.scalar_one()


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
