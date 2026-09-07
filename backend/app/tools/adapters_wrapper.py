from __future__ import annotations

import logging

from app.security.execution_scope import ExecutionMode
from app.sources.adapters.arxiv import ArxivAdapter
from app.sources.adapters.crt_sh import CrtShAdapter
from app.sources.adapters.sec_edgar import SecEdgarAdapter
from app.sources.adapters.semantic_scholar import SemanticScholarAdapter
from app.sources.adapters.trafilatura_extractor import TrafilaturaAdapter
from app.sources.adapters.wikidata import WikidataAdapter
from app.sources.base import ExtractedEntity, SourceResult
from app.tools.base import RegisteredTool, ToolRequest, ToolResult
from app.tools.registry import tool_registry

logger = logging.getLogger(__name__)

# Initialize underlying adapters
_crt_sh = CrtShAdapter()
_wikidata = WikidataAdapter()
_sec_edgar = SecEdgarAdapter()
_arxiv = ArxivAdapter()
_semantic_scholar = SemanticScholarAdapter()
_trafilatura = TrafilaturaAdapter()


# ---------------------------------------------------------------------------
# 1. Certificate Transparency Tool
# ---------------------------------------------------------------------------
async def _exec_crt_sh(request: ToolRequest) -> ToolResult:
    res: SourceResult = await _crt_sh.search(request.target)
    return ToolResult(
        success=res.success,
        tool_name="lookup_certificate_transparency",
        target=request.target,
        output_data={
            "subdomains_found": [e.name for e in res.entities if e.entity_type == "DOMAIN"],
            "evidence_count": len(res.evidence),
        },
        source_result=res,
        error_message=res.error_message,
    )


# ---------------------------------------------------------------------------
# 2. Wikidata Tool
# ---------------------------------------------------------------------------
async def _exec_wikidata(request: ToolRequest) -> ToolResult:
    res: SourceResult = await _wikidata.search(request.target)
    return ToolResult(
        success=res.success,
        tool_name="search_wikidata",
        target=request.target,
        output_data={
            "entities": [{"name": e.name, "type": e.entity_type, "aliases": e.aliases} for e in res.entities],
            "evidence_count": len(res.evidence),
        },
        source_result=res,
        error_message=res.error_message,
    )


# ---------------------------------------------------------------------------
# 3. SEC EDGAR Tool
# ---------------------------------------------------------------------------
async def _exec_sec_edgar(request: ToolRequest) -> ToolResult:
    res: SourceResult = await _sec_edgar.search(request.target)
    return ToolResult(
        success=res.success,
        tool_name="lookup_sec_company",
        target=request.target,
        output_data={
            "entities": [{"name": e.name, "type": e.entity_type, "cik": e.metadata.get("cik")} for e in res.entities],
            "evidence_count": len(res.evidence),
        },
        source_result=res,
        error_message=res.error_message,
    )


# ---------------------------------------------------------------------------
# 4. arXiv Academic Tool
# ---------------------------------------------------------------------------
async def _exec_arxiv(request: ToolRequest) -> ToolResult:
    res: SourceResult = await _arxiv.search(request.target, limit=request.limit)
    return ToolResult(
        success=res.success,
        tool_name="search_arxiv",
        target=request.target,
        output_data={
            "papers_found": [e.name for e in res.entities if e.entity_type == "RESEARCH_PAPER"],
            "authors_found": [e.name for e in res.entities if e.entity_type == "PERSON"],
            "evidence_count": len(res.evidence),
        },
        source_result=res,
        error_message=res.error_message,
    )


# ---------------------------------------------------------------------------
# 5. Semantic Scholar Tool
# ---------------------------------------------------------------------------
async def _exec_semantic_scholar(request: ToolRequest) -> ToolResult:
    res: SourceResult = await _semantic_scholar.search(request.target, limit=request.limit)
    return ToolResult(
        success=res.success,
        tool_name="search_semantic_scholar",
        target=request.target,
        output_data={
            "papers_found": [e.name for e in res.entities if e.entity_type == "RESEARCH_PAPER"],
            "evidence_count": len(res.evidence),
        },
        source_result=res,
        error_message=res.error_message,
    )


# ---------------------------------------------------------------------------
# 6. Fetch Webpage Tool
# ---------------------------------------------------------------------------
async def _exec_fetch_webpage(request: ToolRequest) -> ToolResult:
    res: SourceResult = await _trafilatura.fetch(request.target)
    snippet = res.evidence[0].extracted_snippet if res.evidence else ""
    return ToolResult(
        success=res.success,
        tool_name="fetch_webpage",
        target=request.target,
        output_data={
            "snippet": snippet[:1000],
            "full_snippet_length": len(snippet),
            "evidence_count": len(res.evidence),
        },
        source_result=res,
        error_message=res.error_message,
    )


