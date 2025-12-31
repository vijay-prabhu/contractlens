"""Text chunking service for splitting documents into processable chunks."""
from dataclasses import dataclass
from typing import List

from langchain.text_splitter import RecursiveCharacterTextSplitter


@dataclass
class TextChunk:
    """A chunk of text from a document."""
    content: str
    chunk_index: int
    start_char: int
    end_char: int
    metadata: dict


class ChunkingService:
    """Service for splitting document text into chunks for embedding."""

    def __init__(
        self,
        chunk_size: int = 1000,
        chunk_overlap: int = 200,
    ):
        """Initialize chunking service.

        Args:
            chunk_size: Target size of each chunk in characters
            chunk_overlap: Number of overlapping characters between chunks
        """
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

        # Use recursive splitter for better semantic boundaries
        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            length_function=len,
            separators=[
                "\n\n",  # Paragraph breaks
                "\n",    # Line breaks
                ". ",    # Sentences
                ", ",    # Clauses
                " ",     # Words
                "",      # Characters
            ],
        )

    def chunk_text(
        self,
        text: str,
        document_metadata: dict | None = None,
    ) -> List[TextChunk]:
        """Split text into chunks.

        Args:
            text: Full document text to chunk
            document_metadata: Optional metadata to include with each chunk

        Returns:
            List of TextChunk objects
        """
        if not text.strip():
            return []

        # Create documents with metadata tracking
        docs = self.splitter.create_documents(
            texts=[text],
            metadatas=[document_metadata or {}],
        )

        chunks = []
        current_pos = 0

        for idx, doc in enumerate(docs):
            chunk_text = doc.page_content

            # Find position in original text
            start_char = text.find(chunk_text, current_pos)
            if start_char == -1:
                start_char = current_pos

            end_char = start_char + len(chunk_text)

            chunks.append(
                TextChunk(
                    content=chunk_text,
                    chunk_index=idx,
                    start_char=start_char,
                    end_char=end_char,
                    metadata={
                        **(document_metadata or {}),
                        "chunk_index": idx,
                        "total_chunks": len(docs),
                    },
                )
            )

            # Update position for next search (accounting for overlap)
            current_pos = max(current_pos, end_char - self.chunk_overlap)

        return chunks

    def chunk_for_contracts(
        self,
        text: str,
        document_metadata: dict | None = None,
    ) -> List[TextChunk]:
        """Chunk text optimized for legal contracts.

        Uses smaller chunks with more overlap to preserve clause context.

        Args:
            text: Full contract text
            document_metadata: Optional metadata

        Returns:
            List of TextChunk objects
        """
        contract_splitter = RecursiveCharacterTextSplitter(
            chunk_size=800,
            chunk_overlap=150,
            length_function=len,
            separators=[
                "\n\n",      # Paragraph/section breaks
                "\nSection", # Section headers
                "\nArticle", # Article headers
                "\nClause",  # Clause headers
                "\n",        # Line breaks
                "; ",        # Legal clause separators
                ". ",        # Sentences
                ", ",        # Clauses
                " ",
                "",
            ],
        )

        docs = contract_splitter.create_documents(
            texts=[text],
            metadatas=[document_metadata or {}],
        )

        chunks = []
        current_pos = 0

        for idx, doc in enumerate(docs):
            chunk_text = doc.page_content
            start_char = text.find(chunk_text, current_pos)
            if start_char == -1:
                start_char = current_pos
            end_char = start_char + len(chunk_text)

            chunks.append(
                TextChunk(
                    content=chunk_text,
                    chunk_index=idx,
                    start_char=start_char,
                    end_char=end_char,
                    metadata={
                        **(document_metadata or {}),
                        "chunk_index": idx,
                        "total_chunks": len(docs),
                        "chunking_strategy": "contract_optimized",
                    },
                )
            )

            current_pos = max(current_pos, end_char - 150)

        return chunks
