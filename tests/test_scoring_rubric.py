"""Tests for T48: Scoring rubric anchors and golden set evaluation."""
import types
from unittest.mock import MagicMock

from job_hunt import llm_utils


def _capturing_client(response_text: str):
    client = MagicMock()
    resp = MagicMock()
    resp.text = response_text
    client.models.generate_content.return_value = resp
    return client


def test_scoring_rubric_constant_present_and_has_anchors():
    """SCORING_RUBRIC must be defined and specify hard anchors for caps and high scores."""
    rubric = getattr(llm_utils, "SCORING_RUBRIC", None)
    assert rubric is not None, "SCORING_RUBRIC must be defined in job_hunt.llm_utils"

    # Must specify location / work authorization cap (<= 30)
    assert "30" in rubric and ("onsite" in rubric.lower() or "authorization" in rubric.lower() or "outside india" in rubric.lower())

    # Must specify unsuitable role cap (<= 40)
    assert "40" in rubric and ("unsuitable" in rubric.lower() or "not suitable" in rubric.lower())

    # Must specify seniority cap (<= 50)
    assert "50" in rubric and ("seniority" in rubric.lower() or "years" in rubric.lower())

    # Must specify stack mismatch cap (<= 60)
    assert "60" in rubric and ("stack" in rubric.lower() or "mismatch" in rubric.lower())

    # Must specify 85-100 criteria
    assert "85" in rubric or "100" in rubric


def test_stack_cap_has_explicit_exceptions():
    """T48 review: rule 4 capped jobs that accept a language on the resume (measured on 59 labelled
    jobs: Hotstar 'Java, Golang, or Python' and Toast 'Kotlin, Java, or another OO language' fell to
    58). The cap must say when it does NOT apply."""
    rule4 = llm_utils.SCORING_RUBRIC.split("4.")[1].split("5.")[0].lower()
    assert "every" in rule4 or "all" in rule4                     # fires only if ALL accepted languages are outside the stack
    assert "python" in rule4 and "or another" in rule4            # accepting Python / "or another language" is not a mismatch
    assert "prefer" in rule4                                       # a preferred (not mandated) stack is not a mismatch


def test_rubric_does_not_ask_for_arbitrary_score_spread():
    """Measured on 59 jobs: asking the model to 'avoid clustering' left 2 distinct scores >= 85 and a
    tie of 8, so the instruction was a no-op. Ties need sub-scores (T41), not jitter."""
    rubric = llm_utils.SCORING_RUBRIC.lower()
    assert "avoid clustering" not in rubric and "do not round" not in rubric


def test_single_scoring_prompt_includes_rubric(monkeypatch):
    """score_job_with_gemini must pass SCORING_RUBRIC to Gemini prompt."""
    client = _capturing_client('{"score": 88, "reason": "strong match"}')
    monkeypatch.setattr(
        llm_utils,
        "_get_genai_client_and_types",
        lambda api_key: (client, types.SimpleNamespace(GenerateContentConfig=MagicMock())),
    )
    job = {
        "company": "Amazon",
        "title": "Software Development Engineer II",
        "location": "Bengaluru",
        "content": "Node.js and distributed systems",
    }
    llm_utils.score_job_with_gemini(job, "Resume text", {"gemini_api_key": "dummy"})
    prompt = client.models.generate_content.call_args.kwargs["contents"]
    assert llm_utils.SCORING_RUBRIC in prompt


def test_batch_scoring_prompt_includes_rubric(monkeypatch):
    """score_jobs_batch_with_gemini must pass SCORING_RUBRIC to Gemini batch prompt."""
    client = _capturing_client('[{"job_id": "j1", "score": 88, "reason": "strong match"}]')
    monkeypatch.setattr(
        llm_utils,
        "_get_genai_client_and_types",
        lambda api_key: (client, types.SimpleNamespace(GenerateContentConfig=MagicMock())),
    )
    jobs = [
        {
            "id": "j1",
            "company": "Amazon",
            "title": "Software Development Engineer II",
            "location": "Bengaluru",
            "content": "Node.js and distributed systems",
        }
    ]
    llm_utils.score_jobs_batch_with_gemini(jobs, "Resume text", {"gemini_api_key": "dummy"})
    prompt = client.models.generate_content.call_args.kwargs["contents"]
    assert llm_utils.SCORING_RUBRIC in prompt


def _golden():
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path("scripts").resolve()))
    import score_golden_set
    return score_golden_set


def test_golden_set_csv_is_well_formed():
    """The labelled set the prompt is measured on must be sound (T48 review)."""
    from collections import Counter

    sgs = _golden()
    rows = sgs.load_golden_set()
    assert len(rows) >= 70
    assert {r["split"] for r in rows} == {"dev", "held-out"}
    c = Counter(r["label"] for r in rows)
    assert min(c.values()) >= 5 and set(c) == {"apply", "maybe", "no"}
    urls = Counter(r["url"] for r in rows)
    assert max(urls.values()) == 1, "each posting appears once"
    for r in rows:
        assert len(r["description"]) >= 300, f"{r['id']} {r['company']}: description too short to judge"
        assert r["label_source"] and r["label_reason"], f"{r['id']}: label needs a source and a reason"
    # The first builder fetched the wrong Amazon page and stored ONE description on six different
    # jobs. A posting can legitimately appear twice (same JD, two requisitions), never more.
    assert max(Counter(r["description"] for r in rows).values()) <= 2


