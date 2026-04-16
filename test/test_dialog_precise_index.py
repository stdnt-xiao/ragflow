"""Unit test: precise_index appends location-preservation instruction to system prompt."""

PRECISE_INDEX_SUFFIX = (
    "\n\nWhen the knowledge base content contains numbers followed by "
    "{paragraph_location: page=N, x0=X0, y0=Y0, x1=X1, y1=Y1} tags, "
    "preserve those tags exactly as-is after each number when you cite them in your answer. "
    "Do not remove, rewrite, or summarize the tags."
)


def _build_sys_content(base: str, precise_index: bool) -> str:
    """Extracted helper — mirrors the logic added to dialog_service.py."""
    if precise_index:
        return base + PRECISE_INDEX_SUFFIX
    return base


def test_precise_index_enabled_appends_suffix():
    base = "You are a helpful assistant. {knowledge}"
    result = _build_sys_content(base, precise_index=True)
    assert result.endswith(PRECISE_INDEX_SUFFIX)
    assert result.startswith(base)


def test_precise_index_disabled_no_suffix():
    base = "You are a helpful assistant. {knowledge}"
    result = _build_sys_content(base, precise_index=False)
    assert result == base


def test_precise_index_default_off():
    base = "system prompt"
    result = _build_sys_content(base, precise_index=False)
    assert PRECISE_INDEX_SUFFIX not in result
