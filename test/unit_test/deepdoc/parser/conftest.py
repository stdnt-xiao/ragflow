"""
Isolate deepdoc.parser.mineru_parser from the full package import chain.

deepdoc/parser/__init__.py pulls in docx_parser → rag_tokenizer → scipy,
which conflicts with our torch mock.  We bypass __init__ entirely by
pre-populating sys.modules with lightweight stubs before the test module loads.

A meta path finder intercepts any unknown deepdoc.parser.* submodule import
and returns a MagicMock, so other test files (e.g. test_checkpoint_resume.py)
that import real deepdoc.parser submodules are not broken.
"""
import importlib.util
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock

import pytest

_RAGFLOW_ROOT = Path(__file__).parents[4]  # …/ragflow

_STUBBED_NAMES: list[str] = []


def _stub(name: str, **attrs) -> types.ModuleType:
    m = types.ModuleType(name)
    for k, v in attrs.items():
        setattr(m, k, v)
    sys.modules[name] = m
    _STUBBED_NAMES.append(name)
    return m


# ── torch: Tensor must be a real class (scipy calls issubclass on it) ────────
_torch = _stub("torch")


class _FakeTensor:
    pass


_torch.Tensor = _FakeTensor

# ── Other heavy deps ─────────────────────────────────────────────────────────
for _m in [
    "transformers",
    "magic_pdf",
    "magic_pdf.data",
    "magic_pdf.data.data_reader_writer",
    "magic_pdf.pipe",
    "magic_pdf.pipe.UNIPipe",
    "magic_pdf.model",
    "magic_pdf.libs",
]:
    if _m not in sys.modules:
        sys.modules[_m] = MagicMock()
        _STUBBED_NAMES.append(_m)

# ── Stub deepdoc.parser as a package (set __path__ so Python treats it so) ──
_deepdoc = _stub("deepdoc")
_parser_pkg = types.ModuleType("deepdoc.parser")
_parser_pkg.__path__ = []   # empty → no filesystem lookup, but marks it a package
_parser_pkg.__package__ = "deepdoc.parser"
sys.modules["deepdoc.parser"] = _parser_pkg
_STUBBED_NAMES.append("deepdoc.parser")
_deepdoc.parser = _parser_pkg


# ── Meta path finder: auto-MagicMock any deepdoc.parser.* submodule ─────────
class _DeepDocParserFinder:
    """Return a MagicMock for any unknown deepdoc.parser.* submodule import."""

    def find_spec(self, name, path, target=None):  # noqa: ARG002
        if name.startswith("deepdoc.parser.") and name not in sys.modules:
            import importlib.machinery
            return importlib.machinery.ModuleSpec(name, self)
        return None

    def create_module(self, spec):
        return None  # use default creation

    def exec_module(self, module):
        # Replace with MagicMock so all attribute access works
        name = module.__name__
        mock = MagicMock()
        mock.__name__ = name
        mock.__package__ = name.rsplit(".", 1)[0]
        mock.__spec__ = module.__spec__
        # Swap into sys.modules
        sys.modules[name] = mock


_finder = _DeepDocParserFinder()
sys.meta_path.insert(0, _finder)


# RAGFlowPdfParser: MinerUParser inherits from it; needs a real class.
class _FakeRAGFlowPdfParser:
    pass


# Override the auto-MagicMock for pdf_parser with a proper stub.
_pdf_parser_mock = MagicMock()
_pdf_parser_mock.RAGFlowPdfParser = _FakeRAGFlowPdfParser
sys.modules["deepdoc.parser.pdf_parser"] = _pdf_parser_mock

# ── Load mineru_parser directly from its file ─────────────────────────────────
_spec = importlib.util.spec_from_file_location(
    "deepdoc.parser.mineru_parser",
    _RAGFLOW_ROOT / "deepdoc" / "parser" / "mineru_parser.py",
)
_mineru_mod = importlib.util.module_from_spec(_spec)
sys.modules["deepdoc.parser.mineru_parser"] = _mineru_mod
_STUBBED_NAMES.append("deepdoc.parser.mineru_parser")
_spec.loader.exec_module(_mineru_mod)


@pytest.fixture(scope="session", autouse=True)
def _cleanup_stubs():
    yield
    sys.meta_path[:] = [f for f in sys.meta_path
                        if not isinstance(f, _DeepDocParserFinder)]
    for name in _STUBBED_NAMES:
        sys.modules.pop(name, None)
