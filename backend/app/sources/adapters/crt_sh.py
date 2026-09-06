import logging

import httpx

from app.sources.base import (
    ExtractedEntity,
    ExtractedRelationship,
    RawEvidence,
    SourceAdapter,
    SourceMetadata,
    SourceResult,
)
from app.sources.http_client import get_httpx_client

logger = logging.getLogger(__name__)


class CrtShAdapter(SourceAdapter):
    """
    Adapter for searching crt.sh Certificate Transparency logs.
    Passive certificate intelligence for domain targets.
    """

    @property
    def metadata(self) -> SourceMetadata:
        return SourceMetadata(
            name="crt_sh",
            category="certificate",
            reliability_tier="REPUTABLE",
            is_passive=True,
            rate_limit_per_minute=30,
            timeout_seconds=15,
        )

    async def fetch(self, target: str) -> SourceResult:
        return await self.search(target)

    async def search(self, query: str, limit: int = 50) -> SourceResult:
        domain = query.strip().lower().removeprefix("http://").removeprefix("https://").split("/")[0]
        url = f"https://crt.sh/?q=%.{domain}&output=json"

        try:
            async with get_httpx_client(timeout_seconds=self.metadata.timeout_seconds) as client:
                response = await client.get(url)
                response.raise_for_status()
                data = response.json()
        except httpx.HTTPStatusError as exc:
            return SourceResult(
                success=False,
                source_name=self.metadata.name,
                query=query,
                error_message=f"crt.sh HTTP {exc.response.status_code} error",
            )
        except Exception as exc:  # noqa: BLE001
            return SourceResult(
                success=False,
                source_name=self.metadata.name,
                query=query,
                error_message=f"crt.sh connection failed: {exc!s}",
            )

        if not isinstance(data, list):
            return SourceResult(
                success=False,
                source_name=self.metadata.name,
                query=query,
                error_message="crt.sh returned unexpected response format",
            )

        discovered_domains: set[str] = set()
        evidence_list: list[RawEvidence] = []
        entities: list[ExtractedEntity] = [
            ExtractedEntity(name=domain, entity_type="DOMAIN", confidence=1.0)
        ]
        relationships: list[ExtractedRelationship] = []

        for entry in data[:limit]:
            name_value = entry.get("name_value", "")
            issuer_name = entry.get("issuer_name", "")
            logged_at = entry.get("entry_timestamp")

            subdomains = [sub.strip() for sub in name_value.split("\n") if sub.strip()]
            for sub in subdomains:
                clean_sub = sub.lstrip("*.").lower()
                if clean_sub and clean_sub not in discovered_domains:
                    discovered_domains.add(clean_sub)
                    entities.append(ExtractedEntity(name=clean_sub, entity_type="DOMAIN", confidence=0.95))
                    relationships.append(
                        ExtractedRelationship(
                            source_entity=domain,
                            source_entity_type="DOMAIN",
                            target_entity=clean_sub,
                            target_entity_type="DOMAIN",
                            relationship_type="subdomain_of",
                            confidence=0.95,
                        )
                    )

            snippet = f"Certificate issued for {name_value} by {issuer_name}"
            evidence_list.append(
                RawEvidence(
                    source_name=self.metadata.name,
                    url=url,
                    extracted_snippet=snippet,
                    publication_date=logged_at,
                    metadata={"issuer": issuer_name, "id": entry.get("id")},
                )
            )

        return SourceResult(
            success=True,
            source_name=self.metadata.name,
            query=query,
            evidence=evidence_list[:10],
            entities=entities,
            relationships=relationships,
        )
