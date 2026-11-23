"""The answerable flag: every answerable question is answerable with its document near the top, and no
unanswerable question is."""

from __future__ import annotations

import pytest

from corunis_mcp import extract
from parish import ANSWERABLE, PDF_ANSWERABLE, UNANSWERABLE


@pytest.mark.parametrize("question,document", ANSWERABLE + PDF_ANSWERABLE)
def test_answerable(parish, question, document):
    if document.endswith(".pdf") and not extract.pdf_available():
        pytest.skip("pypdf is not installed")
    result = parish.tool_search(question)
    assert result["answerable"], (question, result["searched"])
    assert document in [p["document"] for p in result["passages"][:3]], question


@pytest.mark.parametrize("question", UNANSWERABLE)
def test_unanswerable(parish, question):
    result = parish.tool_search(question)
    assert result["answerable"] is False and result["passages"] == []
    assert result["say"] == "The documents I can see don't answer this."
