"""T103: the title filter is plain word lists in config.json (candidate.titles), with Manish's as the defaults.

The defaults must make exactly the decisions the hand-written regexes made before T103. Those regexes are frozen below as the
reference (copied from job_hunt/prefilter.py at 7646740); measured on 2026-10-14 over the 34,624 distinct titles of the saved
fetch and the production database: 0 decisions differ.
"""
import csv
import re
from pathlib import Path

import pytest

from job_hunt import prefilter
from job_hunt.models import JobPosting
from job_hunt.prefilter import TitleRules, TitleRulesError

ROOT = Path(__file__).resolve().parent.parent

# -- the reference: the title regexes as they were before T103 --------------------------------------------------------------
_OLD_INCLUDE = re.compile(
    r"\b(back[\s-]?end|node(\.?js)?|sde\d*|software\s*engineer|software\s+dev(elopment)?\s+engineer"
    r"|member\s+of\s+technical\s+staff|mts|computer\s+scientist|developer|full[\s-]*stack"
    r"|api|distributed(\s*systems)?|platform\s*engineer|product\s*engineer"
    r"|infrastructure\s*engineer|systems\s*engineer"
    r"|(gen(erative)?[\s-]*ai|agentic[\s-]+ai|applied[\s-]+ai|ai|llm)[\s-]+engineer|forward[\s-]*deployed[\s-]+engineer)\b",
    re.IGNORECASE,
)
_OLD_GENERIC = re.compile(r"^\s*(?:(?:senior|sr\.?|associate)\s+)?engineer\b|\bsoftware\b.*\bengineer\b", re.IGNORECASE)
_OLD_PLATFORM = (
    r"salesforce|apex|servicenow|dynamics(\s*365)?|d365|sap|abap|netsuite|peoplesoft|coupa|workday"
    r"|cpq|zuora|mulesoft|boomi|informatica|tableau|bi|rpa|uipath|reltio|lims|mainframe|cobol"
    r"|sharepoint|siebel|pega|agentforce"
)
_OLD_EXCLUDE = re.compile(
    r"\b(lead|principal|(?<!technical\s)staff|manager|director|architect|front[\s-]?end"
    r"|react(\.?js)?|angular(js)?|vue(\.?js)?|ios|android|flutter|qa|quality|test(er|ers|ing)?"
    r"|intern(s|ship)?|devops|sre|java|golang|advocate|advocacy|evangelist|devrel)\b"
    r"|\.net\b|\bc#(?!\w)|\bdeveloper\s+relations\b"
    rf"|\b({_OLD_PLATFORM})\b"
    r"|\boracle\s+(ebs|fusion|hcm|erp|cpq|apps|cloud)\b|\bpower\s*(bi|platform|apps|automate)\b"
    r"|\bblue\s*prism\b|\bmarketing\s+cloud\b"
    r"|(?<![\w+])c\+\+|\b(embedded(?!\s+(?:finance|payments?|banking|insurance|lending)\b)|firmware|kernel|gpu|cuda|fpga|verilog|rust|ruby|php)\b",
    re.IGNORECASE,
)


def _old_passes(title):
    return not _OLD_EXCLUDE.search(title) and bool(_OLD_INCLUDE.search(title) or _OLD_GENERIC.search(title))


