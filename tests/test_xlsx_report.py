"""T128: next to every CSV the scan writes a formatted Excel report (.xlsx) of the same rows.

Manish (2026-10-17): "csv or excel, any format works, you decide ... what can we do like formatting, text size, colouring?"
The CSV stays the primary output (scripts, tests and the MCP tool read it); the .xlsx is the one to read and filter: header row
frozen with a filter, Score first and coloured, wrapped Reason, clickable links, real UTF-8 (no import dialog, T126).
No network: adapters and scoring are stubbed; run_scan, the writers and the SQLite rows are real.
"""
import csv
import logging
import shutil
import subprocess
import sys
from pathlib import Path

import openpyxl
import pytest

from job_hunt import main as cli
from job_hunt import scanner, xlsx_report
from job_hunt.db import init_db, update_job_status
from job_hunt.exporter import EXPORT_FIELDS, export_jobs_to_csv
from job_hunt.models import JobPosting, job_key


def _jobs():
    return [
        {"company": "Acme", "ats": "workday", "title": "Backend Engineer", "location": "Bengaluru, Karnātaka, India", "url": "https://acme.example/1",
         "score": 90, "reason": "Node.js microservices match. " * 8, "worth_applying": True, "scan_date": "2026-10-17", "posted_at": "2026-10-16"},
        {"company": "Beta", "ats": "lever", "title": "Platform Engineer", "location": "Pune, India", "url": "https://beta.example/2",
         "score": 75, "reason": "Good stack fit.", "worth_applying": True, "scan_date": "2026-10-17", "posted_at": "Posted 3 Days Ago"},
        {"company": "Gamma", "ats": "ashby", "title": "Data Engineer", "location": "Remote, India", "url": "https://gamma.example/3",
         "score": 60, "reason": "Weaker fit.", "worth_applying": False, "scan_date": "2026-10-17", "posted_at": ""},
    ]


@pytest.fixture
def made(tmp_path):
    """(csv path, xlsx path, worksheet) for three jobs."""
    csv_path = export_jobs_to_csv(_jobs(), base_name="jobs_x", out_dir=tmp_path)
    xlsx = xlsx_report.write_xlsx_report(csv_path)
    return csv_path, xlsx, openpyxl.load_workbook(xlsx).active


def _col(ws, name):
    return [c.value for c in ws[1]].index(name) + 1


def test_the_report_sits_next_to_the_csv_under_the_same_name(made):
    csv_path, xlsx, _ = made
    assert xlsx == csv_path.with_suffix(".xlsx") and xlsx.exists()


def test_it_holds_the_csvs_rows_and_columns(made):
    csv_path, _, ws = made
    with csv_path.open(newline="", encoding="utf-8") as fh:
        rows = list(csv.reader(fh))
    assert [c.value for c in ws[1]] == rows[0] == EXPORT_FIELDS
    assert ws.max_row == len(rows) and ws.max_column == len(rows[0])
    asked = ["Company", "ATS", "Role", "Location", "Posted", "Reason", "Worth Applying", "Scan Date"]   # the text columns, cell for cell
    for i, row in enumerate(rows[1:], start=2):
        for name in asked:
            assert ws.cell(i, _col(ws, name)).value == (row[rows[0].index(name)] or None)


def test_the_score_is_a_number_so_the_spreadsheet_sorts_and_filters_it_as_one(made):
    _, _, ws = made
    col = _col(ws, "Score (%)")
    assert [ws.cell(i, col).value for i in (2, 3, 4)] == [90, 75, 60]
    assert col == 1


def test_the_header_row_is_bold_filled_frozen_and_filterable(made):
    _, _, ws = made
    head = ws[1][0]
    assert head.font.bold and head.fill.fgColor.rgb not in (None, "00000000")
    assert ws.freeze_panes == "C2"                                   # header row, plus Score and Company stay in view when scrolling right
    assert ws.auto_filter.ref == f"A1:{openpyxl.utils.get_column_letter(ws.max_column)}{ws.max_row}"


def test_the_links_are_clickable_with_a_short_label_and_keep_the_address(made):
    _, _, ws = made
    apply_cell = ws.cell(2, _col(ws, "Application URL"))
    assert apply_cell.hyperlink.target == "https://acme.example/1" and apply_cell.value == "Open"
    people = ws.cell(2, _col(ws, "LinkedIn people"))
    assert people.hyperlink.target.startswith("https://www.linkedin.com/search/results/people/") and people.value == "Search"


def test_a_missing_link_stays_an_empty_cell_not_a_dead_link(tmp_path):
    csv_path = export_jobs_to_csv([{"company": "", "title": "T", "score": 80, "url": ""}], base_name="x", out_dir=tmp_path)
    ws = openpyxl.load_workbook(xlsx_report.write_xlsx_report(csv_path)).active
    assert ws.cell(2, _col(ws, "Application URL")).value is None and ws.cell(2, _col(ws, "Application URL")).hyperlink is None
    assert ws.cell(2, _col(ws, "LinkedIn people")).value is None