def test_loader_rejects_bad_label_and_missing_columns(tmp_path):
    import pytest

    sgs = _golden()
    bad_label = tmp_path / "a.csv"
    bad_label.write_text("id,split,company,title,location,url,label,label_source,label_reason,description\n"
                         "1,dev,C,T,L,u,definitely,x,y,d\n")
    with pytest.raises(ValueError, match="label must be one of"):
        sgs.load_golden_set(bad_label)
    no_cols = tmp_path / "b.csv"
    no_cols.write_text("id,company\n1,C\n")
    with pytest.raises(ValueError, match="lacks columns"):
        sgs.load_golden_set(no_cols)


def test_auc_values():
    sgs = _golden()
    assert sgs.auc([90, 80, 20, 10], [True, True, False, False]) == 1.0
    assert sgs.auc([10, 20, 80, 90], [True, True, False, False]) == 0.0
    assert sgs.auc([50, 50], [True, False]) == 0.5          # a tie counts half
    assert sgs.auc([50, 60], [True, True]) != sgs.auc([50, 60], [True, True])  # undefined -> nan


def test_compute_metrics_precision_recall_false_positives_and_ties():
    sgs = _golden()
    #            apply  apply  maybe  no   no   no   apply
    scores =    [92,    88,    70,    75,  65,  30,  58]
    labels = ["apply", "apply", "maybe", "no", "no", "no", "apply"]
    m = sgs.compute_metrics(scores, labels, min_score=60)
    assert m["passes"] == 5 and m["apply_found"] == 2 and m["apply_total"] == 3
    assert m["fit_found"] == 3 and m["fit_total"] == 4
    assert m["false_positives"] == 2 and m["false_positive_indices"] == [3, 4]
    assert m["precision"] == 3 / 5 and m["recall_apply"] == 2 / 3 and m["recall_fit"] == 3 / 4
    assert m["top_count"] == 2 and m["top_distinct"] == 2 and m["max_tie_count"] == 1
    assert sgs.compute_metrics([90, 90, 90], ["apply"] * 3)["max_tie_count"] == 3
    assert sgs.compute_metrics([], [])["passes"] == 0


def test_paired_bootstrap_detects_an_obvious_ranking_gain():
    sgs = _golden()
    labels = ["apply"] * 15 + ["no"] * 15
    good = [90] * 15 + [20] * 15
    useless = [50] * 30
    med, lo, hi = sgs.paired_auc_diff_ci(useless, good, labels)
    assert med == 0.5 and lo > 0 and hi <= 0.5
    med, lo, hi = sgs.paired_auc_diff_ci(good, list(good), labels)
    assert med == 0 == lo == hi


def test_banner_only_while_labels_are_unconfirmed():
    sgs = _golden()
    rows = [{"label_source": "claude-2026-10-04"}, {"label_source": "claude-2026-10-04"}, {"label_source": "manish"}]
    text = "\n".join(sgs.banner(rows))
    assert "NOT CONFIRMED BY MANISH" in text and "2 by claude-2026-10-04" in text and "of 3 rows" in text
    assert sgs.banner([{"label_source": "manish"}] * 3) == []


def test_score_arms_failure_is_none_not_zero_and_rubric_is_restored(monkeypatch):
    """A quota error must not become a score of 0, and the module constant must be put back."""
    sgs = _golden()
    seen = []

    def fake(payload, resume, config, raise_on_error=False):
        seen.append(llm_utils.SCORING_RUBRIC)
        if payload["title"] == "boom":
            raise RuntimeError("429")
        return {"score": 77, "reason": "r"}

    monkeypatch.setattr(sgs, "score_job_with_gemini", fake)
    original = llm_utils.SCORING_RUBRIC
    jobs = [{"id": "1", "company": "C", "title": "ok", "location": "L", "description": "d"},
            {"id": "2", "company": "C", "title": "boom", "location": "L", "description": "d"}]
    out = sgs.score_arms(jobs, "resume", {}, {"off": "", "current": "RUBRIC"}, sleep_interval=0)
    assert out == {"off": {"1": 77, "2": None}, "current": {"1": 77, "2": None}}
    assert seen[:2] == ["", "RUBRIC"]            # arms really used different rubric text
    assert llm_utils.SCORING_RUBRIC == original


def test_report_from_saved_scores_cli(tmp_path):
    """The real CLI on the real golden set, with scores that rank perfectly: no API, exit 0."""
    import json
    import subprocess
    import sys

    sgs = _golden()
    rows = sgs.load_golden_set()
    perfect = {"off": {r["id"]: 50 for r in rows},
               "current": {r["id"]: {"apply": 90, "maybe": 65, "no": 30}[r["label"]] for r in rows}}
    scores = tmp_path / "s.json"
    scores.write_text(json.dumps(perfect))
    res = subprocess.run([sys.executable, "scripts/score_golden_set.py", "--from-scores", str(scores)],
                         capture_output=True, text=True)
    assert res.returncode == 0, res.stderr
    out = res.stdout
    assert "LABELS NOT CONFIRMED BY MANISH" in out
    assert "--- all:" in out and "--- dev:" in out and "--- held-out:" in out
    assert "AUC 1.000" in out and "AUC 0.500" in out
    assert "(Passed)" not in out and "improved" not in out.lower()
