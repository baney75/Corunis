"""verify reads the whole answer, keeps only sentences its quotes support, and drops the rest."""

from __future__ import annotations

from corunis_mcp.tools import NO_ANSWER


def pid_with(parish, phrase: str) -> str:
    rows = parish.index.db.execute("SELECT pid, text FROM passages").fetchall()
    found = [pid for pid, text in rows if phrase in text]
    assert len(found) == 1, (phrase, found)
    return found[0]


def test_supported_sentence_is_kept(parish):
    pid = pid_with(parish, "vigil Mass is at 5:00 pm")
    result = parish.tool_verify(f'The Saturday vigil Mass is at 5:00 pm [{pid} "The Saturday vigil Mass is at 5:00 pm"].')
    assert len(result["kept"]) == 1 and result["dropped"] == []
    assert result["kept"][0]["citations"][0]["document"] == "spaces/everyone/bulletin-2026-10-05.md"
    assert "say" not in result


def test_fabricated_quote_is_caught(parish):
    pid = pid_with(parish, "vigil Mass is at 5:00 pm")
    result = parish.tool_verify(f'The vigil Mass is at 6:00 pm [{pid} "The Saturday vigil Mass is at 6:00 pm"].')
    assert result["kept"] == [] and result["answer"] == NO_ANSWER and result["say"] == NO_ANSWER
    assert "is not in passage" in result["dropped"][0]["reason"]


def test_unsupported_claim_on_a_real_quote_is_dropped(parish):
    roof = pid_with(parish, "Ardent Roofing bid 61,250 dollars")
    boiler = pid_with(parish, "Sterling Mechanical")
    cases = {
        f'Ardent Roofing bid 71,250 dollars [{roof} "Ardent Roofing bid 61,250 dollars"].': "71,250",
        f'The roof bid holds until March 31 [{roof} "The bid holds until January 31"].': "March",
        f'Bramble Mechanical will replace the boiler [{boiler} "replacing the boiler with Sterling Mechanical"].': "Bramble",
        f'Ardent Roofing bid 61,250 dollars in 2025 [{roof} "Ardent Roofing bid 61,250 dollars"].': "2025",
    }
    for answer, fact in cases.items():
        result = parish.tool_verify(answer)
        assert result["kept"] == [], answer
        assert fact in result["dropped"][0]["reason"], result


def test_uncited_sentence_is_dropped_and_cited_one_kept(parish):
    pid = pid_with(parish, "vigil Mass is at 5:00 pm")
    answer = (
        f'The Saturday vigil Mass is at 5:00 pm [{pid} "The Saturday vigil Mass is at 5:00 pm"]. '
        "Father Doyle usually celebrates it. Parking is free."
    )
    result = parish.tool_verify(answer)
    assert [k["sentence"] for k in result["kept"]] == [f'The Saturday vigil Mass is at 5:00 pm [{pid} "The Saturday vigil Mass is at 5:00 pm"].']
    assert {d["sentence"] for d in result["dropped"]} == {"Father Doyle usually celebrates it.", "Parking is free."}
    assert all(d["reason"] == "It cites no passage." for d in result["dropped"])
    assert "Doyle" not in result["answer"] and "Parking" not in result["answer"]


def test_list_items_and_lines_are_sentences_too(parish):
    pid = pid_with(parish, "vigil Mass is at 5:00 pm")
    answer = f'- Vigil Mass at 5:00 pm [{pid} "vigil Mass is at 5:00 pm"]\n- Sunday Mass at 9:00 am'
    result = parish.tool_verify(answer)
    assert len(result["kept"]) == 1 and result["dropped"][0]["sentence"] == "Sunday Mass at 9:00 am"


def test_abstention_alone_needs_no_citation(parish):
    result = parish.tool_verify(NO_ANSWER)
    assert result["answer"] == NO_ANSWER and result["dropped"] == []
    alongside = parish.tool_verify(NO_ANSWER + " The pastor is Father Doyle.")
    assert alongside["answer"] == NO_ANSWER and alongside["dropped"][0]["reason"] == "It cites no passage."


def test_bad_citation_form_is_named(parish):
    result = parish.tool_verify("The vigil Mass is at 5:00 pm [bulletin, page 1].")
    assert "not in the form" in result["dropped"][0]["reason"]


def test_several_citations_are_checked_as_a_union(parish):
    roof = pid_with(parish, "Ardent Roofing bid 61,250 dollars")
    boiler = pid_with(parish, "Sterling Mechanical")
    both = f'[{roof} "Ardent Roofing bid 61,250 dollars"; {boiler} "Sterling Mechanical for 18,400 dollars"]'
    kept = parish.tool_verify(f"The roof bid is 61,250 dollars and the boiler costs 18,400 dollars {both}.")
    assert len(kept["kept"]) == 1 and len(kept["kept"][0]["citations"]) == 2
    one = parish.tool_verify(f'The roof bid is 61,250 dollars and the boiler costs 18,400 dollars [{roof} "Ardent Roofing bid 61,250 dollars"].')
    assert one["kept"] == [] and "18,400" in one["dropped"][0]["reason"]
    bad = parish.tool_verify(f'The roof bid is 61,250 dollars [{roof} "Ardent Roofing bid 61,250 dollars"; {boiler} "a quote nobody wrote"].')
    assert bad["kept"] == []


def test_derived_values_are_marked_and_cite_their_inputs(parish):
    roof = pid_with(parish, "Ardent Roofing bid 61,250 dollars")
    boiler = pid_with(parish, "Sterling Mechanical")
    both = f'[{roof} "Ardent Roofing bid 61,250 dollars"; {boiler} "Sterling Mechanical for 18,400 dollars"]'
    claim = "The roof bid of 61,250 dollars and the boiler at 18,400 dollars total 79,650 dollars"
    assert len(parish.tool_verify(f"{claim} [derived 79,650] {both}.")["kept"]) == 1
    unmarked = parish.tool_verify(f"{claim} {both}.")
    assert unmarked["kept"] == [] and "79,650" in unmarked["dropped"][0]["reason"]
    one_input = parish.tool_verify(f'{claim} [derived 79,650] [{roof} "Ardent Roofing bid 61,250 dollars"].')
    assert one_input["kept"] == [] and "18,400" in one_input["dropped"][0]["reason"]
    no_citation = parish.tool_verify("Together they total 79,650 dollars [derived 79,650].")
    assert no_citation["kept"] == [] and no_citation["dropped"][0]["reason"] == "It cites no passage."


def test_quote_punctuation_is_normalized(parish):
    pid = pid_with(parish, "vigil Mass is at 5:00 pm")
    curly = parish.tool_verify(f"The vigil Mass is at 5:00 pm [{pid} “The Saturday vigil Mass is at 5:00 pm”].")
    assert len(curly["kept"]) == 1, curly
