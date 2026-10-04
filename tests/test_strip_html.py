"""strip_html must yield plain text, including for entity-escaped HTML (T46)."""
from unittest.mock import MagicMock, patch

from job_hunt.adapters.base import strip_html
from job_hunt.adapters.greenhouse import fetch_greenhouse

# Greenhouse's board API sends `content` entity-escaped, exactly like this (2026-10-04).
ESCAPED_GREENHOUSE = (
    "&lt;div class=&quot;content&quot;&gt;&lt;p&gt;&lt;strong&gt;What You&#39;ll Do"
    "&lt;/strong&gt;&lt;/p&gt;&lt;ul&gt;&lt;li&gt;Build Node.js services&lt;/li&gt;"
    "&lt;li&gt;Run Kafka &amp;amp; Postgres&lt;/li&gt;&lt;/ul&gt;&lt;/div&gt;"
)


def test_escaped_html_becomes_plain_text():
    text = strip_html(ESCAPED_GREENHOUSE)
    assert "&lt;" not in text and "<" not in text and "&quot;" not in text
    assert "What You'll Do" in text
    assert "Run Kafka & Postgres" in text


def test_plain_html_is_stripped_and_entities_decoded():
    assert strip_html("<p>Hello &amp; <strong>Node</strong></p>") == "Hello & Node"


def test_block_elements_do_not_glue_words():
    text = strip_html("<ul><li>Node</li><li>Kafka</li></ul>")
    assert "NodeKafka" not in text
    assert "Node" in text and "Kafka" in text


def test_literal_angle_brackets_in_text_survive():
    # "&lt;" in an ordinary (non-escaped) document is text, e.g. a latency target.
    assert "< 50 ms" in strip_html("<p>p99 latency &lt; 50 ms</p>")


def test_empty_input():
    assert strip_html("") == ""


@patch("requests.get")
def test_fetch_greenhouse_descriptions_are_plain_text(mock_get):
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"jobs": [{
        "id": 1, "title": "Backend Engineer", "location": {"name": "Bengaluru, India"},
        "absolute_url": "https://boards.greenhouse.io/x/jobs/1", "content": ESCAPED_GREENHOUSE,
    }]}
    mock_resp.raise_for_status.return_value = None
    mock_get.return_value = mock_resp

    desc = fetch_greenhouse("x")[0].description_text
    assert "&lt;" not in desc and "<div" not in desc
    assert "Build Node.js services" in desc
