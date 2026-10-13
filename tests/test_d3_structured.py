"""D3 v2 structured validator (2026-10-13 external review): wrong candidate-bound claims must be caught."""
import os, sys
import pytest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
here = os.path.join(os.path.dirname(__file__), "..")

@pytest.fixture(scope="module")
def table():
    cwd = os.getcwd(); os.chdir(here)
    try:
        import d3_report_v2 as d
        return d, d.verdict_table()
    finally:
        os.chdir(cwd)

@pytest.mark.parametrize("bad", ["VC-025 succeeded 20/20.", "VC-025 is GO.", "VC-025 took 34.3 ms end to end.",
                                 "VC-002 is NO-GO.", "VC-007 succeeded 14/15."])
def test_wrong_claims_are_caught(table, bad):
    d, t = table
    assert d.check_report(bad, t)

def test_correct_claims_pass(table):
    d, t = table
    assert not d.check_report("VC-025 is INSUFFICIENT_EVIDENCE: 19/20 against 10/10, 24.7 ms end to end.", t)
    assert not d.check_report("## 1. Recommendation", t)
