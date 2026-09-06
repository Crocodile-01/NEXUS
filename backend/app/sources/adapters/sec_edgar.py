from app.sources.base import (
    ExtractedEntity,
    RawEvidence,
    SourceAdapter,
    SourceMetadata,
    SourceResult,
)
from app.sources.http_client import get_httpx_client


class SecEdgarAdapter(SourceAdapter):
    """
    Adapter for SEC EDGAR public submissions and company ticker lookups.
    """

    @property
    def metadata(self) -> SourceMetadata:
        return SourceMetadata(
            name="sec_edgar",
            category="company",
            reliability_tier="OFFICIAL",
            is_passive=True,
            rate_limit_per_minute=10,
            timeout_seconds=15,
        )

    async def search(self, query: str, limit: int = 5) -> SourceResult:
        url = "https://www.sec.gov/files/company_tickers.json"

        try:
            sec_headers = {"User-Agent": "NEXUS OSINT Research Bot admin@nexus-research.org"}
            async with get_httpx_client(timeout_seconds=self.metadata.timeout_seconds, headers=sec_headers) as client:
                response = await client.get(url)
                response.raise_for_status()
                data = response.json()
        except Exception as exc:  # noqa: BLE001
            return SourceResult(
                success=False,
                source_name=self.metadata.name,
                query=query,
                error_message=f"SEC EDGAR connection error: {exc!s}",
            )

        query_lower = query.strip().lower()
        matched_companies = []

        for entry in data.values():
            title = entry.get("title", "")
            ticker = entry.get("ticker", "")
            cik_str = str(entry.get("cik_str", "")).zfill(10)

            if query_lower in title.lower() or query_lower == ticker.lower():
                matched_companies.append((title, ticker, cik_str))
                if len(matched_companies) >= limit:
                    break

        evidence_list: list[RawEvidence] = []
        entities: list[ExtractedEntity] = []

        for title, ticker, cik_str in matched_companies:
            cik_url = f"https://data.sec.gov/submissions/CIK{cik_str}.json"
            ent = ExtractedEntity(
                name=title,
                entity_type="COMPANY",
                aliases=[ticker] if ticker else [],
                confidence=1.0,
                metadata={"ticker": ticker, "cik": cik_str, "sec_url": cik_url},
            )
            entities.append(ent)

            evidence_list.append(
                RawEvidence(
                    source_name=self.metadata.name,
                    url=cik_url,
                    extracted_snippet=f"SEC official filing entity: {title} (Ticker: {ticker}, CIK: {cik_str})",
                    metadata={"cik": cik_str, "ticker": ticker},
                )
            )

        return SourceResult(
            success=True,
            source_name=self.metadata.name,
            query=query,
            evidence=evidence_list,
            entities=entities,
            relationships=[],
        )
