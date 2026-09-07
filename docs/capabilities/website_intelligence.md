# NEXUS — Website / Domain Intelligence Research Capability

This document specifies the architecture, operational workflow, evidentiary standards, and guardrail policies of the NEXUS Website Intelligence vertical slice.

---

## 1. Overview & Capability Objective

The **Website / Domain Intelligence Research** capability provides autonomous, passive, and evidence-first investigation of a public website or domain (e.g. `https://example.com` or `example.com`).

Given a target, NEXUS conducts a bounded reconnaissance workflow to uncover:
- **Organization Identity**: Formal name, legal structure, description, primary domains, and social profiles.
- **Key Personnel**: Publicly named executives, founders, and directors with role attributions.
- **Products & Projects**: Commercial products, software platforms, and open-source repositories.
- **Technology Stack**: Passively detected web frameworks, CMS engines, server infrastructure, programming languages, and cloud providers.
- **Relationships**: Typed entity edges (`operates`, `develops`, `employs`, `uses`, `maintains_repository`, `has_subdomain`).
- **External OSINT Enrichment**: Subdomains (via Certificate Transparency logs), Wikidata corporate profiles/aliases, SEC EDGAR filings/CIK numbers, and arXiv academic publications.
- **Confidence Assessment & Timeline**: Every claim classified into strict evidentiary tiers (`FACT`, `SUPPORTED_INFERENCE`, `UNVERIFIED`) with supporting snippets and temporal anchors.

---

## 2. Investigation Workflow

The website intelligence workflow executes deterministically through eight sequential phases:

```text
       Target URL / Domain
               │
               ▼
       1. VALIDATE & NORMALIZE
          • URL/FQDN syntax check
          • PASSIVE_PUBLIC SSRF & private IP check
               │
               ▼
       2. BOUNDED WEB CRAWL
          • Fetch homepage via safe HTTP client
          • Discover & rank internal links (/about, /products, /team, /docs)
          • Crawl up to max_pages (default: 3)
               │
               ▼
       3. CONTENT & METADATA EXTRACTION
          • Clean text extraction via Trafilatura
          • DOM & metadata parsing (title, meta generator, scripts, links)
               │
               ▼
       4. PASSIVE TECHNOLOGY DETECTION
          • Detect CMS, JS frameworks, web servers, cloud CDNs
          • Classify detections: EXPLICIT, DETECTED, INFERRED
               │
               ▼
       5. ENTITY & RELATIONSHIP EXTRACTION
          • Extract company name, executives, products, GitHub repos
          • Formulate evidentiary relationships with source URLs
               │
               ▼
       6. PUBLIC-SOURCE ENRICHMENT
          • crt.sh: Certificate Transparency subdomain discovery
          • Wikidata: Corporate profiles, aliases, inception dates
          • SEC EDGAR: Official CIK filings (if applicable)
          • arXiv: Academic papers (if research signals present)
               │
               ▼
       7. VERIFICATION & CONFIDENCE SCORING
          • Classify findings: FACT (0.85–0.98), SUPPORTED_INFERENCE (0.75–0.88), UNVERIFIED (<0.5)
          • Ingest evidence & entities into database with content hashes
               │
               ▼
       8. INTELLIGENCE REPORT SYNTHESIS
          • Generate comprehensive WebsiteIntelligenceReport
          • Outline research gaps & audit log
```

---

## 3. Supported Sources & Adapters

| Source | Role | Reliability Tier | Security Controls |
| :--- | :--- | :--- | :--- |
| **Trafilatura / Web Crawler** | Primary website text, internal page crawling, and link discovery | `THIRD_PARTY` | Safe HTTPX client with redirect & private network blocking |
| **crt.sh** | Public Certificate Transparency logs, TLS history, subdomains | `REPUTABLE` | Passive query via official web API |
| **Wikidata** | Corporate entity resolution, aliases, headquarters, inception dates | `REPUTABLE` | Public SPARQL / REST API query |
| **SEC EDGAR** | US public company filings, central index keys (CIK), and tickers | `OFFICIAL` | Public submissions directory API |
| **arXiv** | Scientific publications, author names, academic research focus | `REPUTABLE` | Public Atom XML API |

---

## 4. Evidentiary Standards & Finding Classifications

NEXUS forbids asserting uncorroborated assertions or model hallucinations as truth. Findings are strictly partitioned:

1. **`FACT`** (Confidence: `0.90 – 0.99`):
   - Direct statements extracted from official website text (e.g. *"Acme Corp develops CloudAI"*).
   - Verifiable TLS certificates from crt.sh (e.g. *"Subdomain api.example.com discovered in CT logs"*).
   - Explicit technology signatures in HTML DOM or headers (e.g. *"Server: cloudflare"*).

