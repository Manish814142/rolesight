from job_hunt.models import JobPosting, canonical_hash, url_hash


def test_job_posting_instantiation():
    job = JobPosting(
        global_id="greenhouse:stripe:12345",
        ats="greenhouse",
        company="Stripe",
        title="Software Engineer, Backend",
        location="Bengaluru, India",
        is_remote=False,
        url="https://boards.greenhouse.io/stripe/jobs/12345",
        description_text="Building backend APIs with Node.js and distributed systems.",
        posted_at="2026-04-01T10:00:00Z",
    )
    assert job.global_id == "greenhouse:stripe:12345"
    assert job.ats == "greenhouse"
    assert job.company == "Stripe"
    assert job.title == "Software Engineer, Backend"
    assert job.location == "Bengaluru, India"
    assert job.is_remote is False
    assert job.url == "https://boards.greenhouse.io/stripe/jobs/12345"
    assert "Node.js" in job.description_text
    assert job.posted_at == "2026-04-01T10:00:00Z"
    
    d = job.to_dict()
    assert d["global_id"] == "greenhouse:stripe:12345"
    assert d["company"] == "Stripe"

def test_canonical_hash():
    h1 = canonical_hash("Software Engineer", "Stripe", "Bengaluru")
    h2 = canonical_hash(" software engineer ", "STRIPE", " Bengaluru ")
    assert h1 == h2
    assert len(h1) == 32  # MD5 hex length

def test_url_hash():
    u1 = url_hash("https://boards.greenhouse.io/stripe/jobs/12345")
    u2 = url_hash(" https://boards.greenhouse.io/stripe/jobs/12345 ")
    assert u1 == u2
    assert len(u1) == 32
