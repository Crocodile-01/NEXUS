# NEXUS Source Adapter Contract & Registry Architecture

This document describes the design and specification for modular source adapters in NEXUS.

---

## 1. SourceAdapter Interface Contract

Every source adapter in `app/sources/adapters/` inherits from `SourceAdapter` (`app/sources/base.py`) and implements:

```python
class SourceAdapter(ABC):
    @property
    @abstractmethod
    def metadata(self) -> SourceMetadata:
        """Metadata detailing source name, category, reliability tier, passive capability, rate limit."""
        pass

    async def search(self, query: str, limit: int = 10) -> SourceResult:
        """Query external public API or service."""
        ...

    async def fetch(self, target: str) -> SourceResult:
        """Fetch details for a specific URL or identifier."""
        ...
```

### Data Models & Schemas

- **`RawEvidence`**: Holds normalized text snippet, source URL, publication date, content hash (SHA-256 auto-generated), and provider metadata.
- **`ExtractedEntity`**: Canonical name, entity type (`COMPANY`, `PERSON`, `DOMAIN`, `IP`, `RESEARCH_PAPER`, `TECHNOLOGY`, `PROJECT`), aliases, and confidence score.
- **`ExtractedRelationship`**: Source entity name/type, target entity name/type, relationship type (`subdomain_of`, `authored`, `ceo_of`, `develops`, `uses`), confidence score.
- **`SourceResult`**: Execution status (`success: bool`), query parameter, error message if failed, and lists of extracted evidence, entities, and relationships.

---

## 2. Implemented Native Adapters

| Adapter Name | Category | Reliability Tier | Passive Only | Rate Limit (req/min) | Primary Functionality |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `crt_sh` | Certificate | REPUTABLE | Yes | 30 | Certificate Transparency logs & subdomain extraction |
| `wikidata` | Company/Org | REPUTABLE | Yes | 60 | Company profile, official names & aliases lookup |
| `sec_edgar` | Company | OFFICIAL | Yes | 10 | SEC EDGAR CIK numbers, tickers & official entity filings |
| `arxiv` | Academic | REPUTABLE | Yes | 30 | Research paper abstracts & author entity extraction |
| `semantic_scholar` | Academic | REPUTABLE | Yes | 30 | Academic paper search, author & citation metadata |
| `trafilatura` | Web | THIRD_PARTY | Yes | 60 | Webpage HTML fetch & clean text/markdown extraction |

---

## 3. Evidence Engine & Entity Resolution Pipeline

When a `SourceResult` is returned by an adapter:
1. **Source Record**: Upserts a `Source` record into the database.
2. **Deduplication**: Hashes the snippet with SHA-256 (`content_hash`) to avoid storing duplicate evidence.
3. **Deterministic Entity Resolution**: Resolves entities against existing DB records via:
   - Exact Canonical Name match
   - Alias match
   - Normalized comparison
   - RapidFuzz `WRatio` matching (score ≥ 85%)
4. **Relationship Persistence**: Links source and target entities in the `relationships` table.

---

## 4. Security & Guardrails

- **Default Execution Mode**: `PASSIVE_PUBLIC` enforced across all adapters.
- **Target Validation**: `app/security/target_validator.py` validates URLs, domains, and IP formats, blocking RFC 1918 private IPs and `localhost` from outbound requests to prevent SSRF vulnerabilities.
- **Shared HTTP Client**: `app/sources/http_client.py` sets explicit connect/read timeouts (default 15s) and standard `NEXUS-OSINT-Platform` User-Agent header.
