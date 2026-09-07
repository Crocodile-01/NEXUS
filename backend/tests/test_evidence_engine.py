import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Entity, Evidence, Relationship, Source
from app.services.entity_resolution import resolve_entity
from app.services.evidence_engine import persist_source_result
from app.sources.base import (
    ExtractedEntity,
    ExtractedRelationship,
    RawEvidence,
    SourceResult,
)


@pytest.mark.asyncio
async def test_entity_resolution_flow(test_db_session: AsyncSession):
    # 1. New entity
    ext1 = ExtractedEntity(name="NVIDIA Corp", entity_type="COMPANY", aliases=["NVDA"])
    ent1 = await resolve_entity(test_db_session, ext1)
    assert ent1.canonical_name == "NVIDIA Corp"
    assert len(ent1.aliases) == 1

    # 2. Exact match
    ext2 = ExtractedEntity(name="NVIDIA Corp", entity_type="COMPANY")
    ent2 = await resolve_entity(test_db_session, ext2)
    assert ent2.id == ent1.id

    # 3. Alias match
    ext3 = ExtractedEntity(name="NVDA", entity_type="COMPANY")
    ent3 = await resolve_entity(test_db_session, ext3)
    assert ent3.id == ent1.id

    # 4. RapidFuzz fuzzy match ("NVIDIA Corporation" vs "NVIDIA Corp")
    ext4 = ExtractedEntity(name="NVIDIA Corporation", entity_type="COMPANY")
    ent4 = await resolve_entity(test_db_session, ext4)
    assert ent4.id == ent1.id


@pytest.mark.asyncio
async def test_persist_source_result_flow(test_db_session: AsyncSession):
    source_res = SourceResult(
        success=True,
        source_name="wikidata",
        query="NVIDIA",
        evidence=[
            RawEvidence(
                source_name="wikidata",
                url="https://wikidata.org/wiki/Q2283",
                extracted_snippet="NVIDIA: American technology company",
            )
        ],
        entities=[
            ExtractedEntity(name="NVIDIA", entity_type="COMPANY"),
            ExtractedEntity(name="Jensen Huang", entity_type="PERSON"),
        ],
        relationships=[
            ExtractedRelationship(
                source_entity="Jensen Huang",
                source_entity_type="PERSON",
                target_entity="NVIDIA",
                target_entity_type="COMPANY",
                relationship_type="ceo_of",
            )
        ],
    )

    evidences = await persist_source_result(test_db_session, source_res)
    assert len(evidences) == 1
    assert evidences[0].url == "https://wikidata.org/wiki/Q2283"

    # Verify Source DB entry
    source_stmt = select(Source).where(Source.name == "wikidata")
    source_obj = (await test_db_session.execute(source_stmt)).scalar_one()
    assert source_obj.name == "wikidata"

    # Verify Entity DB entries
    entities = (await test_db_session.execute(select(Entity))).scalars().all()
    assert len(entities) == 2
    ent_names = [e.canonical_name for e in entities]
    assert "NVIDIA" in ent_names
    assert "Jensen Huang" in ent_names

    # Verify Relationship DB entry
    rels = (await test_db_session.execute(select(Relationship))).scalars().all()
    assert len(rels) == 1
    assert rels[0].relationship_type == "ceo_of"


@pytest.mark.asyncio
async def test_evidence_hash_deduplication(test_db_session: AsyncSession):
    source_res = SourceResult(
        success=True,
        source_name="crt_sh",
        query="example.com",
        evidence=[
            RawEvidence(
                source_name="crt_sh",
                url="https://crt.sh/?q=example.com",
                extracted_snippet="Certificate issued for example.com",
            )
        ],
    )

    # Persist first time
    ev1 = await persist_source_result(test_db_session, source_res)
    assert len(ev1) == 1

    # Persist second time (duplicate hash)
    ev2 = await persist_source_result(test_db_session, source_res)
    assert len(ev2) == 1
    assert ev2[0].id == ev1[0].id

    # Total Evidence records in DB should be 1
    all_ev = (await test_db_session.execute(select(Evidence))).scalars().all()
    assert len(all_ev) == 1
