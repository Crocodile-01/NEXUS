from __future__ import annotations

import logging

from app.services.intelligence_engine.schemas import (
    EntityExpansionLead,
    PlannerLimits,
    TypedRelationship,
)
from app.sources.base import ExtractedEntity, ExtractedRelationship

logger = logging.getLogger(__name__)

# Low-value or generic terms to exclude from expansion
STOP_ENTITIES = {
    "privacy policy", "terms of service", "home", "about us", "contact us",
    "login", "sign up", "cookie policy", "careers", "documentation",
    "all rights reserved", "unknown", "general",
}


class EntityExpander:
    """
    Manages bounded secondary entity expansion and uncovers multi-hop relationship chains.
    """

    @classmethod
    def evaluate_expansion_leads(
        cls,
        entities: list[ExtractedEntity],
        relationships: list[ExtractedRelationship],
        current_depth: int,
        limits: PlannerLimits,
        visited: set[str],
    ) -> list[EntityExpansionLead]:
        """
        Evaluates extracted entities to select high-relevance leads for bounded expansion.
        """
        if current_depth >= limits.max_depth:
            return []

        leads: list[EntityExpansionLead] = []

        # Map entity relationships for context
        entity_rel_map: dict[str, list[tuple[str, str, str]]] = {}
        for r in relationships:
            src = r.source_entity.strip()
            tgt = r.target_entity.strip()
            rel_type = r.relationship_type
            entity_rel_map.setdefault(src.lower(), []).append((src, rel_type, tgt))
            entity_rel_map.setdefault(tgt.lower(), []).append((src, rel_type, tgt))

        for ent in entities:
            norm_name = ent.name.strip().lower()
            if not norm_name or norm_name in STOP_ENTITIES or len(norm_name) < 2:
                continue
            if norm_name in visited:
                continue

            ent_type = ent.entity_type.upper()
            relevance = cls._calculate_relevance(ent_type, ent.name, ent.confidence)

            if relevance >= limits.min_relevance_score:
                chains = entity_rel_map.get(norm_name, [])
                leads.append(
                    EntityExpansionLead(
                        entity_name=ent.name.strip(),
                        entity_type=ent_type,
                        discovered_via="entity_extraction",
                        depth=current_depth,
                        relevance_score=round(relevance, 2),
                        relationship_chain=chains[:3],
                    )
                )

        # Sort leads by relevance descending and return top allowed
        leads.sort(key=lambda l: l.relevance_score, reverse=True)
        return leads[: limits.max_new_entities_per_task]

    @classmethod
    def _calculate_relevance(cls, entity_type: str, name: str, confidence: float) -> float:
        """
        Calculates a baseline relevance score for an entity based on its type and characteristics.
        """
        base_score = 0.5
        if entity_type == "REPOSITORY":
            base_score = 0.90
        elif entity_type in ("PROJECT", "PRODUCT"):
            base_score = 0.85
        elif entity_type == "PERSON":
            # Multiple words in person name increase relevance
            base_score = 0.80 if len(name.split()) >= 2 else 0.60
        elif entity_type in ("COMPANY", "ORGANIZATION"):
            base_score = 0.85
        elif entity_type == "RESEARCH_PAPER":
            base_score = 0.78
        elif entity_type == "DOMAIN":
            base_score = 0.70

        # Adjust by extraction confidence
        return min(1.0, (base_score * 0.7) + (confidence * 0.3))

    @classmethod
    def discover_relationship_chains(
        cls,
        relationships: list[TypedRelationship],
    ) -> list[list[str]]:
        """
        Traces multi-hop relationship chains across discovered entities:
        e.g. ['Company X', 'develops', 'Project Y', 'uses', 'Technology Z']
        """
        # Build adjacency graph: subject_lower -> list of (predicate, object_original, object_lower)
        name_map: dict[str, str] = {}
        adj: dict[str, list[tuple[str, str, str]]] = {}
        for rel in relationships:
            s = rel.subject.strip()
            p = rel.predicate.strip()
            o = rel.object.strip()
            s_lower = s.lower()
            o_lower = o.lower()
            if s_lower not in name_map:
                name_map[s_lower] = s
            if o_lower not in name_map:
                name_map[o_lower] = o
            adj.setdefault(s_lower, []).append((p, o, o_lower))

        chains: list[list[str]] = []

        # Find paths of length 2 or 3 hops
        for s_lower, edges in adj.items():
            s_name = name_map[s_lower]
            for p1, o1, o1_lower in edges:
                # Check 2nd hop
                if o1_lower in adj:
                    for p2, o2, o2_lower in adj[o1_lower]:
                        if o2_lower != s_lower:  # Avoid direct loops
                            chains.append([s_name, p1, o1, p2, o2])
                            # Check 3rd hop
                            if o2_lower in adj:
                                for p3, o3, o3_lower in adj[o2_lower]:
                                    if o3_lower not in (s_lower, o1_lower):
                                        chains.append([s_name, p1, o1, p2, o2, p3, o3])

        # Deduplicate and sort by chain length descending
        unique_chains: list[list[str]] = []
        seen = set()
        for chain in sorted(chains, key=len, reverse=True):
            rep = " -> ".join(chain)
            if rep not in seen:
                seen.add(rep)
                unique_chains.append(chain)

        return unique_chains[:10]
