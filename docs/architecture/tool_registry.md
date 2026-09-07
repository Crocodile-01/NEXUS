# NEXUS Tool Registry & Execution Boundary Architecture

This document specifies the design, lifecycle, and guardrail policies of the NEXUS Tool Registry and Execution Boundary.

---

## 1. Architectural Philosophy

NEXUS does not give LLM agents direct, unrestricted access to Python runtimes, operating system shells, or unconstrained HTTP libraries.

Instead, all tool execution proceeds through a **strictly bounded, typed, and auditable pipeline**:

```text
Agent (LLM via OpenAI Agents SDK)
  │
  ▼
Registered Tool (@function_tool adapter)
  │
  ▼
Tool Execution Boundary (app/tools/boundary.py)
  │
  ├─► Guardrail Policy Validation (app/guardrails/tool_guardrails.py)
  │     • Validates target syntax & safety (FQDN, URL, IP)
  │     • Enforces ExecutionScope (PASSIVE_PUBLIC vs AUTHORIZED_SECURITY_ASSESSMENT)
  │     • Checks rate limits & timeout bounds
  │
  ├─► Source Adapter Invocations (app/sources/adapters/*)
  │     • Shared safe HTTP client (SSRF prevention, redirect filters)
  │     • Returns normalized SourceResult
  │
  ├─► Evidence Engine Ingestion (app/services/evidence_engine.py)
  │     • Content hashing (SHA-256 deduplication)
  │     • Entity resolution & relationship extraction
  │
  ├─► Audit Logging (ToolExecution DB Record)
  │     • Captures input parameters, output summary, execution time ms, status
  │
  ▼
Structured ToolResult returned to Agent
```

---

## 2. Tool Registry Specification

The `ToolRegistry` (`app/tools/registry.py`) is an application-level catalog independent of any LLM or SDK.

### RegisteredTool Metadata
Each registered tool is defined by a `RegisteredTool` instance with the following typed metadata:

- `name`: Unique identifier (e.g., `search_wikidata`, `lookup_sec_company`).
- `description`: Plaintext description explaining the capability and ideal usage context.
- `category`: Functional category (`company`, `academic`, `certificate`, `web`, `entity`).
- `input_schema`: Pydantic schema defining expected input parameters (`ToolRequest`).
- `output_schema`: Pydantic schema defining tool response structure (`ToolResult`).
- `required_execution_mode`: Minimal execution mode (`PASSIVE_PUBLIC` by default).
- `risk_level`: Safety classification (`LOW`, `MEDIUM`, `HIGH`).
- `timeout`: Maximum allowed execution duration in seconds.
- `rate_limit`: Maximum allowed calls per minute.
- `enabled`: Boolean flag allowing tools to be toggled on/off dynamically.

### Rejection Policies
- **Duplicate Registration**: Attempting to register a tool with an existing name raises a `ValueError`.
- **Disabled Tools**: Invocations of disabled tools are rejected immediately by the execution boundary.

---

## 3. Implemented Native Tools

All Phase 2 source adapters are wrapped as first-class registered tools:

| Tool Name | Wrapped Component | Category | Risk | Default Mode | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `lookup_certificate_transparency` | `CrtShAdapter` | `certificate` | `LOW` | `PASSIVE_PUBLIC` | Queries Certificate Transparency logs for subdomains and identity certificates. |
| `search_wikidata` | `WikidataAdapter` | `company` | `LOW` | `PASSIVE_PUBLIC` | Retrieves structured company and organization profiles, aliases, and identifiers. |
| `lookup_sec_company` | `SecEdgarAdapter` | `company` | `LOW` | `PASSIVE_PUBLIC` | Queries SEC EDGAR company database for official CIKs, tickers, and filings. |
| `search_arxiv` | `ArxivAdapter` | `academic` | `LOW` | `PASSIVE_PUBLIC` | Searches arXiv for academic research papers, authors, and abstracts. |
| `search_semantic_scholar` | `SemanticScholarAdapter` | `academic` | `LOW` | `PASSIVE_PUBLIC` | Queries Semantic Scholar for papers, citations, and author affiliations. |
| `fetch_webpage` | `TrafilaturaAdapter` | `web` | `LOW` | `PASSIVE_PUBLIC` | Fetches a public webpage and extracts clean, readable text. |
| `extract_web_content` | `TrafilaturaAdapter` | `web` | `LOW` | `PASSIVE_PUBLIC` | Extracts entities and structured text snippets from raw HTML content. |
| `resolve_entity` | `resolve_entity` | `entity` | `LOW` | `PASSIVE_PUBLIC` | Deterministically resolves and deduplicates entities against known records. |

---

## 4. Tool Guardrails & Execution Modes

The guardrail layer (`app/guardrails/tool_guardrails.py`) sits directly in the tool execution path:

### PASSIVE_PUBLIC (Default)
- Target strings must validate against `validate_target()` under `ExecutionScope.passive_public()`.
- Private IP addresses (`10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`, `127.0.0.0/8`, `169.254.0.0/16`) are strictly rejected.
- URLs must use `http` or `https` schemes; localhost and private hostnames are blocked.
- Only passive collection tools are permitted.

### AUTHORIZED_SECURITY_ASSESSMENT
- Mode string alone is never sufficient authorization.
- Must be accompanied by an `ExecutionScope` where `scope.is_elevated` is `True` with verified `authorized_domains` or `authorized_ips`.
- Target must be explicitly present in the authorized scope list.

---

## 5. Audit Logging & State Tracking

Whenever an investigation task invokes a tool:
1. A timer records execution duration (`execution_time_ms`).
2. An entry in the `tool_executions` table is committed with:
   - `task_id`
   - `tool_name`
   - `execution_mode`
   - `input_params`
   - `output_result`
   - `status` (`success` or `failed`)
   - `execution_time_ms`
   - `executed_at`

---

## 6. Extension Points

To add a new tool to NEXUS:
1. Implement the underlying capability in a `SourceAdapter` or utility service.
2. Define a typed `BaseModel` for the tool input.
3. Instantiate a `RegisteredTool` and register it with `tool_registry.register(new_tool)`.
4. The tool will automatically be discoverable by both the application API and the OpenAI Agents SDK Manager.
