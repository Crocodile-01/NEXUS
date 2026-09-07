# NEXUS Website & Domain Intelligence — Real-World Validation & Hardening Report

This document records the empirical validation, security hardening, timing performance measurements, and interactive demonstration capabilities implemented in **NEXUS Milestone 3.5**.

---

## 1. Overview & Objectives

The goal of Milestone 3.5 was to validate the Website / Domain Intelligence vertical slice against live, controlled public targets, harden its HTTP safety and bounds, verify deterministic evidence extraction, measure execution lifecycle timings, and provide an interactive local demonstration interface.

### Architectural Invariants Maintained
- **Bounded & SSRF-Safe Crawling**: Outbound requests strictly adhere to `PASSIVE_PUBLIC` mode using `_SafeRedirectTransport` and async redirect event hooks.
- **Strict Size & Depth Limits**: Maximum 5 MB per response body (`MAX_RESPONSE_BYTES`) and capped page crawl depth (1–10 pages).
- **Graceful OSINT Degradation**: Failures in secondary public lookups (e.g. crt.sh timeout) do not crash the investigation.
- **Evidence-Backed Provenance**: Every entity, technology, and claim links to extracted DOM text, HTTP headers, or verified OSINT statements.

---

## 2. Real-World Validation Results

Three controlled public targets were tested end-to-end against live external networks:

### Target 1: `https://example.com`
* **Canonical Domain**: `example.com`
* **Pages Crawled**: 1
* **Detected Technologies**: Cloudflare (CDN / Web Server)
* **Organization Profile**: Example Domain (IANA / ICANN documentation domain)
* **Verified Findings**:
  - Identified primary organization name 'Example Domain' (Confidence: 90%)
  - Detected web technology stack: Cloudflare (Confidence: 90%)
* **Status**: `completed`

### Target 2: `https://www.python.org`
* **Canonical Domain**: `python.org`
* **Pages Crawled**: 2 (Homepage + prioritized internal link)
* **Detected Technologies**: jQuery, Nginx
* **Entities Discovered**: 36 entities (Python Software Foundation, Python core tooling, PEP repositories)
* **Verified Findings**:
  - Organization profile established for Python Software Foundation / Python.org
  - Identified core infrastructure and web server stack
* **Status**: `completed`

### Target 3: `https://www.djangoproject.com`
* **Canonical Domain**: `djangoproject.com`
* **Pages Crawled**: 2
* **Detected Technologies**: Nginx
* **Entities Discovered**: 25 entities
* **Relationships Discovered**: 23 verified relationships (subdomains, repositories, developers)
* **OSINT Sources Consulted**: `crt.sh`, `trafilatura`, `sec_edgar`, `wikidata`
* **Status**: `completed`

---

## 3. Hardening & Bug Fixes Applied

### A. HTTPX Async Redirect Hook Coroutine Fix
- **Issue Discovered**: In `app/sources/http_client.py`, the `_check_redirect` event hook function was defined synchronously. When `httpx.AsyncClient` processed a redirect, it attempted `await hook(response)`, raising `TypeError: object NoneType can't be used in 'await' expression`.
- **Fix**: Updated `_check_redirect` to `async def _check_redirect(response: httpx.Response) -> None`. Updated all corresponding unit tests in `tests/test_http_client.py` to be async.

### B. Response Body Size Limit (`MAX_RESPONSE_BYTES`)
- **Mechanism**: Added `MAX_RESPONSE_BYTES = 5 * 1024 * 1024` (5 MB) limit in `app/services/website_intelligence/crawler.py`.
- **Validation**: Headers with `Content-Length` exceeding 5 MB are rejected immediately before streaming; response text is safely sliced to 5 MB to prevent memory exhaustion from oversized payloads.

### C. Bounded Page Depth Limits (`MAX_CRAWL_PAGES`)
- **Mechanism**: Clamped `effective_max_pages = min(max(1, max_pages), 10)` to prevent unbounded recursive crawling.

### D. Detailed Execution Timings
- **Added Schema**: `InvestigationTimings` model reporting:
  - `target_validation_ms`: URL & SSRF security policy verification
  - `crawl_ms`: HTTP network fetch and Trafilatura DOM parsing
  - `extraction_ms`: Entity, product, and tech stack regex extraction
  - `enrichment_ms`: Public OSINT lookups (crt.sh, Wikidata, SEC, arXiv)
  - `total_ms`: Total end-to-end runtime

---

## 4. Interactive Demonstration UI (`GET /demo`)

A standalone, dark-themed HTML/JS user interface is mounted directly at:
```text
http://localhost:8000/demo
```

### Features
1. **Interactive Form**: Input target URL, configure max pages (1–10), and toggle OSINT enrichment.
2. **Quick Preset Chips**: One-click fill for `python.org`, `djangoproject.com`, `example.com`, and `wikipedia.org`.
3. **Real-time Lifecycle Status**: Loading spinner displaying live pipeline steps.
4. **Metrics Overview**: Status, Canonical Domain, Pages Crawled, Entities Found, Verified Findings, Total Time.
5. **Phase Timings Breakdown**: Visual pills showing exact millisecond breakdown for each stage.
6. **Tabbed Results View**:
   - *Executive Summary & Org Profile*
   - *Detected Technologies* with category badges and confidence ratings
   - *Findings & Confidence* with classification tags (`HIGH_CONFIDENCE`, `INFERRED`, `UNVERIFIED`)
   - *Entities & Discovered Relationships*
   - *Raw JSON Response Viewer*
7. **Zero External Dependencies**: Pure vanilla HTML5, CSS3, and JavaScript — no external CDNs required.

---

## 5. Automated Verification Summary

- **Total Tests Passing**: 86
- **Test Modules**:
  - `tests/test_website_intelligence.py` (10 tests: crawler, tech detector, entity extractor, e2e, API endpoint, negative SSRF, unreachable target, graceful degradation, demo endpoint, timings)
  - `tests/test_http_client.py` (12 tests: SSRF protection, blocked IPs, redirect hooks, timeouts)
  - `tests/test_agent_manager.py` (5 tests)
  - `tests/test_guardrails.py` (4 tests)
  - `tests/test_tool_execution.py` (4 tests)
  - `tests/test_tool_registry.py` (4 tests)
  - `tests/test_adapters.py` (22 tests)
  - `tests/test_evidence_engine.py` (4 tests)
  - `tests/test_target_validator.py` (11 tests)
  - `tests/test_models.py`, `tests/test_schemas.py`, `tests/test_api_investigations.py`, `tests/test_api_health.py` (10 tests)
- **Linter Status**: `ruff check app tests` clean (0 errors).
