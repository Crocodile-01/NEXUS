import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.entity import Entity
from app.models.evidence import Evidence
from app.models.relationship import Relationship
from app.models.source import Source
from app.services.entity_resolution import resolve_entity
from app.sources.base import ExtractedEntity, SourceResult

logger = logging.getLogger(__name__)


async def get_or_create_source(
    db: AsyncSession,
    source_name: str,
    source_type: str = "web",
    reliability_tier: str = "REPUTABLE",
) -> Source:
    """Ensure Source entity exists in database."""
    stmt = select(Source).where(Source.name == source_name)
    result = await db.execute(stmt)
    source = result.scalar_one_or_none()
    if not source:
        source = Source(
            name=source_name,
            source_type=source_type,
            reliability_tier=reliability_tier,
        )
        db.add(source)
        await db.commit()
        await db.refresh(source)
    return source


async def persist_source_result(
    db: AsyncSession,
    result: SourceResult,
    reliability_tier: str = "REPUTABLE",
) -> list[Evidence]:
    """
    Persist raw evidence, resolved entities, and extracted relationships from a SourceResult.
    Content hashing prevents duplicate evidence storage.
    """
    if not result.success or not result.evidence:
        return []

    # 1. Ensure Source record exists
    source_obj = await get_or_create_source(
        db=db,
        source_name=result.source_name,
        reliability_tier=reliability_tier,
    )

    persisted_evidences: list[Evidence] = []

    # 2. Persist Evidence Records (content_hash deduplication)
    for raw_ev in result.evidence:
        if not raw_ev.content_hash:
            continue

        # Check existing evidence by hash
        hash_stmt = select(Evidence).where(Evidence.content_hash == raw_ev.content_hash)
        existing_ev = (await db.execute(hash_stmt)).scalar_one_or_none()

        if existing_ev:
            persisted_evidences.append(existing_ev)
            continue

        ev_obj = Evidence(
            source_id=source_obj.id,
            url=raw_ev.url,
            raw_content_ref=raw_ev.raw_content,
            extracted_snippet=raw_ev.extracted_snippet,
            content_hash=raw_ev.content_hash,
        )
        db.add(ev_obj)
        await db.commit()
        await db.refresh(ev_obj)
        persisted_evidences.append(ev_obj)

    # 3. Resolve & Persist Entities
    resolved_entity_map: dict[str, Entity] = {}
    for ext_ent in result.entities:
        resolved_ent = await resolve_entity(db, ext_ent)
        resolved_entity_map[ext_ent.name.strip().lower()] = resolved_ent

    # 4. Persist Relationships
    for rel in result.relationships:
        src_name = rel.source_entity.strip().lower()
        tgt_name = rel.target_entity.strip().lower()

        src_ent = resolved_entity_map.get(src_name)
        if not src_ent:
            src_ent = await resolve_entity(
                db, ExtractedEntity(name=rel.source_entity, entity_type=rel.source_entity_type)
            )
            resolved_entity_map[src_name] = src_ent

        tgt_ent = resolved_entity_map.get(tgt_name)
        if not tgt_ent:
            tgt_ent = await resolve_entity(
                db, ExtractedEntity(name=rel.target_entity, entity_type=rel.target_entity_type)
            )
            resolved_entity_map[tgt_name] = tgt_ent

        # Check duplicate relationship
        rel_stmt = select(Relationship).where(
            Relationship.source_entity_id == src_ent.id,
            Relationship.target_entity_id == tgt_ent.id,
            Relationship.relationship_type == rel.relationship_type,
        )
        existing_rel = (await db.execute(rel_stmt)).scalar_one_or_none()

        if not existing_rel:
            assoc_ev_id = persisted_evidences[0].id if persisted_evidences else None
            db_rel = Relationship(
                source_entity_id=src_ent.id,
                target_entity_id=tgt_ent.id,
                relationship_type=rel.relationship_type,
                confidence_score=rel.confidence,
                evidence_id=assoc_ev_id,
            )
            db.add(db_rel)

    await db.commit()
    return persisted_evidences
