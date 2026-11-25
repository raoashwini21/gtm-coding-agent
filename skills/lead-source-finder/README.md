# lead-source-finder

Not sure where to find the right leads? Answer six plain questions about your buyer and get one or two routes, with the exact first step for each.

It is a decision helper for the step before the list. It does not fetch contact details, check emails, or run any scraper.

Built as an add-on to [Shawn Tenam's gtm-coding-agent](https://github.com/shawnla90/gtm-coding-agent) (MIT). It follows the same skill format. Credit for the repo and the format is his.

## Why it exists

No single tool finds every kind of buyer. A database finds companies on LinkedIn. A map scraper finds a dentist. A lookalike tool needs customers to copy. A post scraper finds people who write about one topic. Picking the wrong one wastes a week. This asks about the buyer first.

## The six routes

1. Business database filters (Apollo-style)
2. Lookalikes of your best customers (needs 5 or more customers)
3. Niche companies found by website wording
4. Maps, directories and job boards, via scraping
5. Hiring and tools-used signals
6. People who write or engage about a topic

## How to use it

You need Python 3. Nothing else to install.

**The simple way: answer six questions in Terminal**

```
git clone https://github.com/raoashwini21/gtm-coding-agent
cd gtm-coding-agent
python3 skills/lead-source-finder/recommend.py
```

It asks the questions one at a time. You type a number and press Enter. It looks like this:

```
2. Where does your buyer leave footprints? Pick all that fit, like 1,3
  1) They have a LinkedIn profile or company page
  2) Their business is on a map (shops, clinics, gyms, restaurants)
  3) They are listed in a directory or on a job board
  ...
> 2
```

At the end you get one or two routes: why each fits, what it can't find, and the exact first step. Take that route to your usual tools and build the list.

**With an AI agent**

Open the folder in Claude Code (`cd gtm-coding-agent`, then `claude`) and say: **"Where should I find leads for my buyer?"** The agent asks the same questions in chat and runs the script for you. Other coding agents that read a repo's files should work too, but I have only checked Claude Code.

**For scripts**

`python3 skills/lead-source-finder/recommend.py --answers answers.json` skips the questions and reads a file instead. The fields are listed in [`SKILL.md`](SKILL.md).

Every tool fact in the report has a source link and a "last checked" date, plus the LinkedIn, GDPR and weak-signal warnings that apply. Tests: `python3 -m unittest tests/test_lead_source_finder.py`.

## What you get

For each route: why it fits, what it can't find, the first step, and tool facts with a source link and a "last checked" date. Then a short list of warnings (LinkedIn's rules, GDPR for EU/UK, weak buying signals from engagement).

## Honest limits

- Tool facts come from the vendors' own pages or from search excerpts of them. Open the source link before you decide. [`FACTCHECK.md`](FACTCHECK.md) lists what is solid and what is not.
- Not legal advice.
- It never runs a scraper for you.

## Files

- [`SKILL.md`](SKILL.md): instructions for coding agents
- [`recommend.py`](recommend.py): the rules
- [`facts.json`](facts.json): the sourced, dated facts
- [`FACTCHECK.md`](FACTCHECK.md): what was checked and what was not
- Tests: `python3 -m unittest tests/test_lead_source_finder.py`
