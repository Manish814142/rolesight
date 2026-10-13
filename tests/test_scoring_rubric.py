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

    # Must specify a stack mismatch cap (<= 50 since T73, so a capped job fails MIN_SCORE 60 too)
    assert "stack mismatch cap (score <= 50)" in rubric.lower()

    # Must specify 85-100 criteria
    assert "85" in rubric or "100" in rubric


def test_stack_cap_has_explicit_exceptions():
    """T48 review: rule 4 capped jobs that accept a language on the resume (measured on 59 labelled
    jobs: Hotstar 'Java, Golang, or Python' and Toast 'Kotlin, Java, or another OO language' fell to
    58). The cap must say when it does NOT apply."""
    rule4 = llm_utils.SCORING_RUBRIC.split("4. ")[1].split("5. ")[0].lower()
    assert "requirements or qualifications" in rule4 and "accept none of the candidate's languages" in rule4
    assert "python" in rule4 and "any, another" in rule4          # accepting Python / "another language" is not a mismatch
    assert "prefer" in rule4                                       # a preferred (not mandated) stack is not a mismatch
    assert "java, golang, or python\" is not a mismatch" in rule4


def test_platform_cap_judges_the_work_not_the_employer_name():
    """T58 evaluation: with rule 7 added, ServiceNow's own 2-5 yr Python integration engineer (a software
    role at the company that makes the platform) fell 90 -> 40 on two runs, capped as 'ServiceNow
    platform administration'. The cap must be about the work, not the company name."""
    rule2 = llm_utils.SCORING_RUBRIC.split("2.")[1].split("3.")[0].lower()
    assert "40" in rule2 and ("administer" in rule2 or "administration" in rule2)
    assert "not the employer" in rule2
    assert "software engineer building" in rule2 and "servicenow" in rule2 and "is not platform administration" in rule2


def test_too_junior_cap_judges_by_experience_asked_not_by_title():
    """T58: a fresher-level 'Associate SDE' scored 88-90 under every prompt. But 'Associate' is not junior
    everywhere (Amgen: 'Associate Software Engineer' asks 2-6 yrs, 'Sr Associate' 4-9; Thermo 'Software
    Engineer I' asks 3+), so the cap must key on what the posting asks for."""
    rule7 = llm_utils.SCORING_RUBRIC.split("7.")[1].lower()
    assert "50" in rule7
    assert "fresher" in rule7 and "graduate" in rule7 and "0-1" in rule7
    assert "not by the title" in rule7 or "not the title" in rule7
    assert "3+" in rule7                      # an 'Associate'/'Engineer I' that asks for 3+ years is not too junior


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


def test_score_arms_can_score_a_structured_arm(monkeypatch):
    """T41: the harness compares the structured method with the rubric arms on the same jobs."""
    sgs = _golden()
    monkeypatch.setattr(sgs, "score_job_with_gemini", lambda *a, **k: {"score": 77, "reason": "r"})
    monkeypatch.setattr(sgs, "score_job_structured_with_gemini", lambda *a, **k: {"score": 55, "reason": "r"})
    jobs = [{"id": "1", "company": "C", "title": "T", "location": "L", "description": "d"}]
    out = sgs.score_arms(jobs, "resume", {}, {"current": "RUBRIC", "structured": sgs.STRUCTURED_ARM}, sleep_interval=0)
    assert out == {"current": {"1": 77}, "structured": {"1": 55}}


def test_variance_report_counts_wide_spreads_and_decision_flips(tmp_path):
    import json
    import subprocess
    import sys

    runs = {"a": [90, 90, 90], "b": [45, 85, 50], "c": [58, 62, 61], "d": [75, 75, 69]}
    sys.path.insert(0, "scripts")
    import measure_score_variance as msv

    rep = msv.spread_report(runs)
    assert rep["wide"] == ["b"] and rep["jobs"] == 4
    assert rep["flips"][60] == ["b", "c"] and rep["flips"][70] == ["b", "d"]
    f = tmp_path / "runs.json"
    f.write_text(json.dumps(runs))
    res = subprocess.run([sys.executable, "scripts/measure_score_variance.py", "--from-runs", str(f)], capture_output=True, text=True)
    assert res.returncode == 0, res.stderr
    assert "4 jobs" in res.stdout and "['b']" in res.stdout


# --- T70: compare Gemini models on the golden set -------------------------------------------------------------