# Titles the old rules were written for (their comments and earlier tests), plus every labelled posting's title.
TRICKY = [
    "Senior Backend Engineer", "Back-End Developer", "Backend Engineer II", "Node.js Developer", "NodeJS Engineer", "SDE2", "SDE-2",
    "SDE II", "SDET", "Software Engineer", "Software Dev Engineer", "Software Development Engineer III", "Member of Technical Staff",
    "Lead Member of Technical Staff", "Staff Software Engineer", "Technical Staff Engineer", "MTS 3", "Computer Scientist",
    "Full Stack Developer", "Fullstack Engineer", "Full-Stack Engineer", "API Engineer", "Distributed Systems Engineer",
    "Platform Engineer", "Product Engineer", "Infrastructure Engineer", "Systems Engineer", "GenAI Engineer", "Gen-AI Engineer",
    "Generative AI Engineer", "Agentic AI Engineer", "Applied AI Engineer", "AI Engineer", "LLM Engineer", "AI / ML Engineer",
    "Forward Deployed Engineer", "Forward-Deployed Engineer", "Senior Engineer", "Engineer II", "Sr. Engineer 3", "Associate Engineer",
    "Engineer III, Software", "Data Engineer", "Cloud Engineer", "Engineering Specialist", "Engineers Wanted",
    "Engineering Manager", "Principal Engineer", "Tech Lead", "Solutions Architect", "Director of Engineering",
    "Frontend Engineer", "Front-End Developer", "Front End Developer", "React Developer", "ReactJS Developer", "React.js Engineer",
    "Angular Developer", "AngularJS Developer", "Vue.js Developer", "iOS Developer", "Android Engineer", "Flutter Developer",
    "QA Engineer", "Software Quality Engineer", "Test Engineer", "Software Tester", "Testing Lead", "Software Engineer Intern",
    "Interns - Backend", "Backend Internship", "DevOps Engineer", "SRE", "Java Developer", "Golang Engineer", "JavaScript Developer",
    "Python Developer", "Developer Advocate", "Developer Relations Engineer", "Tech Evangelist", "DevRel Engineer",
    ".NET Developer", "ASP.NET Developer", "C# Developer", "C++ Developer", "C/C++ Engineer", "Salesforce Developer",
    "Apex Developer", "ServiceNow Developer", "Dynamics 365 Developer", "D365 Developer", "SAP ABAP Developer", "Workday Developer",
    "Power BI Developer", "PowerBI Developer", "Power Platform Developer", "Blue Prism Developer", "Marketing Cloud Developer",
    "Oracle EBS Developer", "Oracle Fusion Developer", "Oracle-ERP Tester, Senior", "Oracle Developer", "BI Developer",
    "RPA Developer", "Mainframe Developer", "Embedded Software Engineer", "Backend Engineer - Embedded Finance",
    "Embedded Payments Engineer", "Firmware Engineer", "Kernel Developer", "GPU Software Engineer", "CUDA Engineer",
    "FPGA Engineer", "Rust Developer", "Ruby on Rails Developer", "PHP Developer", "Software Engineer, Payments",
    "Sr Software Application Engineer", "Customer Success Manager", "Business Analyst",
]


def _labelled_titles():
    out = []
    for name in ("golden_set.csv", "golden_set_ai.csv"):
        with (ROOT / "scripts" / name).open(newline="", encoding="utf-8") as fh:
            out += [row["title"] for row in csv.DictReader(fh)]
    return out


@pytest.mark.parametrize("title", sorted(set(TRICKY + _labelled_titles())))
def test_the_default_word_lists_decide_every_title_as_the_old_regexes_did(title):
    assert prefilter.title_is_candidate(title) == _old_passes(title)


def _job(title, location="Bengaluru, India"):
    return JobPosting(global_id="t:1", ats="t", company="c", title=title, location=location, is_remote=False, url="https://x")


# -- the word grammar -------------------------------------------------------------------------------------------------------

def _rules(**kw):
    base = {"include": [], "exclude": [], "exceptions": [], "generic_engineer_titles": False}
    return TitleRules.from_config({"candidate": {"titles": {**base, **kw}}})


def test_an_entry_matches_whole_words_in_any_case():
    prefilter.use_title_rules(_rules(include=["java developer"]))
    assert prefilter.title_is_candidate("Senior JAVA Developer")
    assert not prefilter.title_is_candidate("JavaScript Developer")     # "java" is not a word of "JavaScript"


def test_spaces_and_hyphens_inside_an_entry_are_optional():
    prefilter.use_title_rules(_rules(include=["back end"]))
    for title in ("Back End Engineer", "Back-End Engineer", "Backend Engineer", "back - end dev"):
        assert prefilter.title_is_candidate(title), title


def test_entries_with_symbols_keep_their_own_boundaries():
    prefilter.use_title_rules(_rules(include=["engineer"], exclude=[".net", "c#", "c++"]))
    for title in ("ASP.NET Engineer", ".NET Engineer", "C# Engineer", "C++ Engineer", "C/C++ Engineer"):
        assert not prefilter.title_is_candidate(title), title
    assert prefilter.title_is_candidate("Network Engineer")              # ".net" is not inside "Network"
    assert prefilter.title_is_candidate("Cloud Engineer")                # "c#" / "c++" need the symbol


