---
name: lead-source-finder
version: 1.0.0
description: Help someone decide WHERE to find the right leads (the list of companies or people) before they build a list. Asks six plain questions about the buyer and recommends one or two routes out of six (business database filters, lookalikes of best customers, niche companies by website wording, maps/directories/job boards via scraping, hiring and tools-used signals, people who write or engage about a topic). Each answer says why it fits, what it can't find and the exact first step, with sourced and dated tool facts and the LinkedIn and GDPR warnings that apply. Does not fetch contact data, check emails or run any scraper. Use when the user says "where do I find leads", "which tool for my list", "Apollo or Clay or Apify", "lookalike", "how do I source leads", "where do I find my ICP", "list building source", or "scrape or database".
---

# lead-source-finder

A decision helper for the step before the list: where do the right leads live?

Different buyers leave footprints in different places. A company on LinkedIn is easy to find with database filters. A dentist is on a map, not in a database. A person who writes about one topic is found by their posts. No single tool covers all of these, so this skill asks about the buyer first and only then names a route.

It decides where to look. It never fetches contact details, never checks emails, never runs a scraper, and never stores personal data. After the list exists, the person uses whatever contact tool they already have (Clay, Apollo and so on).

Origin: built as an add-on to Shawn Tenam's [gtm-coding-agent](https://github.com/shawnla90/gtm-coding-agent) (MIT) and follows the same skill format. Credit for the repo and the format is his.

## How to run it

Ask the six questions one at a time, in plain words. Do not show the scoring. Then run:

```bash
python3 skills/lead-source-finder/recommend.py --answers answers.json
python3 skills/lead-source-finder/recommend.py --answers answers.json --format json
```

Standard library only, Python 3.8 or newer, no network, no keys. Offline tests: `python3 -m unittest tests/test_lead_source_finder.py`.

`answers.json`:

```json
{"audience": "business", "footprints": ["linkedin", "map"], "customers": "none",
 "narrowness": "niche", "volume": "small_once", "region": "other", "sensitive": false}
```

## The six questions

1. **Who do you sell to?** One sentence. Also note: businesses, or individuals? (`audience`: `business` or `people`)
2. **Where does this buyer leave footprints?** Pick all that fit. (`footprints`)
   - `linkedin`: a LinkedIn profile or company page
   - `map`: a map listing (shops, clinics, gyms, restaurants)
   - `directory`: a directory or job board
   - `topic`: they write or comment about a topic
   - `tool_or_hiring`: they use a specific tool or hire for a specific role
   - `website_words`: their website uses certain words
3. **Do you have happy customers?** `5plus`, `few`, or `none`. (`customers`)
4. **How narrow is the buyer?** `broad` (any SaaS company), `niche` (one niche), or `very_narrow` (one kind of person saying one kind of thing). (`narrowness`)
5. **How many leads, and how often?** `small_once` (a few hundred, once) or `large_ongoing` (thousands, every month). (`volume`)
6. **Where are they?** `eu_uk` or `other`. This decides which privacy warning applies. (`region`)

Ask one extra thing only if the topic route comes up: is the buyer found through health, religion, politics or similar? (`sensitive`, true or false)

## The six routes

| # | Route | Fits when | Can't find |
|---|---|---|---|
| 1 | Business database filters (Apollo-style) | On LinkedIn, broad buyer | Small local businesses |
| 2 | Lookalikes of your best customers (Ocean.io, DiscoLike) | 5 or more happy customers | Anything, if you have no customers yet |
| 3 | Niche companies by website wording (DiscoLike) | Their site uses telling words | Sites that don't say it |
| 4 | Maps, directories and job boards via scraping (Apify and similar) | Buyer sits on a map or directory | Anyone not listed in public |
| 5 | Hiring and tools-used signals (TheirStack) | A tool or role shows the need | Companies that never post jobs |
| 6 | People who write or engage about a topic (Apify post scrapers, forums) | Very narrow buyer, talks about one thing in public | Quiet buyers; also catches fans and competitors |

The script scores the answers and returns one route, or two when the second is close. It never returns more than two. Lookalikes are skipped unless there are 5 or more customers. If the answers don't point at anything, it says so and gives a safe starting point.

## What the person gets

For each route: why it fits, what it can't find, the exact first step, and the tool facts with a source link and a "last checked" date. Then a short "Before you start" list with the warnings that apply.

## Rules for the agent

- **Never state a tool fact that is not in `facts.json`.** Every claim there has a source and a date. If the person asks about something not in the file, say it is not checked and look it up with a source, or say you don't know. Never guess a price, a limit or a feature.
- **Say how old a fact is.** Prices and credits change. If `last_checked` is more than a few months old, tell the person to open the source link first.
- **Vendor pages are marketing.** Facts marked "vendor claim" are what the vendor says. Say so.
- **Recommend one or two routes, never all six.**
- **Route 6 always carries the weak-signal warning**: people who comment about a topic include competitor staff, students and fans.
- **LinkedIn**: scraping or automating LinkedIn breaks its User Agreement (Section 8.2) and can get accounts restricted. Say so whenever route 6 is chosen, or route 4 with LinkedIn as a footprint.
- **EU/UK buyers**: "public" does not mean free to use. The person becomes the data controller and needs a lawful basis. This is not legal advice.
- **Sensitive topics** (health, religion, politics and similar) can be special-category data under GDPR Article 9. Suggest finding the places and creators these people follow, not a list of individuals.
- **No personal data in demos.** Use made-up buyers. Never put a real person's name, profile or post into the tests, the facts or an example.
- **No contact data.** Do not recommend contact finders or email checks here. Point to the tool the person already uses.
- **Do not run a scraper for the person.** Describe the first step and let them run it.

## Files

- [`recommend.py`](recommend.py): the decision rules and report
- [`facts.json`](facts.json): every tool and rule fact, with source link, how it was read, and the date
- [`FACTCHECK.md`](FACTCHECK.md): what was checked, what was not, and where sources disagree
- [`README.md`](README.md): the short version for people
- Tests: `tests/test_lead_source_finder.py` (ten made-up buyer scenarios and checks on the fact sheet)
