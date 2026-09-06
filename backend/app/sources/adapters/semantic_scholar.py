from app.core.config import settings
from app.sources.base import (
    ExtractedEntity,
    ExtractedRelationship,
    RawEvidence,
    SourceAdapter,
    SourceMetadata,
    SourceResult,
)
from app.sources.http_client import get_httpx_client


class SemanticScholarAdapter(SourceAdapter):
    """
    Adapter for searching Semantic Scholar research papers, authors, and citation graphs.
    """

    @property
    def metadata(self) -> SourceMetadata:
        return SourceMetadata(
            name="semantic_scholar",
            category="academic",
            reliability_tier="REPUTABLE",
            is_passive=True,
            rate_limit_per_minute=30,
            timeout_seconds=15,
        )

    async def search(self, query: str, limit: int = 5) -> SourceResult:
        url = "https://api.semanticscholar.org/graph/v1/paper/search"
        params = {
            "query": query,
            "limit": limit,
            "fields": "title,abstract,authors,year,publicationDate,url,citationCount",
        }

        headers = {}
        if settings.SEMANTIC_SCHOLAR_API_KEY:
            headers["x-api-key"] = settings.SEMANTIC_SCHOLAR_API_KEY

        try:
            async with get_httpx_client(timeout_seconds=self.metadata.timeout_seconds, headers=headers) as client:
                response = await client.get(url, params=params)
                response.raise_for_status()
                data = response.json()
        except Exception as exc:  # noqa: BLE001
            return SourceResult(
                success=False,
                source_name=self.metadata.name,
                query=query,
                error_message=f"Semantic Scholar API error: {exc!s}",
            )

        paper_items = data.get("data", [])
        evidence_list: list[RawEvidence] = []
        entities: list[ExtractedEntity] = []
        relationships: list[ExtractedRelationship] = []

        for paper in paper_items:
            title = paper.get("title", "")
            abstract = paper.get("abstract") or ""
            paper_url = paper.get("url") or f"https://www.semanticscholar.org/paper/{paper.get('paperId')}"
            pub_date = paper.get("publicationDate") or str(paper.get("year") or "")

            if not title:
                continue

            paper_entity = ExtractedEntity(
                name=title,
                entity_type="RESEARCH_PAPER",
                confidence=1.0,
                metadata={"paperId": paper.get("paperId"), "citationCount": paper.get("citationCount")},
            )
            entities.append(paper_entity)

            # Authors
            authors = paper.get("authors", [])
            for author in authors:
                author_name = author.get("name")
                if author_name:
                    entities.append(ExtractedEntity(name=author_name, entity_type="PERSON", confidence=0.9))
                    relationships.append(
                        ExtractedRelationship(
                            source_entity=author_name,
                            source_entity_type="PERSON",
                            target_entity=title,
                            target_entity_type="RESEARCH_PAPER",
                            relationship_type="authored",
                            confidence=0.9,
                        )
                    )

            snippet = f"Paper: '{title}' ({pub_date}) - {abstract[:250]}..."
            evidence_list.append(
                RawEvidence(
                    source_name=self.metadata.name,
                    url=paper_url,
                    extracted_snippet=snippet,
                    publication_date=pub_date,
                    metadata={"paperId": paper.get("paperId")},
                )
            )

        return SourceResult(
            success=True,
            source_name=self.metadata.name,
            query=query,
            evidence=evidence_list,
            entities=entities,
            relationships=relationships,
        )
