"""Dataset builder and size filter for company ingestion."""
from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import yaml

logger = logging.getLogger(__name__)

SUPPORTED_ATS = {
    "greenhouse",
    "lever",
    "ashby",
    "smartrecruiters",
    "recruitee",
    "workable",
    "personio",
    "workday",
}

BLOCKED_HEADCOUNT_TIERS = {
    "1-10 employees",
    "11-50 employees",
}

CORPORATE_SUFFIX_RE = re.compile(
    r"\b(technologies|technology|tech|pvt|ltd|private|limited|inc|corp|corporation|solutions|india|labs|software|systems|services)\b",
    re.IGNORECASE,
)


def normalize_text(text: str) -> str:
    """Normalize text by lowercasing and stripping punctuation/whitespace."""
    if not text:
        return ""
    text = text.lower().strip()
    text = re.sub(r"[\(\)\[\],.\'\"\-&/_+]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def is_blocked_headcount(headcount: Optional[str]) -> bool:
    """Check if the headcount belongs strictly to the safety blocklist tiers (1-10, 11-50)."""
    if not headcount:
        return False
    return headcount.strip() in BLOCKED_HEADCOUNT_TIERS


def load_linkedin_cache(cache_path: str) -> Tuple[Dict[str, str], Dict[str, str]]:
    """Load companyCache and slugCache from LinkedIn size filter backup JSON. An empty path means none is configured (T94)."""
    if not cache_path:
        return {}, {}
    p = Path(cache_path)
    if not p.exists():
        logger.warning("LinkedIn cache file not found: %s", cache_path)
        return {}, {}

    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        company_cache = data.get("companyCache", {})
        slug_cache = data.get("slugCache", {})
        return company_cache, slug_cache
    except Exception as e:
        logger.error("Failed to parse LinkedIn cache %s: %s", cache_path, e)
        return {}, {}


def match_headcount(
    name: str,
    slug: str,
    company_cache: Dict[str, str],
    slug_cache: Dict[str, str],
) -> str:
    """Match company against companyCache using name, normalized name, and slug."""
    if not company_cache:
        return "Unknown"

    name_lower = name.lower().strip()
    norm_name = normalize_text(name)
    slug_lower = slug.lower().strip()
    norm_slug = normalize_text(slug)

    candidates = [name_lower, norm_name, slug_lower, norm_slug]

    # Try removing corporate suffixes
    clean_name = CORPORATE_SUFFIX_RE.sub("", norm_name).strip()
    clean_name = re.sub(r"\s+", " ", clean_name)
    if clean_name and clean_name not in candidates:
        candidates.append(clean_name)

    # 1. Direct match in company_cache
    for cand in candidates:
        if cand in company_cache:
            return company_cache[cand]

    # 2. Check if slug_cache maps to a key in company_cache
    for cand in candidates:
        if cand in slug_cache:
            target = slug_cache[cand]
            if target in company_cache:
                return company_cache[target]

    return "Unknown"


def build_companies_dataset(
    yaml_path: str,
    linkedin_cache_path: str,
    output_path: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Extract companies across supported ATS engines, apply headcount filtering, and deduplicate."""
    p_yaml = Path(yaml_path)
    if not p_yaml.exists():
        raise FileNotFoundError(f"YAML source not found: {yaml_path}")

    with p_yaml.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    company_cache, slug_cache = load_linkedin_cache(linkedin_cache_path)

    seen_keys: Set[Tuple[str, str]] = set()
    seen_names: Set[str] = set()
    result: List[Dict[str, Any]] = []

    for ats, items in data.items():
        ats_clean = ats.lower().strip()
        if ats_clean not in SUPPORTED_ATS:
            continue
        if not isinstance(items, list):
            continue

        for item in items:
            if not isinstance(item, dict):
                continue
            name = item.get("name", "").strip()
            if not name:
                continue

            slug = item.get("slug", "").strip()

            # Deduplication: Avoid duplicate company entries
            dedup_name_key = name.lower()
            dedup_ats_slug = (ats_clean, slug.lower())
            if dedup_name_key in seen_names or (slug and dedup_ats_slug in seen_keys):
                continue

            headcount = match_headcount(name, slug, company_cache, slug_cache)

            # Apply Safety Blocklist: Discard ONLY 1-10 or 11-50 employees
            if is_blocked_headcount(headcount):
                logger.info("Discarding %s (%s): blocked headcount '%s'", name, ats_clean, headcount)
                continue

            seen_names.add(dedup_name_key)
            if slug:
                seen_keys.add(dedup_ats_slug)

            entry: Dict[str, Any] = {
                "name": name,
                "ats": ats_clean,
                "headcount": headcount,
            }

            if ats_clean == "workday":
                # For Workday, include tenant, dc, site if present, or fallback to slug
                for field in ("tenant", "dc", "site"):
                    if field in item:
                        entry[field] = item[field]
                if "slug" not in entry and slug:
                    entry["slug"] = slug
            else:
                entry["slug"] = slug

            result.append(entry)

    if output_path:
        save_companies_json(result, output_path)

    return result


def save_companies_json(companies: List[Dict[str, Any]], path: str) -> None:
    """Save companies list to JSON file with clean indentation."""
    out_file = Path(path)
    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_text(json.dumps(companies, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    logger.info("Wrote %d companies to %s", len(companies), path)
