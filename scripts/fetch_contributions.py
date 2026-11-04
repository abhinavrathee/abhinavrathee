#!/usr/bin/env python3
"""
Scrape real daily contribution counts from GitHub's public, unauthenticated
contributions endpoint (the same fragment the profile page itself uses) and
write data/contributions.json with the raw days plus derived stats
(current streak, longest streak, best day, monthly totals).

No token, no auth, no GraphQL -- just the public HTML GitHub already serves.
Run periodically by .github/workflows/update-profile-art.yml.
"""
import json
import os
import re
import sys
from datetime import date as date_cls, datetime, timedelta
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup

USERNAME = os.environ.get("GH_PROFILE_USER", "abhinavrathee")
URL = f"https://github.com/users/{USERNAME}/contributions"
PROFILE_TIMEZONE = ZoneInfo(os.environ.get("GH_PROFILE_TIMEZONE", "Asia/Kolkata"))
OUT_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "contributions.json")


def fetch_days():
    # The default contributions page is cached as a rolling window and can lag
    # a user's local day. Request each calendar year explicitly, then construct
    # the same Sunday-aligned rolling window GitHub shows on the profile.
    today = datetime.now(PROFILE_TIMEZONE).date()
    first_day = today - timedelta(days=365)
    first_day -= timedelta(days=(first_day.weekday() + 1) % 7)
    all_days = {}

    for year in range(first_day.year, today.year + 1):
        resp = requests.get(
            URL,
            params={"from": f"{year}-01-01", "to": f"{year}-12-31"},
            headers={"User-Agent": "profile-readme-bot/1.0", "Cache-Control": "no-cache"},
            timeout=30,
        )
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        summary = soup.select_one(".js-yearly-contributions")
        summary_text = summary.get_text(" ", strip=True) if summary else ""
        summary_match = re.search(r"\b(\d+)\s+contributions?\b", summary_text, re.I)
        if not summary_match:
            print(f"could not read GitHub's contribution total for {year}", file=sys.stderr)
            sys.exit(1)
        reported_total = int(summary_match.group(1))

        cells = soup.select("td.ContributionCalendar-day")
        expected_days = 366 if date_cls(year, 12, 31).timetuple().tm_yday == 366 else 365
        if len(cells) != expected_days:
            print(
                f"GitHub returned {len(cells)} calendar days for {year}; "
                f"expected {expected_days}, refusing to update",
                file=sys.stderr,
            )
            sys.exit(1)

        year_days = []
        for td in cells:
            date = td.get("data-date")
            if not date:
                print(f"calendar cell for {year} is missing its date", file=sys.stderr)
                sys.exit(1)
            td_id = td.get("id")
            tooltip_el = soup.find("tool-tip", attrs={"for": td_id}) if td_id else None
            text = tooltip_el.get_text(strip=True) if tooltip_el else ""
            if re.search(r"no contributions", text, re.I):
                count = 0
            else:
                match = re.match(r"(\d+)", text)
                if not match:
                    print(f"could not read contribution count for {date}: {text!r}", file=sys.stderr)
                    sys.exit(1)
                count = int(match.group(1))
            year_days.append({"date": date, "count": count, "level": int(td.get("data-level") or 0)})

        parsed_total = sum(day["count"] for day in year_days)
        if parsed_total != reported_total:
            print(
                f"GitHub calendar mismatch for {year}: summary says {reported_total}, "
                f"daily cells sum to {parsed_total}; refusing to update",
                file=sys.stderr,
            )
            sys.exit(1)
        all_days.update({day["date"]: day for day in year_days})

    days = [
        all_days[day.isoformat()]
        for day in (first_day + timedelta(days=offset) for offset in range((today - first_day).days + 1))
        if day.isoformat() in all_days
    ]
    parsed_dates = [date_cls.fromisoformat(day["date"]) for day in days]
    if any(current - previous != timedelta(days=1) for previous, current in zip(parsed_dates, parsed_dates[1:])):
        print("calendar dates are not a complete consecutive daily range", file=sys.stderr)
        sys.exit(1)

    if len(days) != (today - first_day).days + 1:
        print("calendar is missing dates in the rolling profile window", file=sys.stderr)
        sys.exit(1)

    return days


def compute_current_streak(days):
    idx = len(days) - 1
    if days[idx]["count"] == 0:
        idx -= 1  # today isn't over yet -- don't break the streak on it
    streak = 0
    end_idx = idx
    while idx >= 0 and days[idx]["count"] > 0:
        streak += 1
        idx -= 1
    start_idx = idx + 1
    if streak == 0:
        return 0, None, None
    return streak, days[start_idx]["date"], days[end_idx]["date"]


def compute_longest_streak(days):
    longest = run = 0
    longest_start = longest_end = None
    run_start_idx = None
    for i, d in enumerate(days):
        if d["count"] > 0:
            if run == 0:
                run_start_idx = i
            run += 1
            if run > longest:
                longest = run
                longest_start = days[run_start_idx]["date"]
                longest_end = days[i]["date"]
        else:
            run = 0
    return longest, longest_start, longest_end


def build_data(days):
    total = sum(d["count"] for d in days)
    active_days = sum(1 for d in days if d["count"] > 0)
    best = max(days, key=lambda d: d["count"])
    cur_len, cur_start, cur_end = compute_current_streak(days)
    long_len, long_start, long_end = compute_longest_streak(days)

    monthly = {}
    for d in days:
        key = d["date"][:7]
        monthly[key] = monthly.get(key, 0) + d["count"]
    monthly_list = [{"month": k, "total": v} for k, v in sorted(monthly.items())]

    return {
        "username": USERNAME,
        "range": {"start": days[0]["date"], "end": days[-1]["date"]},
        "total_contributions": total,
        "active_days": active_days,
        "avg_per_active_day": round(total / active_days, 1) if active_days else 0,
        "current_streak": {"length": cur_len, "start": cur_start, "end": cur_end},
        "longest_streak": {"length": long_len, "start": long_start, "end": long_end},
        "best_day": {"date": best["date"], "count": best["count"]},
        "monthly": monthly_list,
        "days": days,
    }


if __name__ == "__main__":
    days = fetch_days()
    data = build_data(days)
    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w") as f:
        json.dump(data, f, indent=2)
    print(f"wrote {OUT_PATH}: {data['total_contributions']} contributions, "
          f"current streak {data['current_streak']['length']}, "
          f"longest streak {data['longest_streak']['length']}")
