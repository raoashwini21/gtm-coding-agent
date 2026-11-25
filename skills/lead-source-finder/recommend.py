#!/usr/bin/env python3
"""Lead Source Finder: turn six plain answers into 1 or 2 routes for finding the right leads.

Standard library only. It never touches the network, never scrapes, and never stores or
returns personal data. It decides WHERE to look; it does not fetch contacts or check emails.

Answers (JSON file or flags):
  audience    "business" | "people"        who you sell to (part of question 1)
  footprints  list of: linkedin, map, directory, topic, tool_or_hiring, website_words
  customers   "5plus" | "few" | "none"
  narrowness  "broad" | "niche" | "very_narrow"
  volume      "small_once" | "large_ongoing"
  region      "eu_uk" | "other"
  sensitive   true | false                 buyer is found through health, religion, politics etc.
"""
import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
FOOTPRINTS = {"linkedin", "map", "directory", "topic", "tool_or_hiring", "website_words"}
ENUMS = {
    "audience": {"business", "people"},
    "customers": {"5plus", "few", "none"},
    "narrowness": {"broad", "niche", "very_narrow"},
    "volume": {"small_once", "large_ongoing"},
    "region": {"eu_uk", "other"},
}

ROUTES = {
    1: {"name": "Business database filters",
        "fits": "Your buyer is on LinkedIn and is a fairly broad type of business or job title.",
        "cannot_find": "Small local businesses and anyone who is not on a business database.",
        "first_step": "Write three filters: job title, company size and industry. Run them and read 20 results before you buy anything.",
        "facts": ["apollo-1"]},
    2: {"name": "Lookalikes of your best customers",
        "fits": "You already have 5 or more happy customers and the buyer is a type of company.",
        "cannot_find": "Anything useful if you have no customers yet, and buyers that are unlike your current ones.",
        "first_step": "List your 5 to 10 best customer domains. Use them as the seed.",
        "facts": ["discolike-1", "ocean-1", "ocean-2"]},
    3: {"name": "Niche companies found by website wording",
        "fits": "Your buyer's website would use words that give them away.",
        "cannot_find": "Companies whose site does not say what they do in those words.",
        "first_step": "Write the exact phrase a buyer's homepage would use. Test it on 10 results.",
        "facts": ["discolike-2"]},
    4: {"name": "Maps, directories and job boards (scraping)",
        "fits": "Your buyer sits on a map, in a directory or on a job board.",
        "cannot_find": "Anyone who is not listed in public.",
        "first_step": "Pick the one place where your buyers are all listed. Run one small test search for one city.",
        "facts": ["apify-maps-1", "apify-maps-2", "apify-maps-3"]},
    5: {"name": "Hiring and tools-used signals",
        "fits": "A tool they use or a role they hire for shows they need what you sell.",
        "cannot_find": "Companies that never post jobs, and teams with no visible tools.",
        "first_step": "Name the one tool or the one job title that shows the need. Search only for that.",
        "facts": ["theirstack-1", "theirstack-2", "theirstack-3"]},
    6: {"name": "People who write or engage about a topic",
        "fits": "Your buyer is very narrow and talks about one thing in public.",
        "cannot_find": "Quiet buyers. It also catches fans, students and competitors.",
        "first_step": "Name the topic and the one place it gets discussed. Read 20 posts by hand before running any tool.",
        "facts": ["apify-li-1"]},
}

WARN_WEAK = ("Engagement is a weak buying signal. People who post or comment about a topic include "
             "competitor staff, students and fans. Treat the list as 'interested in the topic', not 'ready to buy'.")
WARN_LINKEDIN = ("LinkedIn says scraping and automation tools break its User Agreement (Section 8.2) and "
                 "can get accounts restricted. Source: see fact linkedin-1.")
WARN_GDPR = ("EU/UK note: 'public' does not mean free to use. You become the data controller for any "
             "personal data you collect, and you need a lawful basis. This is not legal advice. See facts gdpr-1 and gdpr-2.")
WARN_SENSITIVE = ("Sensitive topic: posts that show someone's health, religion, politics and similar can be "
                  "special-category data (GDPR Article 9, see fact gdpr-1). Safer first step: find the places "
                  "and the creators these people follow, not a list of individuals.")
WARN_PEOPLE = ("You sell to individuals, not companies. Stricter privacy and marketing-consent rules usually "
               "apply. Check them for the person's country before you contact anyone.")
NOTE_CONTACTS = ("Contact data is out of scope. Once you have the list, use the tool you already use "
                 "(Clay, Apollo and so on) for contact details.")


def validate(a):
    problems = []
    for key, allowed in ENUMS.items():
        if a.get(key) not in allowed:
            problems.append(f"{key} must be one of {sorted(allowed)}, got {a.get(key)!r}")
    fp = a.get("footprints")
    if not isinstance(fp, list) or not fp:
        problems.append("footprints must be a non-empty list")
    else:
        bad = [x for x in fp if x not in FOOTPRINTS]
        if bad:
            problems.append(f"unknown footprints {bad}; allowed {sorted(FOOTPRINTS)}")
    if not isinstance(a.get("sensitive", False), bool):
        problems.append("sensitive must be true or false")
    return problems


