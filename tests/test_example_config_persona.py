"""T85: the example config (what `autopilot init` writes) must describe the person this fork is built for.

It carried upstream's persona ("10+ YOE Senior/Staff ML/AI Engineer", "relocation to EU / NA / APAC", "pure SWE with no ML"),
which contradicts a pre-filter that rejects Staff titles and non-India places and a rubric written for a 3-year backend
engineer: a user who forgot to edit the three sentences got scores that disagreed with the filter. The guide's own
examples are the single source.
"""
import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
FILES = ["config.example.json", "job_hunt/data/config.example.json"]


def _guide_example(key):
    text = (ROOT / "docs" / "00-user-guide.md").read_text(encoding="utf-8")
    m = re.search(rf"^- `candidate\.{key}`: `\"(.+)\"`$", text, re.MULTILINE)
    assert m, f"the guide has no example line for candidate.{key}"
    return m.group(1)


@pytest.mark.parametrize("path", FILES)
@pytest.mark.parametrize("key", ["profile", "seeking", "not_suitable"])
def test_the_example_sentences_are_the_guides_examples(path, key):
    cand = json.loads((ROOT / path).read_text(encoding="utf-8"))["candidate"]
    assert cand[key] == _guide_example(key)


@pytest.mark.parametrize("path", FILES)
def test_nothing_in_the_example_config_describes_upstreams_persona(path):
    text = (ROOT / path).read_text(encoding="utf-8")
    for phrase in ("10+ YOE", "Staff ML", "MLOps", "relocation to EU", "no ML"):
        assert phrase not in text, (path, phrase)
