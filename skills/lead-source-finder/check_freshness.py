#!/usr/bin/env python3
"""List facts in facts.json whose 'last_checked' date is older than a limit.

Exit code 0 = all fresh, 1 = some are stale, 2 = bad input. Offline, standard library only.
Used by the monthly GitHub Action, and fine to run by hand:
  python3 skills/lead-source-finder/check_freshness.py --max-age-days 60
"""
import argparse
import datetime as dt
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def stale_facts(facts, today, max_age_days):
    out = []
    for f in facts:
        try:
            d = dt.date.fromisoformat(f["last_checked"])
        except (KeyError, ValueError):
            out.append((f.get("id", "?"), None, "missing or bad last_checked date"))
            continue
        age = (today - d).days
        if age > max_age_days:
            out.append((f["id"], age, f"{age} days old"))
    return out


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--max-age-days", type=int, default=60)
    p.add_argument("--today", help="YYYY-MM-DD, for tests")
    p.add_argument("--md", help="write a markdown report to this path when facts are stale")
    p.add_argument("--file", default=str(HERE / "facts.json"))
    a = p.parse_args(argv)
    try:
        facts = json.loads(Path(a.file).read_text())["facts"]
        today = dt.date.fromisoformat(a.today) if a.today else dt.date.today()
    except (OSError, ValueError, KeyError) as e:
        print(f"Cannot check: {e}", file=sys.stderr)
        return 2
    stale = stale_facts(facts, today, a.max_age_days)
    if not stale:
        print(f"All {len(facts)} facts were checked within {a.max_age_days} days.")
        return 0
    lines = [f"{len(stale)} of {len(facts)} facts in `skills/lead-source-finder/facts.json` are older than {a.max_age_days} days:", ""]
    lines += [f"- `{i}`: {why}" for i, _, why in stale]
    lines += ["", "To refresh: open each source link, fix the claim if the page changed, set `last_checked`, then run",
              "`python3 -m unittest tests/test_lead_source_finder.py`. Close this issue when done."]
    text = "\n".join(lines)
    print(text)
    if a.md:
        Path(a.md).write_text(text + "\n")
    return 1


if __name__ == "__main__":
    sys.exit(main())