2. **`SUPPORTED_INFERENCE`** (Confidence: `0.70 – 0.89`):
   - Relational deductions from text context (e.g. *"Jane Doe is affiliated with Acme Corp as CEO based on team page"*).
   - Inferred secondary technologies (e.g. *"Next.js detection implies underlying React framework"*).

3. **`UNVERIFIED`** (Confidence: `< 0.50`):
   - Uncorroborated leads, speculative references, or failed source queries.

---

## 5. Technology Detection Matrix

Technologies are passively identified without active port scanning or vulnerability probing:

| Detection Channel | Example Signal | Technology Detected | Classification |
| :--- | :--- | :--- | :--- |
| **Meta Generator** | `<meta name="generator" content="WordPress 6.4">` | WordPress | `DETECTED` |
| **Script Assets** | `<script src="/_next/static/chunks/main.js">` | Next.js | `DETECTED` |
| **Script Assets** | `<script src="/static/js/react.production.min.js">` | React | `DETECTED` |
| **HTTP Headers** | `Server: cloudflare` | Cloudflare | `DETECTED` |
| **HTTP Headers** | `X-Powered-By: Express` | Express.js | `DETECTED` |
| **Explicit Text** | *"Our backend is powered by FastAPI and PyTorch"* | FastAPI, PyTorch | `EXPLICIT` |
| **Architectural Inference** | WordPress CMS detected | PHP | `INFERRED` |

---

## 6. Execution Bounding & Security Policies

- **Bounded Crawl**: Crawls a maximum of `max_pages` (default: 3, absolute maximum: 10).
- **Execution Time Limits**: Standard per-request timeout of 15 seconds.
- **SSRF & Private IP Rejection**: All URLs resolving to RFC 1918 private IP spaces (`10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`), loopback (`127.0.0.1`, `::1`), link-local (`169.254.0.0/16`), or non-HTTP schemes are rejected by the transport layer before connection establishment.
- **No Active Probing**: No port scanning, directory brute-forcing, credential stuffing, or exploit attempts.

---

## 7. API Usage Example

### Request
```http
POST /api/v1/investigations/website HTTP/1.1
Host: localhost:8000
Content-Type: application/json

{
  "target": "https://example.com",
  "objective": "Identify company profile, technology stack, and leadership",
  "max_pages": 3,
  "enrich": true
}
```

### Response
```json
{
  "investigation_id": "b3e944d1-c1e4-41b9-9cf9-e93cf824db21",
  "status": "completed",
  "target": "https://example.com",
  "canonical_domain": "example.com",
  "tasks_count": 2,
  "findings_count": 7,
  "evidence_count": 3,
  "entities_count": 5,
  "relationships_count": 4,
  "report": {
    "target_url": "https://example.com",
    "canonical_domain": "example.com",
    "investigation_id": "b3e944d1-c1e4-41b9-9cf9-e93cf824db21",
    "executive_summary": "Passive reconnaissance of 'example.com' identified organization 'Example Corp'...",
    "organization_profile": {
      "name": "Example Corp",
      "description": "Provider of cloud computing platforms.",
      "website_url": "https://example.com",
      "canonical_domain": "example.com",
      "domains": ["example.com", "api.example.com"],
      "products_services": ["CloudPlatform"]
    },
    "people_and_organizations": [
      {
        "name": "Jane Doe",
        "entity_type": "PERSON",
        "role_or_title": "CEO",
        "confidence": 0.88
      }
    ],
    "technologies": [
      {
        "name": "Next.js",
        "category": "React Framework",
        "classification": "DETECTED",
        "confidence": 0.95
      }
    ],
    "findings": [
      {
        "claim": "Website 'example.com' is operated by organization 'Example Corp'.",
        "classification": "FACT",
        "confidence_score": 0.98
      }
    ],
    "research_gaps": [
      "Entity has no matching US SEC EDGAR filings (likely private or non-US entity)."
    ]
  }
}
```

---

## 8. Known Limitations

1. **JavaScript-Rendered Content (SPAs)**: Highly dynamic Single Page Applications requiring client-side JavaScript execution are ingested via static HTML extraction (Trafilatura/lxml); full headless browser rendering is deferred to a future phase.
2. **Obfuscated Technologies**: Technologies that do not expose public script URLs, meta tags, or HTTP response headers cannot be detected passively.
3. **Paywalls & Authentication**: Protected intranet pages or gated paywalls are intentionally not bypassed under the `PASSIVE_PUBLIC` security policy.
