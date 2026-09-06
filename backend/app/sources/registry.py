from app.sources.adapters.arxiv import ArxivAdapter
from app.sources.adapters.crt_sh import CrtShAdapter
from app.sources.adapters.sec_edgar import SecEdgarAdapter
from app.sources.adapters.semantic_scholar import SemanticScholarAdapter
from app.sources.adapters.trafilatura_extractor import TrafilaturaAdapter
from app.sources.adapters.wikidata import WikidataAdapter
from app.sources.base import SourceAdapter, SourceMetadata


class AdapterRegistry:
    """
    Central registry storing all active SourceAdapter implementations.
    """

    def __init__(self) -> None:
        self._adapters: dict[str, SourceAdapter] = {}

    def register(self, adapter: SourceAdapter) -> None:
        """Register a new SourceAdapter instance."""
        name = adapter.metadata.name
        self._adapters[name] = adapter

    def get(self, name: str) -> SourceAdapter | None:
        """Retrieve adapter by name."""
        return self._adapters.get(name)

    def list_adapters(self) -> list[SourceMetadata]:
        """List metadata for all registered adapters."""
        return [adapter.metadata for adapter in self._adapters.values()]

    def get_adapters_by_category(self, category: str) -> list[SourceAdapter]:
        """Find adapters matching a functional category."""
        return [
            adapter for adapter in self._adapters.values() if adapter.metadata.category == category
        ]


# Default Global Registry instance with MVP native adapters initialized
registry = AdapterRegistry()
registry.register(CrtShAdapter())
registry.register(WikidataAdapter())
registry.register(SecEdgarAdapter())
registry.register(ArxivAdapter())
registry.register(SemanticScholarAdapter())
registry.register(TrafilaturaAdapter())
