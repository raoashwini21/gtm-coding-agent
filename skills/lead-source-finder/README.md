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

## Use it

You need Python 3. Nothing to install.

```
git clone https://github.com/raoashwini21/gtm-coding-agent
cd gtm-coding-agent
python3 skills/lead-source-finder/recommend.py --answers answers.json
```

Or open the repo in Claude Code and say "where should I find leads for my buyer?". The agent asks the questions for you.

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
