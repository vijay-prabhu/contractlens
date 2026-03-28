"""Section-aware chunking for Docling-extracted documents (ADR-010).

Chunks at section boundaries instead of fixed character count.
If a section exceeds the token limit, splits within the section
at sentence boundaries and prepends the section header for context.
"""
import logging
import re
from dataclasses import dataclass
from typing import List

from app.services.docling_extraction_service import Section

logger = logging.getLogger(__name__)

# Target ~512 tokens ≈ ~2000 chars for legal text
MAX_CHUNK_CHARS = 2000
SENTENCE_PATTERN = re.compile(r'(?<=[.!?])\s+(?=[A-Z("])')


@dataclass
class TextChunk:
    """A chunk of text from a document — compatible with existing pipeline."""
    content: str
    chunk_index: int
    start_char: int
    end_char: int
    metadata: dict


def chunk_sections(
    sections: List[Section],
    document_metadata: dict | None = None,
    max_chunk_chars: int = MAX_CHUNK_CHARS,
) -> List[TextChunk]:
    """Chunk a list of sections into text chunks.

    Sections that fit within max_chunk_chars are kept whole.
    Oversized sections are split at sentence boundaries with the
    section header prepended to each sub-chunk for context.

    Args:
        sections: Sections from DoclingExtractionResult
        document_metadata: Optional metadata for each chunk
        max_chunk_chars: Maximum characters per chunk

    Returns:
        List of TextChunk objects compatible with existing embedding/classification pipeline
    """
    if not sections:
        return []

    chunks: List[TextChunk] = []
    chunk_idx = 0

    for section in sections:
        section_text = f"{section.title}\n\n{section.text}" if section.title != "Preamble" else section.text

        if len(section_text) <= max_chunk_chars:
            # Section fits in one chunk — keep it whole
            chunks.append(TextChunk(
                content=section_text,
                chunk_index=chunk_idx,
                start_char=section.start_char,
                end_char=section.end_char,
                metadata={
                    **(document_metadata or {}),
                    "chunk_index": chunk_idx,
                    "section_title": section.title,
                    "chunking_strategy": "section_aware",
                },
            ))
            chunk_idx += 1
        else:
            # Split within section at sentence boundaries
            header = f"{section.title}\n\n"
            header_len = len(header)
            available = max_chunk_chars - header_len

            sub_chunks = _split_at_sentences(section.text, available)
            for i, sub_text in enumerate(sub_chunks):
                chunk_text = f"{header}{sub_text}" if section.title != "Preamble" else sub_text
                offset = section.start_char + (i * available)

                chunks.append(TextChunk(
                    content=chunk_text,
                    chunk_index=chunk_idx,
                    start_char=offset,
                    end_char=offset + len(chunk_text),
                    metadata={
                        **(document_metadata or {}),
                        "chunk_index": chunk_idx,
                        "section_title": section.title,
                        "sub_chunk": f"{i + 1}/{len(sub_chunks)}",
                        "chunking_strategy": "section_aware",
                    },
                ))
                chunk_idx += 1

    total_sections = len(sections)
    logger.info(
        f"Section chunking: {total_sections} sections → {len(chunks)} chunks "
        f"(max {max_chunk_chars} chars)"
    )

    return chunks


def _split_at_sentences(text: str, max_chars: int) -> List[str]:
    """Split text at sentence boundaries to fit within max_chars."""
    sentences = SENTENCE_PATTERN.split(text)
    if not sentences:
        return [text]

    result: List[str] = []
    current = ""

    for sentence in sentences:
        if not sentence.strip():
            continue

        if len(current) + len(sentence) + 1 <= max_chars:
            current = f"{current} {sentence}".strip() if current else sentence
        else:
            if current:
                result.append(current)
            # If a single sentence exceeds max_chars, include it anyway
            current = sentence

    if current:
        result.append(current)

    return result if result else [text]
