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


def test_golden_set_csv_structure_and_tiers():
    """scripts/golden_set.csv must exist, have 40 rows, required columns, and non-empty descriptions."""
    import csv
    from pathlib import Path

    csv_path = Path("scripts/golden_set.csv")
    assert csv_path.exists(), "scripts/golden_set.csv must exist"

    with open(csv_path, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    assert len(rows) >= 35, f"Expected ~40 jobs, got {len(rows)}"
    expected_fields = {"id", "company", "title", "location", "url", "old_score", "old_reason", "label", "description"}
    assert expected_fields.issubset(set(reader.fieldnames or []))

    # All descriptions must be non-empty
    for r in rows:
        assert len(r["description"].strip()) > 0, f"Empty description for job #{r['id']} ({r['company']})"
        assert r["label"] in ("apply", "maybe", "no"), f"Invalid label '{r['label']}' in job #{r['id']}"

    # Verify representation of tiers
    top = [r for r in rows if int(r["old_score"]) >= 85]
    mid = [r for r in rows if 40 <= int(r["old_score"]) < 85]
    bot = [r for r in rows if int(r["old_score"]) < 40]

    assert len(top) >= 10, f"Expected >= 10 top jobs, got {len(top)}"
    assert len(mid) >= 10, f"Expected >= 10 middle jobs, got {len(mid)}"
    assert len(bot) >= 10, f"Expected >= 10 bottom jobs, got {len(bot)}"


def test_compute_metrics_and_compare_scores():
    """Verify accuracy metrics: precision, tie shrinkage, and agreement rate."""
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path("scripts").resolve()))
    import score_golden_set

    old_scores = [90, 90, 90, 75, 75, 45, 20]
    labels = ["apply", "apply", "maybe", "no", "no", "no", "no"]

    # Baseline old metrics at min_score=60
    old_m = score_golden_set.compute_metrics(old_scores, labels, min_score=60)
    assert old_m["predicted_positives"] == 5  # 90, 90, 90, 75, 75
    assert old_m["strict_true_positives"] == 2  # 2 apply
    assert old_m["false_positives"] == 2  # 2 'no' scored 75
    assert old_m["max_tie_score"] == 90
    assert old_m["max_tie_count"] == 3  # 3 tied at 90

    # New scores where 75s (stack/location mismatches) are capped <= 60, and 90s are de-tied
    new_scores = [92, 89, 87, 55, 30, 45, 20]
    new_m = score_golden_set.compute_metrics(new_scores, labels, min_score=60)
    assert new_m["predicted_positives"] == 3  # 92, 89, 87
    assert new_m["strict_true_positives"] == 2  # 2 apply
    assert new_m["false_positives"] == 0  # 0 false positives!
    assert new_m["max_tie_count"] == 1  # No ties!

    comp = score_golden_set.compare_scores(old_scores, new_scores, labels, min_score=60)
    assert comp["precision_improved"] is True
    assert comp["tie_at_top_shrunk"] is True
    assert comp["mean_absolute_difference"] > 0


def test_golden_set_dry_run_cli(tmp_path):
    """Run score_golden_set.py with --dry-run and verify exit 0 and report output."""
    import subprocess
    import sys

    out_csv = tmp_path / "scored.csv"
    res = subprocess.run(
        [sys.executable, "scripts/score_golden_set.py", "--dry-run", "--output", str(out_csv)],
        capture_output=True,
        text=True,
    )
    assert res.returncode == 0
    assert "GOLDEN SET BENCHMARK EVALUATION" in res.stdout
    assert "SHRUNK (Passed)" in res.stdout
    assert "MAINTAINED/IMPROVED (Passed)" in res.stdout
    assert out_csv.exists()

