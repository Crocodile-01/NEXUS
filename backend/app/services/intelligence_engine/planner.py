from __future__ import annotations

import logging
import uuid

from app.services.intelligence_engine.schemas import (
    EntityExpansionLead,
    PlannerLimits,
    ResearchCategory,
    ResearchPlan,
    ResearchQuestion,
)

logger = logging.getLogger(__name__)


class ResearchPlanner:
    """
    Generates, bounds, and prioritizes structured research questions
    for multi-source entity investigations.
    """

    @classmethod
    def generate_initial_plan(
        cls,
        target: str,
        target_type: str,
        objective: str | None = None,
        limits: PlannerLimits | None = None,
        investigation_id: str | None = None,
    ) -> ResearchPlan:
        """
        Deconstructs an investigation target into an initial set of prioritized
        research questions spanning all 8 core intelligence dimensions.
        """
        inv_id = investigation_id or str(uuid.uuid4())
        active_limits = limits or PlannerLimits()
        questions: list[ResearchQuestion] = []

        norm_target_type = target_type.strip().lower()
        clean_target = target.strip()

        # 1. Identity & Operating Entity
        questions.append(
            ResearchQuestion(
                id=f"q-{uuid.uuid4().hex[:8]}",
                question=f"Who operates '{clean_target}' and what official legal entity or corporate aliases exist?",
                category=ResearchCategory.IDENTITY,
                priority=0.98,
                target_entity=clean_target,
                target_entity_type=norm_target_type,
                suggested_sources=["website", "wikidata", "sec_edgar"],
                depth=0,
                rationale="Identify the authoritative legal or organizational controller behind the target.",
            )
        )

        # 2. Organization & Mission
        questions.append(
            ResearchQuestion(
                id=f"q-{uuid.uuid4().hex[:8]}",
                question=f"What is the stated purpose, commercial offerings, or core mission of '{clean_target}'?",
                category=ResearchCategory.ORGANIZATION,
                priority=0.90,
                target_entity=clean_target,
                target_entity_type=norm_target_type,
                suggested_sources=["website", "wikidata"],
                depth=0,
                rationale="Determine organizational activities, products, and operational focus.",
            )
        )

        # 3. People & Key Leadership
        questions.append(
            ResearchQuestion(
                id=f"q-{uuid.uuid4().hex[:8]}",
                question=f"Who are the publicly associated founders, executives, directors, or maintainers of '{clean_target}'?",
                category=ResearchCategory.PEOPLE,
                priority=0.92,
                target_entity=clean_target,
                target_entity_type=norm_target_type,
                suggested_sources=["website", "wikidata", "arxiv"],
                depth=0,
                rationale="Identify public personnel, corporate officers, and key individual contributors.",
            )
        )

        # 4. Technology & Repositories
        questions.append(
            ResearchQuestion(
                id=f"q-{uuid.uuid4().hex[:8]}",
                question=f"What software technologies, cloud stacks, and open-source repositories are associated with '{clean_target}'?",
                category=ResearchCategory.TECHNOLOGY,
                priority=0.88,
                target_entity=clean_target,
                target_entity_type=norm_target_type,
                suggested_sources=["website", "fetch_webpage"],
                depth=0,
                rationale="Detect technical infrastructure, programming stacks, and linked code repositories.",
            )
        )

        # 5. Digital Infrastructure & TLS
        if norm_target_type in ("domain", "url"):
            questions.append(
                ResearchQuestion(
                    id=f"q-{uuid.uuid4().hex[:8]}",
                    question=f"What public subdomains and TLS certificates are historically associated with '{clean_target}'?",
                    category=ResearchCategory.INFRASTRUCTURE,
                    priority=0.85,
                    target_entity=clean_target,
                    target_entity_type="domain",
                    suggested_sources=["crt_sh"],
                    depth=0,
                    rationale="Map external digital footprint via Certificate Transparency logs.",
                )
            )

        # 6. Research & Scientific Publications
        questions.append(
            ResearchQuestion(
                id=f"q-{uuid.uuid4().hex[:8]}",
                question=f"What academic publications, whitepapers, or scientific research are authored or sponsored by '{clean_target}'?",
                category=ResearchCategory.RESEARCH,
                priority=0.78,
                target_entity=clean_target,
                target_entity_type=norm_target_type,
                suggested_sources=["arxiv", "semantic_scholar"],
                depth=0,
                rationale="Discover scholarly papers, citations, and research affiliations.",
            )
        )

        # 7. External Intelligence & Corroboration
        questions.append(
            ResearchQuestion(
                id=f"q-{uuid.uuid4().hex[:8]}",
                question=f"What independent third-party sources (Wikidata, SEC filings, public registries) corroborate claims regarding '{clean_target}'?",
                category=ResearchCategory.EXTERNAL_INTELLIGENCE,
                priority=0.86,
                target_entity=clean_target,
                target_entity_type=norm_target_type,
                suggested_sources=["wikidata", "sec_edgar", "crt_sh"],
                depth=0,
                rationale="Cross-verify primary claims with independent structured public knowledge bases.",
            )
        )

        # 8. Temporal Evolution & History
        questions.append(
            ResearchQuestion(
                id=f"q-{uuid.uuid4().hex[:8]}",
                question=f"What historical timeline milestones (inception date, filing dates, copyright notices) exist for '{clean_target}'?",
                category=ResearchCategory.TEMPORAL,
                priority=0.74,
                target_entity=clean_target,
                target_entity_type=norm_target_type,
                suggested_sources=["wikidata", "website", "sec_edgar"],
                depth=0,
                rationale="Anchor findings in chronological milestones and observable timestamps.",
            )
        )

        # Tailor plan if objective is provided
        if objective:
            obj_lower = objective.lower()
            for q in questions:
                if q.category == ResearchCategory.TECHNOLOGY and any(w in obj_lower for w in ["tech", "stack", "software", "repo", "ai", "framework"]) or q.category == ResearchCategory.PEOPLE and any(w in obj_lower for w in ["person", "people", "team", "founder", "executive", "ceo", "leadership", "leader"]) or q.category == ResearchCategory.RESEARCH and any(w in obj_lower for w in ["research", "paper", "science", "academic", "publication"]) or q.category == ResearchCategory.INFRASTRUCTURE and any(w in obj_lower for w in ["infrastructure", "domain", "subdomain", "tls", "cert"]):
                    q.priority = 0.99

        return ResearchPlan(
            investigation_id=inv_id,
            target=clean_target,
            target_type=norm_target_type,
            limits=active_limits,
            questions=questions,
        )

    @classmethod
    def generate_expansion_questions(
        cls,
        lead: EntityExpansionLead,
        current_plan: ResearchPlan,
    ) -> list[ResearchQuestion]:
        """
        Dynamically formulates bounded follow-up research questions when a discovered
        entity qualifies as a high-relevance lead (depth < max_depth).
        """
        # Strictly enforce bounds
        if lead.depth >= current_plan.limits.max_depth:
            return []
        if current_plan.total_queries_executed >= current_plan.limits.max_source_queries:
            return []
        if lead.relevance_score < current_plan.limits.min_relevance_score:
            return []

        # Count existing questions targeting this entity
        existing_for_entity = sum(
            1 for q in current_plan.questions if q.target_entity.lower() == lead.entity_name.lower()
        )
        if existing_for_entity >= current_plan.limits.max_expansions_per_entity:
            return []

        expansion_questions: list[ResearchQuestion] = []
        ent_type = lead.entity_type.upper()
        next_depth = lead.depth + 1

        if ent_type == "REPOSITORY":
            expansion_questions.append(
                ResearchQuestion(
                    id=f"q-{uuid.uuid4().hex[:8]}",
                    question=f"What technologies, languages, and maintainers are associated with repository '{lead.entity_name}'?",
                    category=ResearchCategory.TECHNOLOGY,
                    priority=0.82,
                    target_entity=f"https://github.com/{lead.entity_name}",
                    target_entity_type="url",
                    suggested_sources=["fetch_webpage"],
                    depth=next_depth,
                    rationale=f"Secondary expansion on discovered repository '{lead.entity_name}'.",
                )
            )
        elif ent_type == "PERSON":
            expansion_questions.append(
                ResearchQuestion(
                    id=f"q-{uuid.uuid4().hex[:8]}",
                    question=f"What publications, research papers, or organizational affiliations exist for '{lead.entity_name}'?",
                    category=ResearchCategory.RESEARCH,
                    priority=0.76,
                    target_entity=lead.entity_name,
                    target_entity_type="person",
                    suggested_sources=["semantic_scholar", "arxiv", "wikidata"],
                    depth=next_depth,
                    rationale=f"Secondary expansion on named person '{lead.entity_name}'.",
                )
            )
        elif ent_type in ("PROJECT", "PRODUCT"):
            expansion_questions.append(
                ResearchQuestion(
                    id=f"q-{uuid.uuid4().hex[:8]}",
                    question=f"What organization operates project '{lead.entity_name}' and what technical dependencies exist?",
                    category=ResearchCategory.ORGANIZATION,
                    priority=0.79,
                    target_entity=lead.entity_name,
                    target_entity_type="project",
                    suggested_sources=["wikidata", "fetch_webpage"],
                    depth=next_depth,
                    rationale=f"Secondary expansion on product/project '{lead.entity_name}'.",
                )
            )
        elif ent_type in ("COMPANY", "ORGANIZATION") and lead.entity_name.lower() != current_plan.target.lower():
            expansion_questions.append(
                ResearchQuestion(
                    id=f"q-{uuid.uuid4().hex[:8]}",
                    question=f"What corporate profile, identifiers, and subsidiaries are recorded for '{lead.entity_name}'?",
                    category=ResearchCategory.IDENTITY,
                    priority=0.84,
                    target_entity=lead.entity_name,
                    target_entity_type="company",
                    suggested_sources=["wikidata", "sec_edgar"],
                    depth=next_depth,
                    rationale=f"Secondary expansion on associated organization '{lead.entity_name}'.",
                )
            )

        return expansion_questions

    @classmethod
    def prioritize_questions(cls, plan: ResearchPlan) -> list[ResearchQuestion]:
        """
        Returns pending questions ordered by depth ascending, priority descending.
        """
        pending = [q for q in plan.questions if q.status == "pending"]
        return sorted(pending, key=lambda q: (q.depth, -q.priority))