# ---------------------------------------------------------------------------
# 7. Extract Web Content Tool
# ---------------------------------------------------------------------------
async def _exec_extract_web_content(request: ToolRequest) -> ToolResult:
    res: SourceResult = await _trafilatura.fetch(request.target)
    return ToolResult(
        success=res.success,
        tool_name="extract_web_content",
        target=request.target,
        output_data={
            "entities": [{"name": e.name, "type": e.entity_type} for e in res.entities],
            "relationships": [
                {"source": r.source_entity, "relation": r.relationship_type, "target": r.target_entity}
                for r in res.relationships
            ],
            "evidence_count": len(res.evidence),
        },
        source_result=res,
        error_message=res.error_message,
    )


# ---------------------------------------------------------------------------
# 8. Deterministic Entity Resolution Tool
# ---------------------------------------------------------------------------
async def _exec_resolve_entity(request: ToolRequest) -> ToolResult:
    ext_entity = ExtractedEntity(
        name=request.target,
        entity_type=request.target_type.upper() if request.target_type != "general" else "UNKNOWN",
        aliases=request.params.get("aliases", []),
    )
    return ToolResult(
        success=True,
        tool_name="resolve_entity",
        target=request.target,
        output_data={
            "normalized_name": ext_entity.name.strip().lower(),
            "entity_type": ext_entity.entity_type,
            "status": "ready_for_resolution",
        },
        error_message=None,
    )


def register_native_tools() -> None:
    """Register all native NEXUS source adapter tools into the global ToolRegistry."""
    tools = [
        RegisteredTool(
            name="lookup_certificate_transparency",
            description="Search Certificate Transparency logs (crt.sh) for domains, subdomains, and TLS certificate identities.",
            category="certificate",
            func=_exec_crt_sh,
            timeout=15,
            rate_limit=30,
            required_execution_mode=ExecutionMode.PASSIVE_PUBLIC,
            risk_level="LOW",
        ),
        RegisteredTool(
            name="search_wikidata",
            description="Search Wikidata for structured company profiles, aliases, headquarters, and official identifiers.",
            category="company",
            func=_exec_wikidata,
            timeout=15,
            rate_limit=60,
            required_execution_mode=ExecutionMode.PASSIVE_PUBLIC,
            risk_level="LOW",
        ),
        RegisteredTool(
            name="lookup_sec_company",
            description="Search SEC EDGAR database for public company CIK numbers, ticker symbols, and official filings.",
            category="company",
            func=_exec_sec_edgar,
            timeout=15,
            rate_limit=10,
            required_execution_mode=ExecutionMode.PASSIVE_PUBLIC,
            risk_level="LOW",
        ),
        RegisteredTool(
            name="search_arxiv",
            description="Search arXiv academic repository for research papers, authors, abstracts, and technology topics.",
            category="academic",
            func=_exec_arxiv,
            timeout=15,
            rate_limit=30,
            required_execution_mode=ExecutionMode.PASSIVE_PUBLIC,
            risk_level="LOW",
        ),
        RegisteredTool(
            name="search_semantic_scholar",
            description="Search Semantic Scholar for academic publications, citations, and scholarly affiliations.",
            category="academic",
            func=_exec_semantic_scholar,
            timeout=15,
            rate_limit=30,
            required_execution_mode=ExecutionMode.PASSIVE_PUBLIC,
            risk_level="LOW",
        ),
        RegisteredTool(
            name="fetch_webpage",
            description="Fetch a public webpage URL and extract clean, readable text content using Trafilatura.",
            category="web",
            func=_exec_fetch_webpage,
            timeout=15,
            rate_limit=60,
            required_execution_mode=ExecutionMode.PASSIVE_PUBLIC,
            risk_level="LOW",
        ),
        RegisteredTool(
            name="extract_web_content",
            description="Fetch a public webpage and extract structured entities and relationship mentions.",
            category="web",
            func=_exec_extract_web_content,
            timeout=15,
            rate_limit=60,
            required_execution_mode=ExecutionMode.PASSIVE_PUBLIC,
            risk_level="LOW",
        ),
        RegisteredTool(
            name="resolve_entity",
            description="Deterministically normalize and resolve an entity name and type against known records.",
            category="entity",
            func=_exec_resolve_entity,
            timeout=5,
            rate_limit=120,
            required_execution_mode=ExecutionMode.PASSIVE_PUBLIC,
            risk_level="LOW",
        ),
    ]

    for tool in tools:
        if not tool_registry.get(tool.name):
            tool_registry.register(tool)


# Automatically register native tools on import
register_native_tools()
