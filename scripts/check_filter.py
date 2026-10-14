#!/usr/bin/env python3
"""Try the pre-filter on one job (T80); the same as `rolesight check-filter` (T103), which reads config.json's title filter and cities.

    python scripts/check_filter.py "Senior Backend Engineer" "Bengaluru, India"
    python scripts/check_filter.py "Backend Engineer" "" --remote
    python scripts/check_filter.py "Backend Engineer" "Hyderabad, India" --cities "Pune, Mumbai"   # instead of candidate.cities

Prints KEPT (the job would go to Gemini) or REJECTED with the filter's own reason. Local only: no network, no API key.
"""
import sys

from job_hunt.onboarding import check_filter_command

if __name__ == "__main__":
    check_filter_command(sys.argv[1:])
