#!/usr/bin/env python3
"""Lead Source Finder: turn six plain answers into 1 or 2 routes for finding the right leads.

Standard library only. It never touches the network, never scrapes, and never stores or
returns personal data. It decides WHERE to look; it does not fetch contacts or check emails.

Two ways to use it:
  python3 recommend.py            asks you the questions, one at a time (no files needed)
  python3 recommend.py --answers answers.json    for an AI agent or a script

Answers (the JSON file the agent writes):
  audience    "business" | "people"        who you sell to (part of question 1)
  footprints  list of: linkedin, map, directory, topic, tool_or_hiring, website_words
  platforms   list of: linkedin, x, reddit, youtube, other   (only if footprints has "topic";
              where the buyer posts or comments. Missing means "other".)
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
PLATFORMS = {"linkedin", "x", "reddit", "youtube", "other"}
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
        "facts": ["apollo-1", "apollo-2", "zoominfo-1", "cognism-1", "clay-2", "crunchbase-1", "credits-1"]},
    2: {"name": "Lookalikes of your best customers",
        "fits": "You already have 5 or more happy customers and the buyer is a type of company.",
        "cannot_find": "Anything useful if you have no customers yet, and buyers that are unlike your current ones.",
        "first_step": "List your 5 to 10 best customer domains. Use them as the seed.",
        "facts": ["discolike-1", "ocean-1", "ocean-2", "apollo-3", "clay-3", "landbase-1", "dealfront-1"]},
    3: {"name": "Niche companies found by website wording",
        "fits": "Your buyer's website would use words that give them away.",
        "cannot_find": "Companies whose site does not say what they do in those words.",
        "first_step": "Write the exact phrase a buyer's homepage would use. Test it on 10 results.",
        "facts": ["discolike-2", "clay-4", "exa-1", "parallel-1"]},
    4: {"name": "Maps, directories and job boards (scraping)",
        "fits": "Your buyer sits on a map, in a directory or on a job board.",
        "cannot_find": "Anyone who is not listed in public.",
        "first_step": "Pick the one place where your buyers are all listed. Run one small test search for one city.",
        "facts": ["apify-maps-1", "apify-maps-2", "apify-maps-3", "apify-maps-4", "outscraper-1", "gplaces-1"]},
    5: {"name": "Hiring and tools-used signals",
        "fits": "A tool they use or a role they hire for shows they need what you sell.",
        "cannot_find": "Companies that never post jobs, and teams with no visible tools.",
        "first_step": "Name the one tool or the one job title that shows the need. Search only for that.",
        "facts": ["theirstack-1", "theirstack-2", "theirstack-3", "builtwith-1", "wappalyzer-1", "bloomberry-1", "predictleads-1", "coresignal-1"]},
    6: {"name": "Posts and comments in your niche (LinkedIn, X, Reddit, YouTube or anywhere people post)",
        "fits": "Your buyer is very narrow and talks about one thing in public.",
        "cannot_find": "Quiet buyers. It also catches fans, students and competitors.",
        "how": "Step 1: find the posts about your topic. Step 2: pull the people who wrote or commented on them.",
        "first_step": "Name the topic and the place it gets discussed. Read 20 posts by hand. Pick the 5 to 10 best posts and note who wrote them and who commented. Only then choose a tool.",
        "facts": []},
}

# Plain-words questions to ask before choosing between the tools of a route (advice, not tool facts).
CHECKLIST = {
    1: ["Does it cover the countries you sell to? Ask for a sample from your region first.",
        "How are credits counted: one per contact, or emails and phones charged separately?",
        "Can you preview how many companies match before you spend credits?",
        "Do you need contact details at all? This skill does not cover them."],
    2: ["Do you have 5 or more happy customers to use as the seed?",
        "How many seed companies does the tool take, and does it want domains?",
        "Read the top 20 matches by hand. Do they look like your best customers?",
        "Can you export the size of list you need, and what does that cost?"],
    3: ["Write the exact phrase a buyer's homepage would use before you pick a tool.",
        "Does the tool read the real text on websites, or only labels like industry?",
        "Open 10 results and check the sites yourself.",
        "Is it a paid plan or a credit product? Check before you start."],
    4: ["Is your buyer really listed there? Check 10 by hand.",
        "Is it an official API or a scraper? Scrapers can break and have their own rules.",
        "What does 1,000 places cost once phone and website details are included?",
        "Does the maintainer's page show recent updates and reviews?"],
    5: ["Can the tool see the tool or role you care about? Website-only tools miss tools that never show on a site.",
        "Does the data come from job postings, website code, or both?",
        "How fresh is it, and can you filter by title, tool and country?",
        "Test with one tool or one job title before you buy."],
    6: ["Read 20 posts by hand first.",
        "Does the tool need no login, or does it use your own account? Your own account carries the risk.",
        "Check the maintainer, last update and reviews of any actor.",
        "Keep only the people whose headline fits your buyer."],
}
NOTE_MORE = ("These are the tools checked on the dates shown, not every tool that exists. If you use an AI agent, "
             "ask it to search the web for current alternatives and to link a source for each one.")

# Route 6 tools depend on where the buyer posts. Every id here must exist in facts.json.
PLATFORM_FACTS = {
    "linkedin": ["apify-li-1", "apify-li-2", "phantom-1", "clay-1", "salesnav-1"],
    "x": ["x-1"],
    "reddit": [],
    "youtube": ["youtube-1"],
    "other": [],
}
ALERT_FACTS = ["listen-1", "listen-2"]


def route_facts(r, a):
    if r != 6:
        return list(ROUTES[r]["facts"])
    ids = []
    for p in (a.get("platforms") or ["other"]):
        for fid in PLATFORM_FACTS.get(p, []):
            if fid not in ids:
                ids.append(fid)
    return ids + ALERT_FACTS

WARN_WEAK = ("Engagement is a weak buying signal. People who post or comment about a topic include "
             "competitor staff, students and fans. Treat the list as 'interested in the topic', not 'ready to buy'.")
WARN_LINKEDIN = ("LinkedIn says scraping and automation tools break its User Agreement (Section 8.2) and "
                 "can get accounts restricted. Source: see fact linkedin-1.")
WARN_X = ("X says crawling or scraping it without its written consent is prohibited, and its developer docs "
          "list scraping and browser automation as banned non-API access. See fact x-2.")
WARN_REDDIT = ("Reddit: commercial use of its data needs a separate agreement with Reddit, and one guide says its "
               "terms do not allow collecting outside its API. See facts reddit-1 and reddit-2.")
WARN_PLATFORM = ("Every platform has its own rules on collecting people's data. This skill has no checked rules "
                 "for YouTube or the other places you picked, so read their terms before you collect anything.")
WARN_GDPR = ("EU/UK note: 'public' does not mean free to use. You become the data controller for any "
             "personal data you collect, and you need a lawful basis. This is not legal advice. See facts gdpr-1 and gdpr-2.")
WARN_SENSITIVE = ("Sensitive topic: posts that show someone's health, religion, politics and similar can be "
                  "special-category data (GDPR Article 9, see fact gdpr-1). Safer first step: find the places "
                  "and the creators these people follow, not a list of individuals.")
SENSITIVE_FIRST_STEP = ("Find the places and the creators these people follow (communities, newsletters, podcasts, "
                        "hashtags) and reach them there. Do not build a list of individuals from their posts.")
WARN_PEOPLE = ("You sell to individuals, not companies. Stricter privacy and marketing-consent rules usually "
               "apply. Check them for the person's country before you contact anyone.")
NOTE_CONTACTS = ("Contact data is out of scope. Once you have the list, use the tool you already use "
                 "(Clay, Apollo and so on) for contact details.")


def validate(a):
    if not isinstance(a, dict):
        return ["the answers must be a JSON object like {\"audience\": \"business\", ...}"]
    problems = []
    for key, allowed in ENUMS.items():
        v = a.get(key)
        if not isinstance(v, str) or v not in allowed:
            problems.append(f"{key} must be one of {sorted(allowed)}, got {v!r}")
    pl = a.get("platforms", None)
    if pl is not None:
        if not isinstance(pl, list) or not pl:
            problems.append("platforms must be a non-empty list")
        else:
            badp = [x for x in pl if not isinstance(x, str) or x not in PLATFORMS]
            if badp:
                problems.append(f"unknown platforms {badp}; allowed {sorted(PLATFORMS)}")
    fp = a.get("footprints")
    if not isinstance(fp, list) or not fp:
        problems.append("footprints must be a non-empty list")
    else:
        bad = [x for x in fp if not isinstance(x, str) or x not in FOOTPRINTS]
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
    plats = set(a.get("platforms") or ["other"])
    if 6 in chosen:
        warnings.append(WARN_WEAK)
        if "linkedin" in plats: warnings.append(WARN_LINKEDIN)
        if "x" in plats: warnings.append(WARN_X)
        if "reddit" in plats: warnings.append(WARN_REDDIT)
        if plats & {"youtube", "other"}: warnings.append(WARN_PLATFORM)
    if 4 in chosen and {"linkedin", "directory"} <= set(a["footprints"]):  # job boards can include LinkedIn
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
    overrides = {}
    if 6 in chosen and a.get("sensitive"):
        overrides[6] = {"first_step": SENSITIVE_FIRST_STEP, "hide_facts": True}
    return {"status": status, "routes": chosen, "scores": s, "skipped": notes,
            "overrides": overrides, "warnings": uniq, "note": NOTE_CONTACTS}


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
        ov = result.get("overrides", {}).get(r, {})
        out += [f"## {i}. {info['name']}", f"**Why it fits:** {info['fits']}",
                f"**What it can't find:** {info['cannot_find']}"]
        if info.get("how"):
            out.append(f"**How it works:** {info['how']}")
        out.append(f"**First step:** {ov.get('first_step', info['first_step'])}")
        if ov.get("hide_facts"):
            out += ["**Tools:** left out on purpose. This route should not start with scraping people's posts.", ""]
            continue
        out.append("**Tools checked (source, date, kind):**")
        for fid in route_facts(r, a):
            f = facts[fid]
            src = f["source"] if isinstance(f["source"], str) else f["source"][0]
            out.append(f"- **{f['tool']}:** {f['claim']} ([source]({src}), {f['last_checked']}, {f['kind']})")
        out += ["", "**How to choose between them:**"] + [f"- {q}" for q in CHECKLIST[r]] + [""]
    if result["warnings"]:
        out += ["## Before you start"] + [f"- {w}" for w in result["warnings"]]
        import re
        ids = []
        for w in result["warnings"]:
            for fid in re.findall(r"\b(?:linkedin|gdpr|x|reddit)-\d\b", w):
                if fid not in ids:
                    ids.append(fid)
        for fid in ids:
            f = facts[fid]
            srcs = [f["source"]] if isinstance(f["source"], str) else f["source"]
            links = ", ".join(f"[{i}]({s})" for i, s in enumerate(srcs, 1))
            out.append(f"  - `{fid}` ({f['last_checked']}): {f['claim']} {links}")
        out.append("")
    out += [NOTE_MORE, "", result["note"]]
    return "\n".join(out)


QUESTIONS = [
    {"key": "audience", "multi": False,
     "text": "1. Who do you sell to?",
     "options": [("Businesses", "business"), ("Individual people", "people")]},
    {"key": "footprints", "multi": True,
     "text": "2. Where does your buyer leave footprints? Pick all that fit, like 1,3",
     "options": [("They have a LinkedIn profile or company page", "linkedin"),
                 ("Their business is on a map (shops, clinics, gyms, restaurants)", "map"),
                 ("They are listed in a directory or on a job board", "directory"),
                 ("They post or comment about a topic (LinkedIn, X, Reddit, YouTube, forums)", "topic"),
                 ("They use a specific tool, or hire for a specific role", "tool_or_hiring"),
                 ("Their website uses certain words", "website_words")]},
    {"key": "customers", "multi": False,
     "text": "3. Do you already have happy customers?",
     "options": [("5 or more", "5plus"), ("A few (1 to 4)", "few"), ("None yet", "none")]},
    {"key": "narrowness", "multi": False,
     "text": "4. How narrow is your buyer?",
     "options": [("Broad (for example, any SaaS company)", "broad"),
                 ("A niche (one kind of business)", "niche"),
                 ("Very narrow (one kind of person saying one kind of thing)", "very_narrow")]},
    {"key": "volume", "multi": False,
     "text": "5. How many leads do you need?",
     "options": [("A few hundred, once", "small_once"), ("Thousands, every month", "large_ongoing")]},
    {"key": "region", "multi": False,
     "text": "6. Where are they? If any are in the EU or UK, pick 1.",
     "options": [("EU or UK", "eu_uk"), ("Somewhere else", "other")]},
]
PLATFORMS_Q = {"key": "platforms", "multi": True,
               "text": "Where do they post or comment? Pick all that fit, like 1,3",
               "options": [("LinkedIn", "linkedin"), ("X (Twitter)", "x"), ("Reddit", "reddit"),
                           ("YouTube", "youtube"), ("Somewhere else, or not sure", "other")]}
SENSITIVE_Q = {"key": "sensitive", "multi": False,
               "text": "Last one. Do you find these people through something sensitive, like health, religion or politics?",
               "options": [("Yes", True), ("No", False)]}


def _ask_one(q, read, say):
    say("")
    say(q["text"])
    for i, (label, _) in enumerate(q["options"], 1):
        say(f"  {i}) {label}")
    n = len(q["options"])
    while True:
        raw = read("> ").strip()
        try:
            picks = [int(x) for x in raw.replace(" ", "").split(",") if x != ""] if q["multi"] else [int(raw)]
        except ValueError:
            picks = []
        if picks and all(1 <= k <= n for k in picks) and (q["multi"] or len(picks) == 1):
            vals = []
            for k in picks:
                if q["options"][k - 1][1] not in vals:
                    vals.append(q["options"][k - 1][1])
            return vals if q["multi"] else vals[0]
        say(f"Please type a number from 1 to {n}" + (", or several like 1,3." if q["multi"] else "."))


def ask_answers(read=input, say=print):
    """Ask the questions one at a time and return the answers dict. No files, no network."""
    say("Where should you find your leads? Six quick questions. Type a number and press Enter.")
    a = {}
    for q in QUESTIONS:
        a[q["key"]] = _ask_one(q, read, say)
    if "topic" in a["footprints"]:
        a["platforms"] = _ask_one(PLATFORMS_Q, read, say)
    a["sensitive"] = _ask_one(SENSITIVE_Q, read, say) if "topic" in a["footprints"] else False
    say("")
    return a


def _read_stderr(prompt=""):
    sys.stderr.write(prompt)
    sys.stderr.flush()
    line = sys.stdin.readline()
    if line == "":
        raise EOFError
    return line.rstrip("\n")


def main(argv=None, read=input):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--answers", help="path to a JSON file with the answers (skips the questions)")
    p.add_argument("--ask", action="store_true", help="ask the questions here (this is the default)")
    p.add_argument("--format", choices=["md", "json"], default="md")
    args = p.parse_args(argv)
    if args.answers and args.ask:
        p.error("use either --answers or --ask, not both")
    if args.answers:
        try:
            a = json.loads(Path(args.answers).read_text())
        except (OSError, ValueError) as e:
            print(f"Cannot read {args.answers}: {e}", file=sys.stderr)
            return 2
    else:
        try:
            if args.format == "json":
                say = lambda t="": print(t, file=sys.stderr)  # keep stdout clean for the JSON
                read = _read_stderr if read is input else read
            else:
                say = print
            a = ask_answers(read, say)
        except (EOFError, KeyboardInterrupt):
            print("\nStopped. Nothing was saved.", file=sys.stderr)
            return 130
    try:
        res = recommend(a)
    except ValueError as e:
        print(f"Cannot recommend: {e}", file=sys.stderr)
        return 2
    try:
        print(json.dumps(res, indent=2) if args.format == "json" else render(a, res))
    except BrokenPipeError:
        raise
    except (OSError, ValueError, KeyError) as e:
        print(f"Cannot build the report (is facts.json missing or damaged?): {e}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    try:
        code = main()
        sys.stdout.flush()  # a closed pipe shows up here, not at exit
    except BrokenPipeError:  # for example: recommend.py | head
        import os
        try:
            os.dup2(os.open(os.devnull, os.O_WRONLY), sys.stdout.fileno())
        except Exception:
            pass
        code = 0
    sys.exit(code)
