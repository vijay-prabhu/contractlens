"""Document extraction using Docling for structured output (ADR-010).

Produces structured documents with sections, tables, and metadata
instead of flat text. Replaces PyMuPDF for PDF parsing.
"""
import io
import logging
from dataclasses import dataclass, field
from typing import List, Optional

from docling.document_converter import DocumentConverter
from docling_core.types.io import DocumentStream
from docling_core.types.doc.labels import DocItemLabel

logger = logging.getLogger(__name__)


@dataclass
class Section:
    """A logical section extracted from a document."""
    title: str
    text: str
    level: int = 0
    start_char: int = 0
    end_char: int = 0


@dataclass
class DoclingExtractionResult:
    """Structured extraction result from Docling."""
    sections: List[Section]
    full_text: str
    markdown: str
    page_count: int
    metadata: dict
    tables_count: int = 0


# Singleton converter — expensive to create, reuse across calls
_converter: Optional[DocumentConverter] = None


def _get_converter() -> DocumentConverter:
    global _converter
    if _converter is None:
        _converter = DocumentConverter()
    return _converter


class DoclingExtractionService:
    """Extraction service using Docling for structured document parsing."""

    def extract(self, content: bytes, file_type: str) -> DoclingExtractionResult:
        """Extract structured content from a document.

        Args:
            content: Raw bytes of the document
            file_type: 'pdf' or 'docx'

        Returns:
            DoclingExtractionResult with sections, full text, and markdown
        """
        filename = f"document.{file_type}"
        stream = DocumentStream(name=filename, stream=io.BytesIO(content))

        converter = _get_converter()
        result = converter.convert(stream)
        doc = result.document

        # Extract sections by iterating the document tree
        sections = self._extract_sections(doc)

        # Get full text and markdown exports
        full_text = doc.export_to_text()
        markdown = doc.export_to_markdown()

        # Count pages and tables
        page_count = result.pages if hasattr(result, 'pages') else self._estimate_pages(doc)
        tables_count = sum(1 for item, _ in doc.iterate_items() if item.label == DocItemLabel.TABLE)

        # Extract metadata
        metadata = {}
        if hasattr(result, 'metadata') and result.metadata:
            metadata = dict(result.metadata) if hasattr(result.metadata, '__iter__') else {}

        logger.info(
            f"Docling extracted: {len(sections)} sections, "
            f"{tables_count} tables, ~{page_count} pages"
        )

        return DoclingExtractionResult(
            sections=sections,
            full_text=full_text,
            markdown=markdown,
            page_count=page_count,
            metadata=metadata,
            tables_count=tables_count,
        )

    def _extract_sections(self, doc) -> List[Section]:
        """Extract logical sections from a Docling document.

        Groups content under section headers. Content before the first
        section header goes into a "Preamble" section.
        """
        sections: List[Section] = []
        current_title = "Preamble"
        current_level = 0
        current_texts: List[str] = []
        char_pos = 0

        for item, level in doc.iterate_items():
            label = item.label

            # Skip page headers/footers — this is the key advantage over PyMuPDF
            if label in (DocItemLabel.PAGE_HEADER, DocItemLabel.PAGE_FOOTER):
                continue

            # Get text content from the item
            text = item.text if hasattr(item, 'text') and item.text else ""

            if label == DocItemLabel.SECTION_HEADER or label == DocItemLabel.TITLE:
                # Save previous section if it has content
                if current_texts:
                    section_text = "\n\n".join(current_texts)
                    sections.append(Section(
                        title=current_title,
                        text=section_text,
                        level=current_level,
                        start_char=char_pos,
                        end_char=char_pos + len(section_text),
                    ))
                    char_pos += len(section_text) + 2

                # Start new section
                current_title = text.strip() if text else f"Section {len(sections) + 1}"
                current_level = level
                current_texts = []

            elif label == DocItemLabel.TABLE:
                # Export table as markdown to preserve structure
                try:
                    table_md = item.export_to_markdown() if hasattr(item, 'export_to_markdown') else text
                    if table_md:
                        current_texts.append(table_md)
                except Exception:
                    if text:
                        current_texts.append(text)

            elif text.strip():
                current_texts.append(text.strip())

        # Don't forget the last section
        if current_texts:
            section_text = "\n\n".join(current_texts)
            sections.append(Section(
                title=current_title,
                text=section_text,
                level=current_level,
                start_char=char_pos,
                end_char=char_pos + len(section_text),
            ))

        return sections

    def _estimate_pages(self, doc) -> int:
        """Estimate page count from document content."""
        text = doc.export_to_text()
        # Rough estimate: ~3000 chars per page for a legal document
        return max(1, len(text) // 3000)
