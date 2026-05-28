"""Phase 0 spike (THROWAWAY) — prove the risky citation core before building the app.

Pipeline:  one PDF -> Docling -> Markdown -> LlamaIndex nodes (with char offsets)
           -> VectorStoreIndex (Gemini embeddings) -> CitationQueryEngine (Gemini LLM)
           -> grounded answer with [n] markers + per-citation source spans.

GO/NO-GO question: for each citation, can we relocate the cited passage inside the
parsed markdown using the node's char offsets (or a substring fallback)? If yes, the
click-to-highlight feature is feasible and the project is a go.
"""

import os
import sys
import textwrap

from dotenv import load_dotenv

load_dotenv()
API_KEY = os.getenv("GEMINI_API_KEY")
if not API_KEY:
    sys.exit("GEMINI_API_KEY missing from backend/.env")

PDF_PATH = sys.argv[1] if len(sys.argv) > 1 else "test_doc.pdf"
LLM_MODEL = "gemini-2.5-flash"
EMBED_MODEL = "gemini-embedding-001"


def rule(title: str) -> None:
    print("\n" + "=" * 78 + f"\n{title}\n" + "=" * 78)


# ---------------------------------------------------------------- 1. PARSE
rule("1. DOCLING PARSE")
import torch
from docling.document_converter import DocumentConverter, PdfFormatOption
from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions

try:  # import location varies across docling versions
    from docling.datamodel.accelerator_options import AcceleratorDevice, AcceleratorOptions
except ImportError:
    from docling.datamodel.pipeline_options import AcceleratorDevice, AcceleratorOptions

# Resolve the compute device ONCE, then reuse everywhere below.
#   - CUDA when present (GPU servers — fastest).
#   - CPU otherwise. On Apple Silicon we deliberately stay on CPU and do NOT use MPS:
#     MPS lacks float64, which crashes Docling's RT-DETR layout model. Do not switch
#     this to MPS "for speed" — it will hard-fail the parse.
device = AcceleratorDevice.CUDA if torch.cuda.is_available() else AcceleratorDevice.CPU
print(f"Docling device: {device}")

opts = PdfPipelineOptions()
opts.accelerator_options = AcceleratorOptions(device=device)
opts.do_ocr = False  # text-layer PDFs: skip OCR (faster, no model downloads)
converter = DocumentConverter(
    format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=opts)}
)

md = converter.convert(PDF_PATH).document.export_to_markdown()
print(f"Parsed markdown: {len(md)} chars\n")
print(textwrap.indent(md[:600] + ("..." if len(md) > 600 else ""), "  "))

# ---------------------------------------------------------------- 2. NODES
rule("2. CHUNK -> NODES (char offsets retained)")
from llama_index.core import Document, VectorStoreIndex, Settings
from llama_index.core.node_parser import SentenceSplitter

doc = Document(text=md)
nodes = SentenceSplitter(chunk_size=320, chunk_overlap=40).get_nodes_from_documents([doc])
print(f"{len(nodes)} nodes")
for i, n in enumerate(nodes):
    ok = n.start_char_idx is not None and md[n.start_char_idx : n.end_char_idx] == n.get_content()
    print(f"  node[{i}] off[{n.start_char_idx}:{n.end_char_idx}] roundtrip={'OK' if ok else 'NO'} "
          f":: {n.get_content()[:60]!r}")

# ---------------------------------------------------------------- 3. MODELS
rule("3. GEMINI MODELS")
from llama_index.llms.google_genai import GoogleGenAI
from llama_index.embeddings.google_genai import GoogleGenAIEmbedding

Settings.llm = GoogleGenAI(model=LLM_MODEL, api_key=API_KEY)
Settings.embed_model = GoogleGenAIEmbedding(model_name=EMBED_MODEL, api_key=API_KEY)
print(f"LLM={LLM_MODEL}  embeddings={EMBED_MODEL}")

# ---------------------------------------------------------------- 4. INDEX + ENGINE
rule("4. INDEX + CitationQueryEngine")
from llama_index.core.query_engine import CitationQueryEngine

index = VectorStoreIndex(nodes)
engine = CitationQueryEngine.from_args(index, similarity_top_k=3, citation_chunk_size=256)
print("ready")


def strip_prefix(text: str) -> str:
    # CitationQueryEngine prepends "Source N:\n" to each citation node.
    if text.startswith("Source ") and ":\n" in text[:20]:
        return text.split(":\n", 1)[1].strip()
    return text.strip()


def locate(passage: str) -> str:
    """Can we find this passage in the parsed markdown? Report the strategy used."""
    idx = md.find(passage)
    if idx != -1:
        return f"FOUND via exact substring at char {idx}-{idx + len(passage)}"
    # tolerate whitespace differences
    squashed_md = " ".join(md.split())
    squashed_p = " ".join(passage.split())
    if squashed_p in squashed_md:
        return f"FOUND via whitespace-normalized substring (offset recoverable)"
    return "NOT FOUND"


def ask(question: str, expect_grounded: bool) -> None:
    rule(f"QUERY ({'grounded' if expect_grounded else 'OUT-OF-SOURCES'}): {question}")
    resp = engine.query(question)
    print("ANSWER:\n" + textwrap.indent(textwrap.fill(str(resp), 92), "  "))
    print(f"\nCITATIONS / SOURCE NODES: {len(resp.source_nodes)}")
    for i, sn in enumerate(resp.source_nodes, 1):
        node = sn.node
        passage = strip_prefix(node.get_content())
        print(f"\n  [{i}] score={sn.score:.3f}  node_offset=[{node.start_char_idx}:{node.end_char_idx}]")
        print(textwrap.indent(textwrap.fill(passage[:240], 88), "      "))
        print(f"      RELOCATE -> {locate(passage)}")


# ---------------------------------------------------------------- 5. RUN
ask("What is the correlation between spindle density and word-pair recall, "
    "and for which items is the effect largest?", expect_grounded=True)

ask("What is the capital of France?", expect_grounded=False)

rule("DONE — inspect: (a) do citations relocate in markdown? (b) is the out-of-sources answer refused?")
