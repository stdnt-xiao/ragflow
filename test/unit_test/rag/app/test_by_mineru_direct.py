"""Tests for by_mineru direct server URL fallback path."""
import os
from unittest.mock import MagicMock, patch


def test_by_mineru_uses_parser_config_server_url_when_no_model():
    """by_mineru creates MinerUParser directly when parser_config.mineru_server_url is set and no tenant model exists."""
    from rag.app.naive import by_mineru

    fake_sections = [("text content", "pos_tag")]
    fake_tables = []

    mock_parser_instance = MagicMock()
    mock_parser_instance.parse_pdf.return_value = (fake_sections, fake_tables)

    os.environ.pop("MINERU_APISERVER", None)

    with patch("deepdoc.parser.mineru_parser.MinerUParser", return_value=mock_parser_instance) as mock_cls:
        sections, tables, parser = by_mineru(
            filename="test.pdf",
            binary=b"fake pdf content",
            parser_config={"mineru_server_url": "http://localhost:8000"},
        )

    mock_cls.assert_called_once_with(mineru_api="http://localhost:8000", mineru_api_key="")
    assert sections == fake_sections
    assert tables == fake_tables
    assert parser is mock_parser_instance


def test_by_mineru_returns_none_without_any_server_config():
    """by_mineru returns (None, None, None) and calls callback when no model or server URL."""
    from rag.app.naive import by_mineru

    mock_callback = MagicMock()

    os.environ.pop("MINERU_APISERVER", None)

    sections, tables, parser = by_mineru(
        filename="test.pdf",
        binary=b"fake",
        callback=mock_callback,
        parser_config={},
    )

    assert sections is None
    assert tables is None
    assert parser is None
    mock_callback.assert_called_once_with(-1, "MinerU not found.")


def test_by_mineru_parser_config_url_takes_effect_over_missing_env():
    """parser_config.mineru_server_url works even when MINERU_APISERVER env var is absent."""
    from rag.app.naive import by_mineru

    mock_parser_instance = MagicMock()
    mock_parser_instance.parse_pdf.return_value = ([], [])

    os.environ.pop("MINERU_APISERVER", None)

    with patch("deepdoc.parser.mineru_parser.MinerUParser", return_value=mock_parser_instance):
        sections, tables, parser = by_mineru(
            filename="test.pdf",
            binary=b"fake",
            parser_config={"mineru_server_url": "http://custom-server:9000"},
        )

    assert parser is mock_parser_instance


def test_by_mineru_passes_api_key_from_parser_config():
    """by_mineru passes mineru_api_key from parser_config to MinerUParser."""
    from rag.app.naive import by_mineru

    mock_parser_instance = MagicMock()
    mock_parser_instance.parse_pdf.return_value = ([], [])

    os.environ.pop("MINERU_APISERVER", None)

    with patch("deepdoc.parser.mineru_parser.MinerUParser", return_value=mock_parser_instance) as mock_cls:
        by_mineru(
            filename="test.pdf",
            binary=b"fake",
            parser_config={"mineru_server_url": "https://api.mineru.net", "mineru_api_key": "sk-test-key"},
        )

    mock_cls.assert_called_once_with(mineru_api="https://api.mineru.net", mineru_api_key="sk-test-key")
