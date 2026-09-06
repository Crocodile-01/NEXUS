import xml.etree.ElementTree as ET

from app.sources.base import (
    ExtractedEntity,
    ExtractedRelationship,
    RawEvidence,
    SourceAdapter,
    SourceMetadata,
    SourceResult,
)
from app.sources.http_client import get_httpx_client


class ArxivAdapter(SourceAdapter):
    """
    Adapter for searching arXiv research papers and author metadata.
    """

    @property
    def metadata(self) -> SourceMetadata:
        return SourceMetadata(
            name="arxiv",
            category="academic",
            reliability_tier="REPUTABLE",
            is_passive=True,
            rate_limit_per_minute=30,
            timeout_seconds=15,
        )

    async def search(self, query: str, limit: int = 5) -> SourceResult:
        url = f"http://export.arxiv.org/api/query?search_query=all:{query}&start=0&max_results={limit}"

        try:
            async with get_httpx_client(timeout_seconds=self.metadata.timeout_seconds) as client:
                response = await client.get(url)
                response.raise_for_status()
                xml_content = response.text
        except Exception as exc:  # noqa: BLE001
            return SourceResult(
                success=False,
                source_name=self.metadata.name,
                query=query,
                error_message=f"arXiv API connection error: {exc!s}",
            )

        evidence_list: list[RawEvidence] = []
        entities: list[ExtractedEntity] = []
        relationships: list[ExtractedRelationship] = []

        try:
            root = ET.fromstring(xml_content)
            ns = {"atom": "http://www.w3.org/2005/Atom"}

            for entry in root.findall("atom:entry", ns):
                title_elem = entry.find("atom:title", ns)
                summary_elem = entry.find("atom:summary", ns)
                published_elem = entry.find("atom:published", ns)
                id_elem = entry.find("atom:id", ns)

                title = title_elem.text.strip().replace("\n", " ") if title_elem is not None and title_elem.text else ""
                summary = summary_elem.text.strip().replace("\n", " ") if summary_elem is not None and summary_elem.text else ""
                published = published_elem.text.strip() if published_elem is not None and published_elem.text else ""
                paper_id = id_elem.text.strip() if id_elem is not None and id_elem.text else ""

                if not title:
                    continue

                paper_entity = ExtractedEntity(
                    name=title,
                    entity_type="RESEARCH_PAPER",
                    confidence=1.0,
                    metadata={"arxiv_id": paper_id, "published": published},
                )
                entities.append(paper_entity)

                # Extract Authors
                for author_elem in entry.findall("atom:author", ns):
                    name_node = author_elem.find("atom:name", ns)
                    if name_node is not None and name_node.text:
                        author_name = name_node.text.strip()
                        entities.append(
                            ExtractedEntity(name=author_name, entity_type="PERSON", confidence=0.9)
                        )
                        relationships.append(
                            ExtractedRelationship(
                                source_entity=author_name,
                                source_entity_type="PERSON",
                                target_entity=title,
                                target_entity_type="RESEARCH_PAPER",
                                relationship_type="authored",
                                confidence=0.9,
                            )
                        )

                snippet = f"Research Paper: '{title}' - Abstract: {summary[:300]}..."
                evidence_list.append(
                    RawEvidence(
                        source_name=self.metadata.name,
                        url=paper_id,
                        extracted_snippet=snippet,
                        publication_date=published,
                        metadata={"title": title, "arxiv_id": paper_id},
                    )
                )

        except Exception as exc:  # noqa: BLE001
            return SourceResult(
                success=False,
                source_name=self.metadata.name,
                query=query,
                error_message=f"Failed to parse arXiv XML: {exc!s}",
            )

        return SourceResult(
            success=True,
            source_name=self.metadata.name,
            query=query,
            evidence=evidence_list,
            entities=entities,
            relationships=relationships,
        )
