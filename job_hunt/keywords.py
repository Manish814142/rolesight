"""Keyword gap analysis for `draft` (T44): the technologies a posting names that the resume does not.

Deterministic and free (no LLM call): a fixed vocabulary of tech terms, each with the spellings it goes by. A word that
is also ordinary English (Go, Spring, React, REST, SAP, RAG, ML…) is matched with its capitalisation only, and some
need context ("Express" counts only as Express.js / next to Node), so a gap list is a hint to read the posting, not a
verdict: it cannot tell a requirement from an example ("languages such as Kotlin, Java or C#"). Vocabulary order is
the report order.
"""
from __future__ import annotations

import re
from typing import Dict, List, Pattern, Tuple

_I = re.IGNORECASE

# (canonical name, pattern). A pattern compiled without re.IGNORECASE is case-sensitive on purpose.
_VOCABULARY: List[Tuple[str, Pattern[str]]] = [(name, re.compile(rx, flags)) for name, rx, flags in [
    # languages and runtimes
    ("Python", r"\bpython\b", _I),
    ("Java", r"\bjava\b(?!\s*script)(?!-)", _I),
    ("JavaScript", r"\bjava\s*script\b|\becmascript\b", _I),
    ("TypeScript", r"\btype\s*script\b", _I),
    ("Node.js", r"\bnode\.?js\b", _I),
    ("Go", r"\b[Gg]olang\b|\bGo\b(?!\s*-?\s*(to|through|above|beyond|ahead|back|out|over|live|on|for|get)\b)", 0),
    ("Kotlin", r"\bkotlin\b", _I),
    ("Scala", r"\bscala\b", _I),
    ("C#", r"(?<![\w#])c\s?#(?![\w#])|\bc-?sharp\b", _I),
    (".NET", r"(?<![\w.])\.net\b|\basp\.net\b|\bdotnet\b", _I),
    ("C++", r"(?<![\w+])c\s?\+\+(?!\+)", _I),
    ("Rust", r"\bRust\b", 0),
    ("Ruby", r"\bruby\b", _I),
    ("PHP", r"\bphp\b", _I),
    ("Swift", r"\bSwift\b", 0),
    ("Elixir", r"\belixir\b", _I),
    ("SQL", r"\bSQL\b", 0),
    ("Bash / shell", r"\bbash\b|\bshell\s+script", _I),
    # frameworks and APIs
    ("Express.js", r"\bexpress\.?js\b|\bnode(\.?js)?\s*(/|and|\+|,|with)\s*express\b", _I),
    ("NestJS", r"\bnest\.?js\b", _I),
    ("Spring / Spring Boot", r"\bSpring\b(?!\s*(board|time|semester))", 0),
    ("Django", r"\bdjango\b", _I),
    ("Flask", r"\bFlask\b", 0),
    ("FastAPI", r"\bfast\s?api\b", _I),
    ("Ruby on Rails", r"\bruby\s+on\s+rails\b|\bRails\b", 0),
    ("React", r"\bReact(\.?js|JS| Native)?\b", 0),
    ("Angular", r"\bangular(\.?js)?\b", _I),
    ("Vue", r"\bvue(\.?js)?\b", _I),
    ("Next.js", r"\bnext\.?js\b", _I),
    ("GraphQL", r"\bgraph\s?ql\b", _I),
    ("gRPC", r"\bgrpc\b", _I),
    ("REST", r"\bREST(ful)?\b|\bRESTful\b", 0),
    # data stores, queues, data platforms
    ("PostgreSQL", r"\bpostgres(ql)?\b", _I),
    ("MySQL", r"\bmysql\b", _I),
    ("MongoDB", r"\bmongo(db)?\b", _I),
    ("Redis", r"\bredis\b", _I),
    ("DynamoDB", r"\bdynamo\s?db\b", _I),
    ("Cassandra", r"\bcassandra\b", _I),
    ("Elasticsearch", r"\belastic\s?search\b|\bopensearch\b", _I),
    ("Kafka", r"\bkafka\b", _I),
    ("RabbitMQ", r"\brabbit\s?mq\b", _I),
    ("SQS", r"\bsqs\b", _I),
    ("Kinesis", r"\bkinesis\b", _I),
    ("Spark", r"\b(py)?spark\b", _I),
    ("Hadoop", r"\bhadoop\b", _I),
    ("Airflow", r"\bairflow\b", _I),
    ("Snowflake", r"\bSnowflake\b", 0),
    ("BigQuery", r"\bbig\s?query\b", _I),
    ("Databricks", r"\bdatabricks\b", _I),
    # cloud, infrastructure, delivery
    ("AWS", r"\baws\b|\bamazon\s+web\s+services\b", _I),
    ("AWS Lambda", r"\blambda\b", _I),
    ("GCP", r"\bgcp\b|\bgoogle\s+cloud\b", _I),
    ("Azure", r"\bazure\b", _I),
    ("Kubernetes", r"\bkubernetes\b|\bk8s\b", _I),
    ("Docker", r"\bdocker\b", _I),
    ("Terraform", r"\bterraform\b", _I),
    ("Helm", r"\bHelm\b", 0),
    ("Jenkins", r"\bjenkins\b", _I),
    ("GitHub Actions", r"\bgithub\s+actions\b", _I),
    ("CI/CD", r"\bci\s?/\s?cd\b|\bcontinuous\s+(integration|delivery|deployment)\b", _I),
    ("Linux", r"\blinux\b", _I),
    ("Microservices", r"\bmicro-?\s?services?\b", _I),
    # AI / ML
    ("LLM", r"\bLLMs?\b|\blarge\s+language\s+models?\b", 0),
    ("GenAI", r"\bgen\s?ai\b|\bgenerative\s+ai\b", _I),
    ("RAG", r"\bRAG\b", 0),
    ("LangChain", r"\blang\s?chain\b", _I),
    ("PyTorch", r"\bpytorch\b", _I),
    ("TensorFlow", r"\btensor\s?flow\b", _I),
    ("Machine learning", r"\bmachine\s+learning\b|\bML\b", 0),
    # enterprise platforms (the T12 / T73 kind of requirement)
    ("Salesforce", r"\bsalesforce\b", _I),
    ("SAP", r"\bSAP\b", 0),
    ("ServiceNow", r"\bservicenow\b", _I),
]]


def find_terms(text: str) -> List[str]:
    """The vocabulary terms that occur in `text`, in vocabulary order."""
    return [name for name, rx in _VOCABULARY if rx.search(text or "")]


def keyword_gaps(jd: str, resume: str) -> Dict[str, List[str]]:
    """{"missing": terms the posting names that the resume does not, "matched": terms in both}, vocabulary order."""
    in_resume = set(find_terms(resume))
    named = find_terms(jd)
    return {"missing": [t for t in named if t not in in_resume], "matched": [t for t in named if t in in_resume]}


def gap_report(gaps: Dict[str, List[str]], title: str = "") -> str:
    """The text of keyword_gaps.txt."""
    missing, matched = gaps["missing"], gaps["matched"]
    return "\n".join([
        f"Keyword gaps{': ' + title if title else ''}",
        "(fixed vocabulary of tech terms found in the posting and in your resume; no LLM)",
        "",
        f"In the posting, not in your resume ({len(missing)}): {', '.join(missing) or '-'}",
        f"In both ({len(matched)}): {', '.join(matched) or '-'}",
        "",
        "Check in the posting whether each missing term is required (qualifications) or only an example or a plus.",
        "",
    ])
