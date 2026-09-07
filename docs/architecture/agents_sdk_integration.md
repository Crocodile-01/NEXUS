# NEXUS — OpenAI Agents SDK Integration Specification

This document records architectural decisions and compatibility findings for integrating the OpenAI Agents SDK (`openai-agents`) into NEXUS.

---

## 1. Overview & SDK Selection

- **Package**: `openai-agents` (version `0.22.0`)
- **Official Source**: `https://github.com/openai/openai-agents-python`
- **Python Compatibility**: Python >= 3.10 required.
- **Architectural Role in NEXUS**:
  - The OpenAI Agents SDK is utilized as the **agent orchestration layer**.
  - The **application layer retains absolute authority** over investigation state, tool execution policies, persistence, target validation, and evidence provenance.
  - The agent interacts with tools only through the **NEXUS Tool Execution Boundary**. It is never granted unrestricted, raw network or operating system access.

---

## 2. Critical Compatibility & Runtime Findings

### Python 3.11.0 Typing Generic Indexing Bug
During environment verification on Python 3.11.0, `agents.tool` encountered:
```text
File ".../agents/tool.py", line 93, in <module>
    | ToolFunctionWithToolContext[ToolParams]
KeyError: ~TContext
```
- **Root Cause**: `ToolContext` inherits from `RunContextWrapper[TContext]`. In Python 3.11.0, subscripting a parameterized `Callable[Concatenate[ToolContext, ToolParams], Any]` without explicitly parameterizing `ToolContext[Any]` fails in `typing._determine_new_args` due to a known PEP 695 typing bug in Python 3.11.0 (subsequently fixed in Python >= 3.11.2).
- **Resolution**:
  - In `agents/tool.py`, `ToolFunctionWithToolContext` must be defined as `Callable[Concatenate[ToolContext[Any], ToolParams], Any]`.
  - Production deployments should use Python >= 3.11.2 or Python 3.12+ where this typing bug is fixed in the standard library.

---

## 3. Manager/Planner Agent Architecture

Rather than launching multiple autonomous agents that communicate recursively or initiate unbounded loops, NEXUS implements a **Manager-style architecture**:

```text
               NEXUS API (FastAPI)
                       │
                       ▼
             Investigation Manager
           (app/agents/manager.py)
                       │
             ┌─────────┴─────────┐
             │                   │
             ▼                   ▼
    OpenAI Agents SDK       NEXUS Database
     (Agent + Runner)      (Investigation, Tasks,
             │              AgentRuns, Findings)
             ▼
     Registered Tools
     (@function_tool)
             │
             ▼
  Tool Execution Boundary
  (Guardrails + Validation)
             │
             ▼
      Source Adapters
```

### Key Principles
1. **Single Point of Control**: The Manager Agent oversees a specific investigation objective and task.
2. **Specialists as Tools**: Subordinate capabilities (e.g. Wikidata lookups, SEC EDGAR searches, arXiv paper discovery, certificate transparency checks) are exposed to the Manager as typed tools, not as autonomous background agents.
3. **Structured Outputs**: The Manager produces structured, typed results adhering to `AgentRunResult` and `AgentFinding`.

---

## 4. Structured Output Classification

To eliminate hallucinations and prevent the LLM from asserting speculative inferences as verified facts, all findings extracted or formulated by agents must be strictly classified into three explicit tiers:

| Tier | Meaning | Verification Requirement |
| :--- | :--- | :--- |
| `FACT` | Direct empirical statement extracted from verified source evidence. | Must cite a valid `evidence_id` or verifiable source URL. |
| `SUPPORTED_INFERENCE` | Logical deduction or correlation derived from one or more verified facts. | Must cite underlying supporting evidence snippets or entities. |
| `UNVERIFIED` | Hypothesis, lead, or claim requiring further research or corroboration. | Cannot be treated as ground truth in intelligence reports. |

The LLM is explicitly forbidden from silently upgrading `SUPPORTED_INFERENCE` or `UNVERIFIED` claims to `FACT`.

---

## 5. Security & Guardrail Flow

The agent cannot bypass security:
1. **SDK Level**: Tools registered with `@function_tool` are configured with strict JSON schemas and bounded execution parameters.
2. **NEXUS Boundary Level**: All tool invocations must route through `ToolExecutionBoundary.execute()`.
3. **Guardrail Check**: The boundary executes `validate_tool_call()` to verify:
   - Target validity (FQDN format, IP range, URL scheme).
   - Execution mode compliance (`PASSIVE_PUBLIC` blocks RFC 1918 private IPs, localhost, and active operations).
   - Elevated authorization requirements (`AUTHORIZED_SECURITY_ASSESSMENT` requires an explicit, verified `ExecutionScope`).
4. **Transport Level**: Safe HTTP transport blocks internal network destinations and malicious redirects beneath the SDK.

---

## 6. Current Limitations & Future Roadmap

- **Phase 3 Scope**: Initial Manager agent invocation, tool boundary execution, structured finding extraction, and tool execution logging.
- **Deferred to Later Phases**:
  - Recursive multi-turn investigation expansion.
  - Multi-agent handoffs between specialist agents.
  - Neo4j graph synchronization.
  - Active scanning / network reconnaissance.