def test_score_arms_with_a_pinned_model_never_falls_back(monkeypatch):
    """Comparing models needs every score from the named model. The normal chain silently answers from the
    fallback model when the first fails (on 2026-10-06 about 9 of T60's 200 calls did); --model forbids that."""
    import types
    from unittest.mock import MagicMock

    sgs = _golden()
    monkeypatch.setattr(llm_utils.time, "sleep", lambda s: None)
    calls = []
    client = MagicMock()

    def generate(model, contents, config):
        calls.append(model)
        if model == "m-pinned":
            raise Exception("503 UNAVAILABLE")
        return types.SimpleNamespace(text='{"score": 88, "reason": "answered by another model"}')

    client.models.generate_content.side_effect = generate
    monkeypatch.setattr(llm_utils, "_get_genai_client_and_types",
                        lambda api_key: (client, types.SimpleNamespace(GenerateContentConfig=MagicMock())))
    jobs = [{"id": "1", "company": "C", "title": "T", "location": "L", "description": "d"}]
    config = {"gemini_api_key": "k", "gemini_model": "m-pinned"}

    assert sgs.score_arms(jobs, "r", config, {"current": "RUBRIC"}, sleep_interval=0) == {"current": {"1": 88}}
    calls.clear()
    out = sgs.score_arms(jobs, "r", config, {"current": "RUBRIC"}, sleep_interval=0, model="m-pinned")
    assert out == {"current": {"1": None}} and set(calls) == {"m-pinned"}
    assert llm_utils._gemini_models({})[0] != "m-pinned"          # the chain is restored afterwards


def test_score_agreement_between_two_arms():
    sgs = _golden()
    a = {"1": 90, "2": 50, "3": 70, "4": 65}
    b = {"1": 80, "2": 50, "3": 60, "4": None}           # job 4 failed in b: left out, never counted as 0
    ag = sgs.score_agreement(a, b, (60, 70))
    assert ag["jobs"] == 3 and abs(ag["mean_abs_diff"] - 20 / 3) < 1e-9 and ag["within_10"] == 3
    assert ag["decision_changes"] == {60: [], 70: ["3"]}


def test_main_names_arms_after_a_pinned_model_and_scores_only_the_chosen_arms(tmp_path, monkeypatch):
    import json

    sgs = _golden()
    resume = tmp_path / "r.md"
    resume.write_text("Node.js")
    monkeypatch.setattr(sgs, "load_config", lambda: {"candidate": {"resume_path": str(resume)}})
    seen = {}

    def fake_score_arms(jobs, resume_text, config, arms, sleep_interval=4.2, model=None):
        seen.update(arms=dict(arms), model=model, n=len(jobs))
        return {name: {j["id"]: 70 for j in jobs} for name in arms}

    monkeypatch.setattr(sgs, "score_arms", fake_score_arms)
    out = tmp_path / "s.json"
    assert sgs.main(["--arms", "current", "--model", "gemini-x", "--limit", "2", "--save-scores", str(out)]) == 0
    assert seen == {"arms": {"current@gemini-x": llm_utils.SCORING_RUBRIC}, "model": "gemini-x", "n": 2}
    assert list(json.loads(out.read_text())) == ["current@gemini-x"]


def test_from_scores_merges_several_files_and_prints_agreement(tmp_path):
    import json
    import subprocess
    import sys

    sgs = _golden()
    rows = sgs.load_golden_set()
    f1, f2 = tmp_path / "a.json", tmp_path / "b.json"
    f1.write_text(json.dumps({"current@m1": {r["id"]: {"apply": 90, "maybe": 65, "no": 30}[r["label"]] for r in rows}}))
    f2.write_text(json.dumps({"current@m2": {r["id"]: {"apply": 85, "maybe": 75, "no": 30}[r["label"]] for r in rows}}))
    res = subprocess.run([sys.executable, "scripts/score_golden_set.py", "--from-scores", str(f1), str(f2)],
                         capture_output=True, text=True)
    assert res.returncode == 0, res.stderr
    assert "current@m1" in res.stdout and "current@m2" in res.stdout
    n_fit = sum(r["label"] != "no" for r in rows)
    expected = (5 * sum(r["label"] == "apply" for r in rows) + 10 * sum(r["label"] == "maybe" for r in rows)) / len(rows)
    assert f"current@m1 vs current@m2: {len(rows)} jobs, mean |difference| {expected:.1f}" in res.stdout
    assert "maybe" in res.stdout and n_fit > 0
    dup = subprocess.run([sys.executable, "scripts/score_golden_set.py", "--from-scores", str(f1), str(f1)],
                         capture_output=True, text=True)
    assert dup.returncode != 0 and "twice" in dup.stderr


