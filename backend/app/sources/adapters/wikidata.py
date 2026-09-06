from app.sources.base import (
    ExtractedEntity,
    ExtractedRelationship,
    RawEvidence,
    SourceAdapter,
    SourceMetadata,
    SourceResult,
)
from app.sources.http_client import get_httpx_client


class WikidataAdapter(SourceAdapter):
    """
    Adapter for querying Wikidata entities, company profiles, and public details.
    """

    @property
    def metadata(self) -> SourceMetadata:
        return SourceMetadata(
            name="wikidata",
            category="company",
            reliability_tier="REPUTABLE",
            is_passive=True,
            rate_limit_per_minute=60,
            timeout_seconds=15,
        )

    async def search(self, query: str, limit: int = 5) -> SourceResult:
        url = "https://www.wikidata.org/w/api.php"
        params = {
            "action": "wbsearchentities",
            "search": query,
            "language": "en",
            "format": "json",
            "limit": limit,
        }

        try:
            async with get_httpx_client(timeout_seconds=self.metadata.timeout_seconds) as client:
                response = await client.get(url, params=params)
                response.raise_for_status()
                data = response.json()
        except Exception as exc:  # noqa: BLE001
            return SourceResult(
                success=False,
                source_name=self.metadata.name,
                query=query,
                error_message=f"Wikidata API error: {exc!s}",
            )

        search_results = data.get("search", [])
        if not search_results:
            return SourceResult(
                success=True,
                source_name=self.metadata.name,
                query=query,
                evidence=[],
                entities=[],
                relationships=[],
            )

        evidence_list: list[RawEvidence] = []
        entities: list[ExtractedEntity] = []
        relationships: list[ExtractedRelationship] = []

        for item in search_results:
            entity_id = item.get("id")
            label = item.get("label", query)
            description = item.get("description", "")
            item_url = item.get("concepturi", f"https://www.wikidata.org/wiki/{entity_id}")

            aliases = item.get("aliases", [])

            extracted_ent = ExtractedEntity(
                name=label,
                entity_type="COMPANY" if "company" in description.lower() or "corporation" in description.lower() else "ORGANIZATION",
                aliases=aliases,
                confidence=0.9,
                metadata={"wikidata_id": entity_id, "description": description},
            )
            entities.append(extracted_ent)

            if description:
                evidence_list.append(
                    RawEvidence(
                        source_name=self.metadata.name,
                        url=item_url,
                        extracted_snippet=f"{label}: {description}",
                        metadata={"wikidata_id": entity_id},
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