def score(a):
    fp = set(a["footprints"])
    n, c, v = a["narrowness"], a["customers"], a["volume"]
    s = {r: 0 for r in ROUTES}
    notes = {}
    # 1 database
    if "linkedin" in fp: s[1] += 3
    if n == "broad": s[1] += 2
    if v == "large_ongoing": s[1] += 1
    if a["audience"] == "people": s[1] -= 3
    # 2 lookalikes (hard requirement)
    if c == "5plus":
        s[2] += 3
        if n in ("niche", "broad"): s[2] += 1
        if fp & {"linkedin", "website_words"}: s[2] += 1
    else:
        notes[2] = "Skipped: lookalikes need 5 or more happy customers." if c == "few" else "Skipped: lookalikes need customers to copy."
    if a["audience"] == "people":
        s[2] = 0
        notes[2] = "Skipped: lookalikes work on companies, not individuals."
    # 3 website wording
    if "website_words" in fp: s[3] += 3
    if n in ("niche", "very_narrow") and "website_words" in fp: s[3] += 1
    # 4 maps and directories
    if fp & {"map", "directory"}: s[4] += 3
    if n == "niche" and fp & {"map", "directory"}: s[4] += 1
    # 5 hiring and tools
    if "tool_or_hiring" in fp: s[5] += 3
    if n == "niche" and "tool_or_hiring" in fp: s[5] += 1
    if a["audience"] == "people": s[5] = 0
    # 6 people who write
    if "topic" in fp: s[6] += 3
    if n == "very_narrow" and "topic" in fp: s[6] += 2
    return s, notes


def recommend(a):
    problems = validate(a)
    if problems:
        raise ValueError("; ".join(problems))
    s, notes = score(a)
    order = sorted(s, key=lambda r: (-s[r], r))
    top = order[0]
    chosen = [top]
    if s[top] < 3:
        status = "vague"
    else:
        status = "ok"
        second = order[1]
        if s[second] >= 3 and s[top] - s[second] <= 2:
            chosen.append(second)
    if status == "vague":
        chosen = [1] if a["audience"] == "business" else [6]
    warnings = []
    if 6 in chosen:
        warnings += [WARN_WEAK, WARN_LINKEDIN]
    if 4 in chosen and "linkedin" in a["footprints"]:
        warnings.append(WARN_LINKEDIN)
    if (set(chosen) & {4, 6}) and a["region"] == "eu_uk":
        warnings.append(WARN_GDPR)
    if 6 in chosen and a.get("sensitive"):
        warnings.append(WARN_SENSITIVE)
    if a["audience"] == "people":
        warnings.append(WARN_PEOPLE)
    seen, uniq = set(), []
    for w in warnings:
        if w not in seen:
            seen.add(w); uniq.append(w)
    return {"status": status, "routes": chosen, "scores": s, "skipped": notes,
            "warnings": uniq, "note": NOTE_CONTACTS}


def load_facts():
    return {f["id"]: f for f in json.loads((HERE / "facts.json").read_text())["facts"]}


def render(a, result):
    facts = load_facts()
    out = ["# Where to find your leads", ""]
    if result["status"] == "vague":
        out += ["Your answers did not point strongly at one place, so this is a safe starting point. "
                "Answer question 2 again with the places your buyer shows up in public.", ""]
    for i, r in enumerate(result["routes"], 1):
        info = ROUTES[r]
        out += [f"## {i}. {info['name']}", f"**Why it fits:** {info['fits']}",
                f"**What it can't find:** {info['cannot_find']}",
                f"**First step:** {info['first_step']}", "**Facts (source, last checked):**"]
        for fid in info["facts"]:
            f = facts[fid]
            src = f["source"] if isinstance(f["source"], str) else f["source"][0]
            out.append(f"- {f['claim']} ([source]({src}), {f['last_checked']})")
        out.append("")
    if result["warnings"]:
        out += ["## Before you start"] + [f"- {w}" for w in result["warnings"]]
        import re
        ids = []
        for w in result["warnings"]:
            for fid in re.findall(r"\b(?:linkedin|gdpr)-\d\b", w):
                if fid not in ids:
                    ids.append(fid)
        for fid in ids:
            f = facts[fid]
            srcs = [f["source"]] if isinstance(f["source"], str) else f["source"]
            links = ", ".join(f"[{i}]({s})" for i, s in enumerate(srcs, 1))
            out.append(f"  - `{fid}` ({f['last_checked']}): {f['claim']} {links}")
        out.append("")
    out += [result["note"]]
    return "\n".join(out)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--answers", help="path to a JSON file with the answers")
    p.add_argument("--format", choices=["md", "json"], default="md")
    args = p.parse_args(argv)
    if not args.answers:
        p.error("give --answers answers.json (see the docstring for the fields)")
    a = json.loads(Path(args.answers).read_text())
    try:
        res = recommend(a)
    except ValueError as e:
        print(f"Cannot recommend: {e}", file=sys.stderr)
        return 2
    print(json.dumps(res, indent=2) if args.format == "json" else render(a, res))
    return 0


if __name__ == "__main__":
    sys.exit(main())