def test_variance_script_can_pin_a_model_and_pick_jobs(tmp_path, monkeypatch):
    """T70: re-checking T60 on one model means named jobs, that model only, and the chain restored after."""
    import json
    import sys

    sys.path.insert(0, "scripts")
    import measure_score_variance as msv

    resume = tmp_path / "r.md"
    resume.write_text("Node.js")
    monkeypatch.setattr(msv, "load_config", lambda: {"candidate": {"resume_path": str(resume)}})
    monkeypatch.setattr(msv.time, "sleep", lambda s: None)
    seen = []

    def fake(payload, resume_text, config, raise_on_error=False):
        seen.append((payload["title"], llm_utils._gemini_models(config), config.get("gemini_temperature")))
        return {"score": 60, "reason": "r"}

    monkeypatch.setattr(msv, "score_job_with_gemini", fake)
    out = tmp_path / "runs.json"
    assert msv.main(["--ids", "g27,ab5", "--runs", "2", "--model", "gemini-x", "--temperature", "0",
                     "--save", str(out)]) == 0
    assert sorted(json.loads(out.read_text())) == ["ab5", "g27"]
    assert len(seen) == 4 and all(models == ["gemini-x"] and temp == 0 for _, models, temp in seen)
    assert llm_utils._gemini_models({})[0] != "gemini-x"


def test_variance_script_can_read_another_labelled_set(tmp_path, monkeypatch):
    """T79: Notion's FDE role (ai65) is in the AI set, not in golden_set.csv, so re-scoring it needs --csv."""
    import json
    import sys

    sys.path.insert(0, "scripts")
    import measure_score_variance as msv

    resume = tmp_path / "r.md"
    resume.write_text("Node.js")
    monkeypatch.setattr(msv, "load_config", lambda: {"candidate": {"resume_path": str(resume)}})
    monkeypatch.setattr(msv.time, "sleep", lambda s: None)
    titles = []
    monkeypatch.setattr(msv, "score_job_with_gemini",
                        lambda payload, resume_text, config, raise_on_error=False: titles.append(payload["title"]) or {"score": 70, "reason": "r"})
    out = tmp_path / "runs.json"
    assert msv.main(["--csv", "scripts/golden_set_ai.csv", "--ids", "ai65", "--runs", "3", "--save", str(out)]) == 0
    assert json.loads(out.read_text()) == {"ai65": [70, 70, 70]}
    assert len(titles) == 3 and all("Forward Deployed" in t for t in titles)


# --- T73: rubric v6, Manish's apply rule (skip a posting that requires what he lacks) --------------------------

def _rule(n):
    return llm_utils.SCORING_RUBRIC.split(f"{n}. ")[1].split(f"{n + 1}. ")[0].lower()


def test_stack_cap_sits_below_every_min_score_in_use():
    """Rule 4 capped at 60 = MIN_SCORE 60, so a capped job still passed (Nike g16: 60 under the old rubric)."""
    import re
    cap = int(re.search(r"score <= (\d+)", _rule(4)).group(1))
    assert cap < 60


def test_example_lists_and_frontend_typescript_are_handled():
    """Measured 2026-10-07: 'languages such as Kotlin, Java or C#' was read as a requirement (Expedia g1, an
    `apply` job, fell to 50 under v5), and Sureify's 'Golang required + React/TS' passed at 75 because TypeScript
    appeared somewhere in the posting."""
    rule4 = _rule(4)
    assert "such as" in rule4 and "only as examples" in rule4 and "are not requirements" in rule4
    assert "languages such as kotlin, java or c#\" with qualifications asking for any language are a stretch" in rule4
    assert "frontend part does not count" in rule4 and "golang required, react/typescript frontend\" is" in rule4


def test_required_domain_or_tool_cap():
    """Manish 2026-10-07: he skips postings that require a domain or tool he lacks (golden-set g27: video games)."""
    rule8 = llm_utils.SCORING_RUBRIC.split("8. ")[1].lower()
    assert "score <= 50" in rule8 and "required" in rule8 and "video-games industry" in rule8
    assert "preferred or nice-to-have" in rule8 and "never trigger" in rule8


def test_languages_named_only_in_the_responsibilities_are_a_stretch_not_a_cap():
    """T73 review (claude-b, 2026-10-08): under v6, golden-set `apply` job g1 (Expedia: qualifications ask for any
    language; Kotlin/Java/C# appear only in "you will build ... using languages such as") scored 50 in 10 of 11 runs.
    v7 counts only the requirements: g1 75-85 in 5 of 5 runs, false positives still 0 (two full runs)."""
    rule4 = _rule(4)
    assert "only in the responsibilities" in rule4 and "are not requirements" in rule4
    assert "stack stretch (rule 6, moderate match), not a cap" in rule4


