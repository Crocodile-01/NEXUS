from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from app.sources.adapters.arxiv import ArxivAdapter
from app.sources.adapters.crt_sh import CrtShAdapter
from app.sources.adapters.sec_edgar import SecEdgarAdapter
from app.sources.adapters.semantic_scholar import SemanticScholarAdapter
from app.sources.adapters.trafilatura_extractor import TrafilaturaAdapter
from app.sources.adapters.wikidata import WikidataAdapter
from app.sources.registry import AdapterRegistry, registry


@pytest.mark.asyncio
async def test_crt_sh_adapter_mocked():
    mock_data = [
        {
            "id": 12345,
            "issuer_name": "C=US, O=DigiCert Inc",
            "name_value": "nvidia.com\nwww.nvidia.com\napi.nvidia.com",
            "entry_timestamp": "2024-01-01T00:00:00",
        }
    ]

    mock_client = AsyncMock()
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.raise_for_status = MagicMock()
    mock_response.json = MagicMock(return_value=mock_data)
    mock_client.get = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    adapter = CrtShAdapter()

    with patch("app.sources.adapters.crt_sh.get_httpx_client", return_value=mock_client):
        result = await adapter.search("nvidia.com")

    assert result.success is True
    assert result.source_name == "crt_sh"
    assert len(result.evidence) >= 1
    assert len(result.entities) >= 2
    domain_names = [e.name for e in result.entities]
    assert "nvidia.com" in domain_names
    assert "api.nvidia.com" in domain_names


@pytest.mark.asyncio
async def test_wikidata_adapter_mocked():
    mock_data = {
        "search": [
            {
                "id": "Q2283",
                "label": "Microsoft",
                "description": "American multinational technology corporation",
                "aliases": ["MSFT"],
                "concepturi": "http://www.wikidata.org/entity/Q2283",
            }
        ]
    }

    mock_client = AsyncMock()
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.raise_for_status = MagicMock()
    mock_response.json = MagicMock(return_value=mock_data)
    mock_client.get = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    adapter = WikidataAdapter()

    with patch("app.sources.adapters.wikidata.get_httpx_client", return_value=mock_client):
        result = await adapter.search("Microsoft")

    assert result.success is True
    assert len(result.entities) == 1
    assert result.entities[0].name == "Microsoft"
    assert result.entities[0].entity_type == "COMPANY"
    assert "MSFT" in result.entities[0].aliases


@pytest.mark.asyncio
async def test_sec_edgar_adapter_mocked():
    mock_data = {
        "0": {"cik_str": 1045810, "ticker": "NVDA", "title": "NVIDIA CORP"},
        "1": {"cik_str": 789019, "ticker": "MSFT", "title": "MICROSOFT CORP"},
    }

    mock_client = AsyncMock()
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.raise_for_status = MagicMock()
    mock_response.json = MagicMock(return_value=mock_data)
    mock_client.get = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    adapter = SecEdgarAdapter()

    with patch("app.sources.adapters.sec_edgar.get_httpx_client", return_value=mock_client):
        result = await adapter.search("NVIDIA")

    assert result.success is True
    assert len(result.entities) == 1
    assert result.entities[0].name == "NVIDIA CORP"
    assert result.entities[0].aliases == ["NVDA"]


@pytest.mark.asyncio
async def test_arxiv_adapter_mocked():
    mock_xml = """<?xml version="1.0" encoding="UTF-8"?>
    <feed xmlns="http://www.w3.org/2005/Atom">
      <entry>
        <id>http://arxiv.org/abs/2401.00001v1</id>
        <title>Deep Residual Learning for Vision</title>
        <summary>We present a residual learning framework.</summary>
        <published>2024-01-01T00:00:00Z</published>
        <author><name>Kaiming He</name></author>
      </entry>
    </feed>
    """

    mock_client = AsyncMock()
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.raise_for_status = MagicMock()
    mock_response.text = mock_xml
    mock_client.get = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    adapter = ArxivAdapter()

    with patch("app.sources.adapters.arxiv.get_httpx_client", return_value=mock_client):
        result = await adapter.search("Residual Learning")

    assert result.success is True
    assert len(result.entities) == 2  # Paper + Author
    paper_ent = next(e for e in result.entities if e.entity_type == "RESEARCH_PAPER")
    author_ent = next(e for e in result.entities if e.entity_type == "PERSON")
    assert paper_ent.name == "Deep Residual Learning for Vision"
    assert author_ent.name == "Kaiming He"
    assert len(result.relationships) == 1
    assert result.relationships[0].relationship_type == "authored"


@pytest.mark.asyncio
async def test_semantic_scholar_adapter_mocked():
    mock_data = {
        "data": [
            {
                "paperId": "abc123paper",
                "title": "Attention Is All You Need",
                "abstract": "The dominant sequence transduction models are based on complex recurrent networks.",
                "publicationDate": "2017-06-12",
                "authors": [{"name": "Ashish Vaswani"}],
            }
        ]
    }

    mock_client = AsyncMock()
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.raise_for_status = MagicMock()
    mock_response.json = MagicMock(return_value=mock_data)
    mock_client.get = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    adapter = SemanticScholarAdapter()

    with patch("app.sources.adapters.semantic_scholar.get_httpx_client", return_value=mock_client):
        result = await adapter.search("Attention Is All You Need")

    assert result.success is True
    assert len(result.entities) == 2
    assert result.entities[0].name == "Attention Is All You Need"
    assert result.entities[1].name == "Ashish Vaswani"


@pytest.mark.asyncio
async def test_trafilatura_adapter_mocked():
    mock_html = "<html><body><h1>NEXUS Research</h1><p>NEXUS is an intelligence platform.</p></body></html>"

    mock_client = AsyncMock()
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.raise_for_status = MagicMock()
    mock_response.text = mock_html
    mock_client.get = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    adapter = TrafilaturaAdapter()

    with patch("app.sources.adapters.trafilatura_extractor.get_httpx_client", return_value=mock_client):
        result = await adapter.fetch("https://example.com/article")

    assert result.success is True
    assert len(result.evidence) == 1
    assert "NEXUS" in result.evidence[0].extracted_snippet


def test_registry_registration():
    custom_reg = AdapterRegistry()
    crt_adapter = CrtShAdapter()
    custom_reg.register(crt_adapter)

    assert custom_reg.get("crt_sh") is crt_adapter
    assert len(custom_reg.list_adapters()) == 1
    assert len(registry.list_adapters()) == 6
