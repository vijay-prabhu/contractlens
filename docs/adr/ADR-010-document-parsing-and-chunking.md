# ADR-010: Document Parsing & Chunking — Docling Migration

## Status
Proposed

## Date
2026-03-28

## Context

ContractLens uses PyMuPDF for PDF extraction and a LangChain `RecursiveCharacterTextSplitter` for chunking. Both have significant quality problems that affect every downstream step.

### Current Parsing: PyMuPDF

```python
page = doc[page_num]
text = page.get_text("text")
```

`get_text("text")` dumps raw text with no structure preservation. Benchmarks across 800+ documents rate PyMuPDF at **6/10** for LLM-focused extraction.

### What breaks with complex documents

| Content Type | What happens | Impact |
|---|---|---|
| **Tables** | Cells dumped as flat text stream. `Party A 5.25% Fixed Party B SOFR+1%` | Payment schedules, fee grids, interest rate tables become unreadable |
| **Headers/footers** | Extracted as regular text on every page | 200-page doc = 200 repeated noise lines, wasting classification API calls |
| **Diagrams/images** | Completely lost — `get_text` only extracts text | Scanned contracts, image-embedded clauses invisible to the system |
| **Section hierarchy** | Flat text, no nesting | "Section 4.2(a)(iii)" loses its relationship to parent sections |
| **Cross-references** | Split across chunks | "as defined in Section 2.1" becomes meaningless when Section 2.1 is in a different chunk |

### Real-World Example: Bank ISDA Master Agreement

An ISDA contract is typically 150+ pages (base agreement + schedules + credit support annex + confirmations). Current system behavior:

| Step | What happens |
|---|---|
| **Extraction** | ~450,000 chars of flat text with 150 repeated headers/footers |
| **Chunking** | ~560 chunks at 800 chars each, many mid-clause fragments |
| **Classification** | ~560 GPT-4o-mini calls, ~30-40% on garbage (headers, table fragments, split clauses) |
| **Quality** | Table data misclassified, sections split arbitrarily, cross-references broken |
| **Time** | ~150s for classification even with parallelization |

### Current Chunking: LangChain Fixed-Size

```python
contract_splitter = RecursiveCharacterTextSplitter(
    chunk_size=800,        # ~200 tokens — too small
    chunk_overlap=150,
    separators=["\n\n", "\nSection", "\nArticle", "\nClause", "\n", "; ", ". ", ...]
)
```

**Problems:**
1. **800 chars (~200 tokens) is too small.** Research shows 256-512 tokens is the sweet spot for embeddings. Our chunks lose context.
2. **Section headers are separators, not preserved.** The splitter splits *at* `\nSection` but doesn't keep the header with its content.
3. **ADR-004 findings:** "IP Rights (identical in both versions) appeared as two 'Modified' entries at 94% and 82% similarity because the chunks split at different character positions."
4. **No grounding.** The 800/150 values aren't benchmarked.

### Research Evidence

| Finding | Source |
|---|---|
| Adaptive/section-aware chunking beats fixed-size: 87% vs 13% accuracy | MDPI Bioengineering 2025 (peer-reviewed, p=0.001) |
| Recursive 512-token splitting ranked #1 at 69% accuracy across 7 strategies | Vecta benchmark Feb 2026 |
| Docling achieves 97.9% accuracy on complex table extraction | Procycons PDF Extraction Benchmark 2025 |
| PyMuPDF rated 6/10, LlamaParse 9/10 for structure-aware extraction | Applied AI benchmark, 800+ documents |
| "If you're still relying on PyMuPDF for parsing, your RAG pipeline is already broken at the data layer" | Applied AI 2025 |
| Parser accuracy varies 55+ points by domain | Applied AI benchmark |

## Decision

### 1. Replace PyMuPDF with Docling for PDF Parsing

