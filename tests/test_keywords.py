"""T44: keyword gap analysis for `draft` — which technologies the posting names that the resume does not (no LLM)."""
import pytest

from job_hunt import drafter
from job_hunt.db import init_db, save_job
from job_hunt.keywords import find_terms, keyword_gaps
from job_hunt.models import JobPosting


@pytest.mark.parametrize("text, expected", [
    ("Strong Java and Spring Boot", {"Java", "Spring / Spring Boot"}),
    ("JavaScript and TypeScript on Node.js", {"JavaScript", "TypeScript", "Node.js"}),
    ("C#/.NET Core or C++", {"C#", ".NET", "C++"}),
    ("ASP.NET MVC", {".NET"}),
    ("Golang microservices", {"Go", "Microservices"}),
    ("We use Go and gRPC", {"Go", "gRPC"}),
    ("PostgreSQL, MySQL and MongoDB; Redis caching", {"PostgreSQL", "MySQL", "MongoDB", "Redis"}),
    ("AWS (Lambda, SQS), Kubernetes and Terraform", {"AWS", "AWS Lambda", "SQS", "Kubernetes", "Terraform"}),
    ("RESTful APIs and GraphQL", {"REST", "GraphQL"}),
    ("LLMs, RAG and LangChain", {"LLM", "RAG", "LangChain"}),
])
def test_terms_are_found_with_their_aliases(text, expected):
    assert set(find_terms(text)) == expected


@pytest.mark.parametrize("text", [
    "Go above and beyond for our customers; go to market fast",   # the English verb, not the language
    "a node in the cluster; we react quickly; take a rest",        # bare words that are not the technology
    "NoSQL stores and MySQLx",                                     # 'SQL' inside other words
    "careers.example.net and javascript-free pages",                # a domain is not .NET; 'Java' needs its own word
    "American Express card members",                               # the company, not Express.js
    "the springboard for your career; trust and safety",
])
def test_ordinary_words_are_not_technologies(text):
    found = set(find_terms(text))
    assert not found & {"Go", "Node.js", "React", "REST", "SQL", ".NET", "Java", "Express.js", "Spring / Spring Boot",
                        "Rust"}, found


def test_gaps_are_what_the_posting_names_and_the_resume_lacks():
    jd = "Backend services in Kotlin, Java or C#/.NET on AWS with Redis and DynamoDB; Node.js a plus"
    resume = "Node.js, TypeScript, Python; AWS (Lambda, SQS), Redis, MongoDB"
    gaps = keyword_gaps(jd, resume)
    assert gaps["missing"] == ["Java", "Kotlin", "C#", ".NET", "DynamoDB"]   # vocabulary order
    assert gaps["matched"] == ["Node.js", "Redis", "AWS"]


URL = "https://acme.co/jobs/1"


@pytest.fixture
def draft_env(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "resume").mkdir()
    (tmp_path / "resume" / "r.md").write_text("Node.js and TypeScript backend engineer; AWS, Redis, PostgreSQL.")
    init_db(str(tmp_path / "data" / "jobs.db"))
    save_job(JobPosting(global_id="greenhouse:acme:1", ats="greenhouse", company="Acme Co", title="Backend Engineer",
                        location="Bengaluru, India", is_remote=False, url=URL,
                        description_text="Required: Go and Kubernetes. Our stack: PostgreSQL, Redis, gRPC."))
    monkeypatch.setattr(drafter, "chat_with_llm", lambda config, messages, **k: "OUT")
    return {"candidate": {"name": "Ada", "resume_path": "resume/r.md"}}


def test_draft_writes_keyword_gaps_next_to_the_cover_letter(draft_env, tmp_path, caplog):
    import logging
    caplog.set_level(logging.INFO, logger="autopilot")
    drafter.draft_application(draft_env, URL)
    (folder,) = (tmp_path / "output").iterdir()
    text = (folder / "keyword_gaps.txt").read_text(encoding="utf-8")
    assert "In the posting, not in your resume (3): Go, gRPC, Kubernetes" in text
    assert "In both (2): PostgreSQL, Redis" in text
    assert (folder / "cover_letter_acme_co.md").exists()
    assert any("not in your resume" in r.getMessage() and "Kubernetes" in r.getMessage() for r in caplog.records)