def test_ai_specialisation_is_a_missing_required_domain():
    """T74 (Manish, 2026-10-10): AI/FDE titles reach Gemini, but he applies only when the posting accepts his
    Node/Python backend stack plus GenAI use in workflows; heavy AI (LangChain/LangGraph, vector DBs, fine-tuning ...) is a
    domain he lacks. Measured on 75 AI/FDE postings (scripts/golden_set_ai.csv): the v7 text passed 18 of 65 `no` jobs at 70."""
    rule8 = llm_utils.SCORING_RUBRIC.split("8. ")[1].lower()
    for term in ("langchain", "langgraph", "vector database", "fine-tuning", "pytorch", "mlops", "rag"):
        assert term in rule8, term
    assert "inside backend services" in rule8                       # what he has done: not a mismatch
    assert "only preferred" in rule8 and "prompt engineering or workflow automation" in rule8
    assert "does not hide the requirement" in rule8                 # "frameworks such as LangGraph" is still a requirement


def test_ai_clause_caps_hands_on_requirements_not_familiarity():
    """T74, first measurement (3.5, three runs each): a clause that capped any mention of RAG / agent frameworks in the
    requirements took DevRev's Forward Deployed Engineer ('familiarity with LLMs, prompt engineering, RAG and function
    calling') from 75, 75, 75 to 45, 45, 45. Familiarity is not the skill he lacks; building these systems is."""
    rule8 = llm_utils.SCORING_RUBRIC.split("8. ")[1].lower()
    assert "hands-on experience building or operating" in rule8
    assert "familiarity or a basic understanding" in rule8


def test_ai_clause_ignores_bonus_and_preferred_sections():
    """T74, golden-set regression (3.5, v8b): MongoDB 'Software Engineer 3' (apply, 90 under v7) fell to 45 because its
    'Bonus Round' (vector databases, agent orchestration such as LangGraph) was read as required. Sections called
    bonus / preferred / nice to have / a plus never trigger the cap, whatever they name."""
    rule8 = llm_utils.SCORING_RUBRIC.split("8. ")[1].lower()
    assert "bonus" in rule8 and "good to have" in rule8 and "even when they name" in rule8


def test_ai_golden_set_is_well_formed():
    """scripts/golden_set_ai.csv (T74): 75 AI / Forward Deployed Engineer postings, India, fetched 2026-10-10, labelled by
    Claude against Manish's stated rule (allow only if the posting accepts his Node/Python backend stack plus GenAI use in
    workflows; not if it requires LangChain/LangGraph, vector databases, fine-tuning or other heavy AI). Not confirmed by him."""
    rows = _golden().load_golden_set("scripts/golden_set_ai.csv")
    assert len(rows) == 75
    assert len({r["id"] for r in rows}) == 75 and all(r["id"].startswith("ai") for r in rows)
    assert {r["label"] for r in rows} <= {"apply", "maybe", "no"}
    assert sum(r["label"] != "no" for r in rows) == 9          # the allowed ones: 1 apply, 8 maybe (ai54 was relabelled no on re-reading)
    assert all(len(r["description"]) > 1000 and r["label_reason"] for r in rows)
    assert {r["label_source"] for r in rows} == {"claude-2026-10-10"}      # none confirmed by Manish yet


def test_variance_script_survives_a_failed_call(tmp_path, monkeypatch):
    """Review of T79 (2026-10-13): one 503 from an overloaded Gemini aborted a 20-run measurement and saved nothing.
    A failed call is now skipped (never stored as a score) and the other runs are kept."""
    import json
    import sys

    sys.path.insert(0, "scripts")
    import measure_score_variance as msv

    resume = tmp_path / "r.md"
    resume.write_text("Node.js")
    monkeypatch.setattr(msv, "load_config", lambda: {"candidate": {"resume_path": str(resume)}})
    monkeypatch.setattr(msv.time, "sleep", lambda s: None)
    calls = []

    def flaky(payload, resume_text, config, raise_on_error=False):
        calls.append(1)
        if len(calls) == 2:
            raise RuntimeError("503 UNAVAILABLE")
        return {"score": 75, "reason": "r"}

    monkeypatch.setattr(msv, "score_job_with_gemini", flaky)
    out = tmp_path / "runs.json"
    assert msv.main(["--csv", "scripts/golden_set_ai.csv", "--ids", "ai65", "--runs", "3", "--save", str(out)]) == 0
    assert json.loads(out.read_text()) == {"ai65": [75, 75]}