[Docling](https://github.com/docling-project/docling) is an open-source document parser that produces structured output:

- **Tables** → preserved as structured objects with rows, columns, headers
- **Headers/footers** → detected and stripped
- **Section hierarchy** → preserved with nesting
- **OCR** → built-in for scanned pages (uses EasyOCR or Tesseract)
- **Output formats** → Markdown, JSON, or DoclingDocument (structured representation)
- **Local execution** → no API calls, no data leaves the machine
- **Integrations** → LangChain, LlamaIndex, LangGraph compatible

```python
from docling.document_converter import DocumentConverter

converter = DocumentConverter()
result = converter.convert("contract.pdf")

# Structured document with sections, tables, metadata
doc = result.document

# Export as markdown (preserves structure)
markdown = doc.export_to_markdown()

# Or iterate sections directly
for section in doc.sections:
    print(section.title, section.level, section.text)
```

### 2. Section-Aware Chunking

Replace fixed-size chunking with section-boundary chunking using Docling's structured output:

**Strategy:** Chunk at section boundaries. If a section exceeds the token limit (~512 tokens), split within the section using sentence boundaries. Prepend section header to each sub-chunk for context.

```python
def chunk_document(docling_doc, max_tokens=512):
    chunks = []
    for section in docling_doc.sections:
        section_text = f"{section.title}\n\n{section.text}"

        if token_count(section_text) <= max_tokens:
            # Section fits in one chunk — keep it whole
            chunks.append(section_text)
        else:
            # Split within section, preserving header context
            sub_chunks = split_at_sentences(section.text, max_tokens - token_count(section.title))
            for sub in sub_chunks:
                chunks.append(f"{section.title}\n\n{sub}")

    return chunks
```

**Key changes from current approach:**

| Aspect | Current | New |
|---|---|---|
| Chunk boundary | Character count (800) | Section boundary |
| Chunk size | ~200 tokens | ~512 tokens (up to full section) |
| Context preservation | 150 char overlap | Section header prepended to each sub-chunk |
| Table handling | Tables become garbled text in chunks | Tables kept as structured markdown within their section's chunk |
| Header/footer | Included as noise | Stripped by Docling before chunking |

### 3. Handle Complex Content

**Tables:** Docling extracts tables as structured data. For classification, tables are converted to markdown format and included in their parent section's chunk. This means GPT-4o-mini sees:

```
Section 5: Payment Terms

Payment is due within 30 days of invoice. Late payments accrue interest at 1.5% per month.

| Payment Milestone | Amount | Due Date |
|---|---|---|
| Phase 1 Delivery | $250,000 | March 15, 2026 |
| Phase 2 Delivery | $175,000 | June 30, 2026 |
```

Instead of: `Payment Milestone Amount Due Date Phase 1 Delivery $250,000 March 15, 2026 Phase 2...`

**OCR for scanned pages:** Docling detects image-only pages and runs OCR automatically. No configuration needed for standard quality scans.

**Headers/footers:** Docling identifies and strips repeated page elements. No more "CONFIDENTIAL — Page X of 200" polluting 200 chunks.

### 4. ISDA Contract: Before vs After

| Metric | Before (PyMuPDF + 800 char) | After (Docling + section-aware) |
|---|---|---|
| Chunks produced | ~560 (many garbage) | ~50-80 (clean sections) |
| Classification API calls | 560 | 50-80 |
| Classification time (parallel) | ~150s | ~20-30s |
| Classification cost | ~$0.10 | ~$0.02 |
| Table accuracy | Garbled text | Structured markdown |
| Header/footer noise | ~30-40% of chunks | 0% |
| Mid-clause splits | Frequent | Rare (only oversized sections) |
| Comparison accuracy | ~36 changes (inflated 2.5x) | ~14 changes (matches reality) |

### 5. Backward Compatibility

The change affects the extraction and chunking steps. Downstream services (embedding, classification, comparison, search) receive text strings — they don't care how the text was produced. No changes needed to:
- Embedding service
- Classification service (benefits from better input)
- Search service
- Comparison service
- Database schema (clauses table unchanged)

Existing documents in the database keep their current chunks/embeddings. New uploads use the new pipeline. A "Reprocess" button already exists in the UI to re-process old documents through the new pipeline.

## Implementation

### Phase 1: Add Docling parser alongside PyMuPDF
- Add `docling` to `pyproject.toml`
- Create `DoclingExtractionService` that returns structured output
- Keep `ExtractionService` as fallback for edge cases
- Feature flag to toggle between parsers

### Phase 2: Section-aware chunking
- New `SectionChunkingService` that takes Docling output
- Chunks at section boundaries with 512-token target
- Prepends section headers to sub-chunks
- Replace `chunk_for_contracts` calls in document processor

### Phase 3: Remove old pipeline
- Remove PyMuPDF extraction (or keep as lightweight fallback)
- Remove LangChain `RecursiveCharacterTextSplitter` dependency (for chunking — LangChain may still be used elsewhere)
- Remove `chunk_for_contracts` method

## Files to Modify

| File | Change |
|---|---|
| `pyproject.toml` | Add `docling` dependency |
| `backend/app/services/extraction_service.py` | New Docling extraction alongside existing PyMuPDF |
| `backend/app/services/chunking_service.py` | New section-aware chunking |
| `backend/app/workers/document_processor.py` | Wire new extraction + chunking |

## Consequences

### Positive
- Tables, headers, sections preserved — dramatically better classification input
- 7-10x fewer chunks per document — faster processing, lower cost
- Section-level comparison becomes possible (fixes ADR-004's core issue)
- OCR support for scanned contracts
- Local execution — no data sent to external parsing APIs

### Negative
- Docling is a heavier dependency (~500MB with OCR models)
- Docker image size increases
- Initial processing is slightly slower (Docling does more work than raw text extraction)
- Need to verify Docling handles all contract formats we encounter

### Trade-offs
- Using Docling (local, open-source) over LlamaParse (API, commercial) — avoids vendor lock-in and data privacy concerns
- 512-token target rather than dynamic sizing — simpler implementation, can tune later
- Not re-processing existing documents automatically — users trigger via Reprocess button

## References
- [Docling: Get Your Documents Ready for Gen AI](https://github.com/docling-project/docling)
- [PDF Data Extraction Benchmark 2025](https://procycons.com/en/blogs/pdf-data-extraction-benchmark/)
- [The State of PDF Parsing: 800+ Documents](https://www.applied-ai.com/briefings/pdf-parsing-benchmark/)
- [NVIDIA: Finding the Best Chunking Strategy](https://developer.nvidia.com/blog/finding-the-best-chunking-strategy-for-accurate-ai-responses/)
- [Vecta Chunking Benchmark Feb 2026](https://www.firecrawl.dev/blog/best-chunking-strategies-rag)
- [MDPI: Adaptive Chunking for Clinical Decision Support (2025)](https://www.mdpi.com/journals/bioengineering)