def test_long_text_wraps_and_the_columns_have_their_own_widths(made):
    _, _, ws = made
    letter = openpyxl.utils.get_column_letter
    assert ws.cell(2, _col(ws, "Reason")).alignment.wrap_text
    assert ws.column_dimensions[letter(_col(ws, "Reason"))].width >= 60
    assert ws.column_dimensions[letter(_col(ws, "Score (%)"))].width <= 12
    assert ws.cell(2, 1).alignment.vertical == "top"


def test_a_row_with_long_text_is_tall_enough_for_all_of_it_and_a_short_row_stays_one_line(made):
    """Seen in a LibreOffice render of the first version: rows kept one line's height and the wrapped Reason was drawn over itself."""
    _, _, ws = made
    reason = len(ws.cell(2, _col(ws, "Reason")).value)
    width = ws.column_dimensions[openpyxl.utils.get_column_letter(_col(ws, "Reason"))].width
    assert ws.row_dimensions[2].height >= 15 * -(-reason // int(width))      # a line is 15 points
    assert (ws.row_dimensions[3].height or 15) == 15


def test_every_font_it_sets_names_the_typeface_so_no_program_falls_back_to_a_serif_one(made):
    """The same render showed the header, the links and the scores in a serif font: a font with no name is the viewer's choice."""
    _, _, ws = made
    cells = [ws.cell(1, 1), ws.cell(2, _col(ws, "Score (%)")), ws.cell(2, _col(ws, "Application URL")), ws.cell(2, _col(ws, "LinkedIn people"))]
    assert [(c.font.name, c.font.sz) for c in cells] == [("Calibri", 11)] * 4


def test_the_score_is_coloured_green_when_strong_amber_when_worth_applying_and_left_plain_below_that(made):
    _, _, ws = made
    ((rng, rules),) = [(str(cf.sqref), cf.rules) for cf in ws.conditional_formatting]
    assert rng == "A2:A4"
    worth = openpyxl.utils.get_column_letter(_col(ws, "Worth Applying"))
    # green is not given to a score the person's own min_score rules out (min_score 90: an 86 is "No"), hence the <> "No"
    assert [r.formula for r in rules] == [[f'AND($A2>=85,${worth}2<>"No")'], [f'AND($A2<85,${worth}2="Yes")']]
    assert all(r.dxf.fill is not None for r in rules)


def test_an_untrusted_job_title_that_looks_like_a_formula_stays_text(tmp_path):
    """Role and Company come from a company's job board. A cell beginning with = + - @ is a formula to a spreadsheet."""
    jobs = [{"company": "=1+1", "title": '=HYPERLINK("http://evil.example","click")', "score": 80, "location": "@SUM(A1)", "reason": "+cmd|' /C calc'!A0"}]
    csv_path = export_jobs_to_csv(jobs, base_name="x", out_dir=tmp_path)
    ws = openpyxl.load_workbook(xlsx_report.write_xlsx_report(csv_path)).active
    for name, text in (("Company", "=1+1"), ("Role", '=HYPERLINK("http://evil.example","click")'), ("Location", "@SUM(A1)"), ("Reason", "+cmd|' /C calc'!A0")):
        cell = ws.cell(2, _col(ws, name))
        assert cell.value == text and cell.data_type == "s", name


def test_non_ascii_text_is_stored_as_it_is(made):
    _, _, ws = made
    assert ws.cell(2, _col(ws, "Location")).value == "Bengaluru, Karnātaka, India"


def test_a_scan_with_nothing_new_still_gives_a_valid_empty_report(tmp_path):
    csv_path = export_jobs_to_csv([], base_name="empty", out_dir=tmp_path)
    ws = openpyxl.load_workbook(xlsx_report.write_xlsx_report(csv_path)).active
    assert [c.value for c in ws[1]] == EXPORT_FIELDS and ws.max_row == 1
    assert ws.conditional_formatting is not None and not list(ws.conditional_formatting)


def test_optional_columns_are_carried_over_after_the_fixed_ones(tmp_path):
    job = {**_jobs()[0], "application": "applied 2026-10-01", "model": "gemini-3.1-flash-lite"}
    csv_path = export_jobs_to_csv([job], base_name="x", out_dir=tmp_path)
    ws = openpyxl.load_workbook(xlsx_report.write_xlsx_report(csv_path)).active
    assert [c.value for c in ws[1]][len(EXPORT_FIELDS):] == ["Application", "Model"]
    assert ws.cell(2, _col(ws, "Application")).value == "applied 2026-10-01"


def test_a_report_that_cannot_be_written_leaves_the_csv_warns_and_removes_a_stale_report(tmp_path, monkeypatch, caplog):
    """The report is the secondary output: a failure must not lose the scan, and an old report beside a new CSV would show yesterday's jobs."""
    csv_path = export_jobs_to_csv(_jobs(), base_name="jobs_x", out_dir=tmp_path)
    stale = csv_path.with_suffix(".xlsx")
    stale.write_bytes(b"yesterday")
    monkeypatch.setattr(openpyxl.Workbook, "save", lambda self, *a, **k: (_ for _ in ()).throw(PermissionError("locked")))
    with caplog.at_level(logging.WARNING):
        assert xlsx_report.write_xlsx_report(csv_path) is None
    assert csv_path.exists() and not stale.exists()
    assert any("Excel report" in r.getMessage() and "locked" in r.getMessage() for r in caplog.records)


def test_any_error_while_building_the_report_is_only_a_warning(tmp_path, monkeypatch):
    """A missing library (ImportError) or a surprise in one cell (ValueError) is as little reason to stop a scan as a locked file."""
    csv_path = export_jobs_to_csv(_jobs(), base_name="jobs_x", out_dir=tmp_path)
    for error in (ImportError("no openpyxl"), ValueError("bad cell")):
        monkeypatch.setattr(xlsx_report, "_build", lambda header, rows, error=error: (_ for _ in ()).throw(error))
        assert xlsx_report.write_xlsx_report(csv_path) is None
    assert csv_path.exists()


def test_no_half_written_report_is_left_behind_when_saving_fails(tmp_path, monkeypatch):
    csv_path = export_jobs_to_csv(_jobs(), base_name="jobs_x", out_dir=tmp_path)

    def half_then_fail(self, path):
        Path(path).write_bytes(b"PK half")
        raise OSError("disk full")

    monkeypatch.setattr(openpyxl.Workbook, "save", half_then_fail)
    assert xlsx_report.write_xlsx_report(csv_path) is None
    assert sorted(p.name for p in tmp_path.iterdir()) == ["jobs_x.csv"]


def test_an_old_report_survives_until_the_new_one_is_complete(tmp_path, monkeypatch):
    """The report is written beside its final name and moved over it, so a reader never meets a half file."""
    csv_path = export_jobs_to_csv(_jobs(), base_name="jobs_x", out_dir=tmp_path)
    seen = []
    real_replace = xlsx_report.os.replace
    monkeypatch.setattr(xlsx_report.os, "replace", lambda a, b: (seen.append((Path(a).name, Path(b).name)), real_replace(a, b))[1])
    xlsx_report.write_xlsx_report(csv_path)
    assert seen == [("jobs_x.xlsx.tmp", "jobs_x.xlsx")]


def test_control_characters_a_job_board_may_send_do_not_stop_the_report(tmp_path):
    """XML cannot hold them; openpyxl raises on them, which would have cost every row of the report."""
    csv_path = export_jobs_to_csv([{"company": "A\x0bB", "title": "T\x00U", "score": 80, "reason": "x\x1fy"}], base_name="x", out_dir=tmp_path)
    ws = openpyxl.load_workbook(xlsx_report.write_xlsx_report(csv_path)).active
    assert (ws.cell(2, _col(ws, "Company")).value, ws.cell(2, _col(ws, "Role")).value, ws.cell(2, _col(ws, "Reason")).value) == ("AB", "TU", "xy")


def test_an_address_longer_than_excel_accepts_is_kept_as_plain_text_not_a_broken_link(tmp_path):
    url = "https://x.example/" + "a" * 2500
    csv_path = export_jobs_to_csv([{"company": "A", "title": "T", "score": 80, "url": url}], base_name="x", out_dir=tmp_path)
    ws = openpyxl.load_workbook(xlsx_report.write_xlsx_report(csv_path)).active
    cell = ws.cell(2, _col(ws, "Application URL"))
    assert cell.hyperlink is None and cell.value == url


# --- the real scan -----------------------------------------------------------------------

def _posting(n: int, ats: str = "greenhouse") -> JobPosting:
    return JobPosting(global_id=f"{ats}:x:{n}", ats=ats, company=f"Co {n}", title=f"Backend Engineer {n}", location="Bengaluru, India",
                      is_remote=False, url=f"https://{ats}.example/{n}", description_text="Node.js")


@pytest.fixture
def scan(tmp_path, monkeypatch):
    """One scan of two boards; scores 90 and 75. The fixture returns a function that scans again."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(scanner, "send_telegram", lambda *a, **k: False)
    (tmp_path / "resume.md").write_text("Node.js backend engineer")
    init_db("data/jobs.db")
    boards = {"G": [_posting(1), _posting(2)]}
    monkeypatch.setattr(scanner, "fetch_company_jobs", lambda c: list(boards[c["name"]]))

    def fake_score(job, **kw):
        score = 90 if job.title.endswith("1") else 75
        update_job_status(job_key(job), "scored", score, "fits")
        return {"score": score, "reason": "fits", "status": "scored"}

    monkeypatch.setattr(scanner, "score_and_process_job", fake_score)

    def run(new=()):
        boards["G"] = [_posting(1), _posting(2), *new]
        scanner.run_scan({"candidate": {"resume_path": "resume.md", "min_score": 70}, "gemini_api_key": "k", "telegram": {}},
                         [{"name": "G", "ats": "greenhouse", "slug": "g"}])
    run()
    return run


def _sheet(path):
    return openpyxl.load_workbook(path).active


def test_a_scan_writes_a_report_for_the_scans_file_and_for_open_matches(scan):
    (jobs_csv,) = Path("output/history").glob("jobs_*.csv")
    assert _sheet(jobs_csv.with_suffix(".xlsx")).max_row == 3
    ws = _sheet("output/open_matches.xlsx")
    assert ws.max_row == 3 and [ws.cell(i, 1).value for i in (2, 3)] == [90, 75]


def test_the_open_matches_report_is_replaced_by_the_next_scan_like_its_csv(scan):
    scan(new=[_posting(3)])                      # nothing new is scored above 70 but the new job (75): same boards otherwise
    with Path("output/open_matches.csv").open(newline="", encoding="utf-8") as fh:
        csv_urls = [r["Application URL"] for r in csv.DictReader(fh)]
    ws = _sheet("output/open_matches.xlsx")
    assert ws.max_row - 1 == len(csv_urls) == 1
    assert ws.cell(2, _col(ws, "Application URL")).hyperlink.target == csv_urls[0] == "https://greenhouse.example/3"


def test_a_second_scan_that_finds_nothing_empties_the_report_too(scan):
    scan()
    assert _sheet("output/open_matches.xlsx").max_row == 1


def test_autopilot_export_writes_one_too(scan, monkeypatch):
    before = set(Path("output/history").glob("*.xlsx"))
    monkeypatch.setattr(sys, "argv", ["autopilot", "export"])
    cli.main()
    (written,) = set(Path("output/history").glob("*.xlsx")) - before
    assert _sheet(written).max_row == 3


def test_a_scan_still_finishes_and_keeps_its_csvs_when_the_report_cannot_be_written(tmp_path, monkeypatch):
    monkeypatch.setattr(openpyxl.Workbook, "save", lambda self, *a, **k: (_ for _ in ()).throw(PermissionError("locked")))
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(scanner, "send_telegram", lambda *a, **k: False)
    (tmp_path / "resume.md").write_text("Node.js")
    init_db("data/jobs.db")
    monkeypatch.setattr(scanner, "fetch_company_jobs", lambda c: [_posting(1)])
    monkeypatch.setattr(scanner, "score_and_process_job",
                        lambda job, **kw: (update_job_status(job_key(job), "scored", 90, "fits"), {"score": 90, "reason": "fits", "status": "scored"})[1])
    scanner.run_scan({"candidate": {"resume_path": "resume.md", "min_score": 70}, "gemini_api_key": "k", "telegram": {}},
                     [{"name": "G", "ats": "greenhouse", "slug": "g"}])
    assert len(list(Path("output/history").glob("jobs_*.csv"))) == 1 and Path("output/open_matches.csv").exists()
    assert not list(Path("output").glob("*.xlsx"))


# --- a real spreadsheet program ----------------------------------------------------------

@pytest.mark.skipif(not shutil.which("soffice"), reason="LibreOffice is not installed")
def test_libreoffice_opens_it_keeps_the_letters_and_does_not_run_a_formula(tmp_path):
    """The real consumer: LibreOffice reads the .xlsx and saves it back as CSV. 'Karnātaka' must survive without an import dialog
    and a title that begins with = must still be text, not its result."""
    jobs = [{"company": "Acme", "title": "=1+1", "location": "Bengaluru, Karnātaka, India", "url": "https://a.example/1", "score": 88}]
    xlsx = xlsx_report.write_xlsx_report(export_jobs_to_csv(jobs, base_name="x", out_dir=tmp_path))
    out = tmp_path / "back"
    subprocess.run(["soffice", f"-env:UserInstallation=file://{tmp_path}/profile", "--headless", "--convert-to", "csv:Text - txt - csv (StarCalc):44,34,76,1",
                    "--outdir", str(out), str(xlsx)], check=True, capture_output=True, timeout=180)
    with (out / "x.csv").open(newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    assert rows[0]["Role"] == "=1+1" and rows[0]["Location"] == "Bengaluru, Karnātaka, India" and rows[0]["Score (%)"] == "88"
