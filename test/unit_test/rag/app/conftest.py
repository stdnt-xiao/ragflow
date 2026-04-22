"""
Stub heavy dependencies for rag.app unit tests.

rag/app/naive.py imports deepdoc.parser.pdf_parser which pulls in xgboost,
and various API/DB layers. We pre-stub these so tests can import by_mineru
without requiring GPU libraries or a running database.

Important: do NOT stub `rag` itself — Python must resolve it as a real package.
"""
import sys
import types
from unittest.mock import MagicMock


def _stub_if_missing(name: str) -> MagicMock:
    if name not in sys.modules:
        m = MagicMock()
        m.__name__ = name
        sys.modules[name] = m
    return sys.modules[name]


# ── xgboost (broken pkg_resources issue on this env) ────────────────────────
for _xgb in ["xgboost", "xgboost.core", "xgboost.compat", "xgboost.sklearn"]:
    _stub_if_missing(_xgb)

# ── Other heavy ML deps ──────────────────────────────────────────────────────
for _m in [
    "torch", "transformers",
    "magic_pdf", "magic_pdf.data", "magic_pdf.data.data_reader_writer",
    "magic_pdf.pipe", "magic_pdf.pipe.UNIPipe",
    "magic_pdf.model", "magic_pdf.libs",
    "cv2", "sklearn", "scipy", "scipy.sparse",
    "rapidocr_onnxruntime",
]:
    _stub_if_missing(_m)

# PIL needs Image attribute
_pil = _stub_if_missing("PIL")
_stub_if_missing("PIL.Image")

# ── deepdoc: stub the package so submodule imports work without filesystem ────
if "deepdoc" not in sys.modules:
    _deepdoc_pkg = types.ModuleType("deepdoc")
    _deepdoc_pkg.__path__ = []
    sys.modules["deepdoc"] = _deepdoc_pkg

if "deepdoc.parser" not in sys.modules:
    _parser_pkg = types.ModuleType("deepdoc.parser")
    _parser_pkg.__path__ = []
    _parser_pkg.__package__ = "deepdoc.parser"
    sys.modules["deepdoc.parser"] = _parser_pkg

for _m in [
    "deepdoc.parser.pdf_parser",
    "deepdoc.parser.figure_parser",
    "deepdoc.parser.docling_parser",
    "deepdoc.parser.tcadp_parser",
    "deepdoc.parser.paddleocr_parser",
    "deepdoc.parser.mineru_parser",
]:
    _stub_if_missing(_m)

# mineru_parser needs MinerUParser class for patching
_mineru_mod = sys.modules["deepdoc.parser.mineru_parser"]
_mineru_mod.MinerUParser = MagicMock()
# Register as attribute of deepdoc.parser package so patch() can resolve it
sys.modules["deepdoc.parser"].mineru_parser = _mineru_mod

# Populate attributes that naive.py does "from deepdoc.parser import X" on
_parser_ns = sys.modules["deepdoc.parser"]
for _attr in [
    "DocxParser", "EpubParser", "ExcelParser", "HtmlParser", "JsonParser",
    "MarkdownElementExtractor", "MarkdownParser", "PdfParser", "TxtParser",
]:
    if not hasattr(_parser_ns, _attr):
        setattr(_parser_ns, _attr, MagicMock())

# pdf_parser needs PlainParser, VisionParser
_pp = sys.modules["deepdoc.parser.pdf_parser"]
_pp.PlainParser = MagicMock()
_pp.VisionParser = MagicMock()
_pp.RAGFlowPdfParser = MagicMock()

# figure_parser attrs
_fp = sys.modules["deepdoc.parser.figure_parser"]
_fp.VisionFigureParser = MagicMock()
_fp.vision_figure_parser_docx_wrapper_naive = MagicMock()
_fp.vision_figure_parser_pdf_wrapper = MagicMock()

# docling_parser attr
_dp = sys.modules["deepdoc.parser.docling_parser"]
_dp.DoclingParser = MagicMock()

# tcadp_parser attr
_tp = sys.modules["deepdoc.parser.tcadp_parser"]
_tp.TCADPParser = MagicMock()

# ── api.db and services (stubs) ───────────────────────────────────────────────
for _m in [
    "api", "api.db", "api.db.db_models",
    "api.db.services", "api.db.services.llm_service",
    "api.db.joint_services", "api.db.joint_services.tenant_model_service",
]:
    _stub_if_missing(_m)

# LLMBundle used in naive.py
sys.modules["api.db.services.llm_service"].LLMBundle = MagicMock()

# ── rag submodules that naive.py imports (but NOT rag itself) ─────────────────
# rag.nlp is imported as: from rag.nlp import (...)
# We need rag.nlp to exist as a stub
_stub_if_missing("rag.nlp")
_stub_if_missing("rag.utils")
_stub_if_missing("rag.utils.file_utils")

# ── common modules ────────────────────────────────────────────────────────────
for _m in [
    "common", "common.token_utils", "common.constants",
    "common.float_utils", "common.parser_config_utils",
    "common.text_utils",
]:
    _stub_if_missing(_m)

# common.constants needs LLMType
_cc = sys.modules["common.constants"]
_cc.LLMType = MagicMock()

# common.parser_config_utils needs normalize_layout_recognizer
_cpu = sys.modules["common.parser_config_utils"]
_cpu.normalize_layout_recognizer = MagicMock(return_value=("DeepDOC", None))

# ── docx (python-docx) ────────────────────────────────────────────────────────
for _m in [
    "docx", "docx.opc", "docx.opc.pkgreader", "docx.opc.oxml",
    "docx.table", "docx.text", "docx.text.paragraph",
    "markdown",
]:
    _stub_if_missing(_m)
