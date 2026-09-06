import re

from rapidfuzz import fuzz
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.entity import Entity, EntityAlias
from app.sources.base import ExtractedEntity


def normalize_name(name: str) -> str:
    """Normalize string by lowercasing, stripping punctuation, and collapsing whitespace."""
    clean = re.sub(r"[^\w\s]", "", name.lower())
    return " ".join(clean.split())


async def resolve_entity(db: AsyncSession, extracted: ExtractedEntity) -> Entity:
    """
    Deterministically resolves an extracted entity against existing database records.
    Hierarchy:
    1. Exact Canonical Match (canonical_name + entity_type)
    2. Alias Match
    3. Normalized Comparison
    4. Fuzzy Match with RapidFuzz WRatio (>= 85% score within same entity_type)
    """
    raw_name = extracted.name.strip()
    entity_type = extracted.entity_type.upper()
    norm_target = normalize_name(raw_name)

    # 1. Exact Canonical Match
    exact_stmt = select(Entity).options(selectinload(Entity.aliases)).where(
        Entity.canonical_name == raw_name, Entity.entity_type == entity_type
    )
    result = await db.execute(exact_stmt)
    existing = result.scalar_one_or_none()
    if existing:
        return existing

    # 2. Alias Match
    alias_stmt = select(EntityAlias).where(EntityAlias.alias_name == raw_name)
    alias_result = await db.execute(alias_stmt)
    alias_match = alias_result.scalar_one_or_none()
    if alias_match:
        ent_stmt = select(Entity).options(selectinload(Entity.aliases)).where(Entity.id == alias_match.entity_id)
        return (await db.execute(ent_stmt)).scalar_one()

    # Fetch all candidate entities of the same type for normalized & fuzzy comparison
    all_type_stmt = select(Entity).options(selectinload(Entity.aliases)).where(Entity.entity_type == entity_type)
    candidates = (await db.execute(all_type_stmt)).scalars().all()

    for candidate in candidates:
        cand_norm = normalize_name(candidate.canonical_name)
        # 3. Normalized Comparison
        if cand_norm == norm_target:
            if raw_name != candidate.canonical_name and not any(a.alias_name == raw_name for a in candidate.aliases):
                new_alias = EntityAlias(entity_id=candidate.id, alias_name=raw_name, source_provenance="normalization")
                db.add(new_alias)
                await db.commit()
            return candidate

        # Check aliases normalized
        for alias_obj in candidate.aliases:
            if normalize_name(alias_obj.alias_name) == norm_target:
                return candidate

        # 4. RapidFuzz Fuzzy Match (WRatio >= 85%)
        ratio = fuzz.WRatio(norm_target, cand_norm)
        if ratio >= 85:
            if raw_name != candidate.canonical_name and not any(a.alias_name == raw_name for a in candidate.aliases):
                new_alias = EntityAlias(entity_id=candidate.id, alias_name=raw_name, source_provenance=f"rapidfuzz_{int(ratio)}")
                db.add(new_alias)
                await db.commit()
            return candidate

    # No match found -> create new Entity
    new_entity = Entity(
        canonical_name=raw_name,
        entity_type=entity_type,
        confidence_score=extracted.confidence,
        metadata_json=extracted.metadata,
    )
    for alias_str in extracted.aliases:
        if alias_str.strip() and alias_str.strip() != raw_name:
            new_entity.aliases.append(
                EntityAlias(alias_name=alias_str.strip(), source_provenance="extracted")
            )

    db.add(new_entity)
    await db.commit()
    await db.refresh(new_entity)
    return new_entity
