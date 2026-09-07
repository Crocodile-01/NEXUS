import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Entity,
    EntityAlias,
    Evidence,
    Investigation,
    InvestigationTask,
    Source,
)


@pytest.mark.asyncio
async def test_investigation_and_task_models(test_db_session: AsyncSession):
    inv = Investigation(
        target="NVIDIA",
        target_type="company",
        objective="Analyze GPU tech trends",
        mode="PASSIVE_PUBLIC",
    )
    task = InvestigationTask(
        investigation_id=inv.id,
        name="Identify NVIDIA official domains",
        task_type="domain_recon",
        depth_level=0,
    )
    inv.tasks.append(task)
    test_db_session.add(inv)
    await test_db_session.commit()

    result = await test_db_session.execute(
        select(Investigation).where(Investigation.id == inv.id)
    )
    fetched_inv = result.scalar_one()
    assert fetched_inv.target == "NVIDIA"
    assert fetched_inv.status == "created"
    assert len(fetched_inv.tasks) == 1
    assert fetched_inv.tasks[0].name == "Identify NVIDIA official domains"


@pytest.mark.asyncio
async def test_entity_alias_and_evidence_models(test_db_session: AsyncSession):
    entity = Entity(
        canonical_name="NVIDIA Corporation",
        entity_type="COMPANY",
        confidence_score=0.98,
    )
    alias = EntityAlias(entity_id=entity.id, alias_name="NVDA", source_provenance="NASDAQ")
    entity.aliases.append(alias)

    source = Source(name="crt.sh", source_type="certificate", reliability_tier="REPUTABLE")
    evidence = Evidence(
        source=source,
        url="https://crt.sh/?q=nvidia.com",
        extracted_snippet="nvidia.com SAN entry",
        content_hash="abc123hash",
    )

    test_db_session.add_all([entity, source, evidence])
    await test_db_session.commit()

    fetched_entity = (
        await test_db_session.execute(select(Entity).where(Entity.id == entity.id))
    ).scalar_one()
    assert fetched_entity.canonical_name == "NVIDIA Corporation"
    assert len(fetched_entity.aliases) == 1
    assert fetched_entity.aliases[0].alias_name == "NVDA"

    fetched_evidence = (
        await test_db_session.execute(select(Evidence).where(Evidence.id == evidence.id))
    ).scalar_one()
    assert fetched_evidence.content_hash == "abc123hash"