def test_exclude_wins_over_include_and_an_exception_lifts_it():
    prefilter.use_title_rules(_rules(include=["engineer"], exclude=["staff", "embedded"], exceptions=["technical staff", "embedded finance"]))
    assert not prefilter.title_is_candidate("Staff Engineer")
    assert prefilter.title_is_candidate("Member of Technical Staff Engineer")
    assert not prefilter.title_is_candidate("Embedded Systems Engineer")
    assert prefilter.title_is_candidate("Embedded Finance Engineer")
    assert not prefilter.title_is_candidate("Staff Engineer, Embedded Finance")   # the exception lifts only its own words


def test_the_generic_engineer_switch():
    prefilter.use_title_rules(_rules(include=["developer"], generic_engineer_titles=True))
    assert prefilter.title_is_candidate("Senior Engineer") and prefilter.title_is_candidate("Engineer III, Software")
    prefilter.use_title_rules(_rules(include=["developer"], generic_engineer_titles=False))
    assert not prefilter.title_is_candidate("Senior Engineer")


def test_the_rejection_reason_names_the_excluded_word():
    prefilter.use_title_rules(_rules(include=["developer"], exclude=["java"]))
    assert prefilter.should_evaluate_job(_job("Java Developer")) == (False, "Title matched exclude pattern: 'Java'")
    assert prefilter.should_evaluate_job(_job("Data Analyst")) == (False, "Title did not match include pattern")


# -- reading candidate.titles -----------------------------------------------------------------------------------------------

def test_no_titles_block_means_the_defaults():
    rules = TitleRules.from_config({"candidate": {"name": "x"}})
    assert rules == TitleRules()
    assert "backend" not in rules.include and "back end" in rules.include and "java" in rules.exclude


def test_a_titles_block_is_taken_as_written_missing_lists_are_empty():
    rules = TitleRules.from_config({"candidate": {"titles": {"include": ["Java Developer"]}}})
    assert rules.include == ("Java Developer",) and rules.exclude == () and rules.exceptions == ()
    assert rules.generic_engineer_titles is False


def test_a_comma_separated_string_is_accepted_and_duplicates_dropped():
    rules = TitleRules.from_config({"candidate": {"titles": {"include": "Backend, backend , API"}}})
    assert rules.include == ("Backend", "API")


@pytest.mark.parametrize("titles, message", [
    ({"include": []}, "no title would pass"),
    ({"include": ["backend"], "exlude": ["java"]}, "exlude"),
    ({"include": ["back<end>"]}, "back<end>"),
    ({"include": ["x" * 61]}, "longer than 60"),
    ({"include": [3]}, "text"),
    ("backend", "object"),
])
def test_an_unusable_titles_block_is_refused_with_a_message_that_says_what_to_fix(titles, message):
    with pytest.raises(TitleRulesError, match=re.escape(message)):
        TitleRules.from_config({"candidate": {"titles": titles}})


def test_an_include_entry_that_an_exclude_word_always_blocks_is_reported():
    rules = _rules(include=["java developer", "backend"], exclude=["java"])
    assert rules.warnings() == ["include entry 'java developer' can never pass: it contains the excluded 'java'"]
    assert TitleRules().warnings() == []          # the defaults are consistent


def test_configure_titles_switches_the_filter_the_scan_and_the_adapters_use():
    rules = prefilter.configure_titles({"candidate": {"titles": {"include": ["java developer"], "exclude": ["intern"]}}})
    assert prefilter.active_title_rules() is rules
    assert prefilter.title_is_candidate("Java Developer")            # what the Workday adapter calls during the fetch
    assert prefilter.should_evaluate_job(_job("Java Developer"))[0]
    assert not prefilter.should_evaluate_job(_job("Backend Engineer"))[0]


def test_title_exclusions_lists_every_excluded_word_for_the_measuring_script():
    assert prefilter.title_exclusions("Lead Java Developer, Android") == {"lead", "java", "android"}
    assert prefilter.title_exclusions("Member of Technical Staff") == set()
