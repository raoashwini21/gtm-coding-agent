# FACTCHECK: lead-source-finder

Checked on **2026-11-25**. Every claim in `facts.json` has a source link. This file says how each was read and what is not settled. Open the link before you rely on a number.

## How the facts were read

| Read how | Facts |
|---|---|
| Fetched the page | `discolike-1` to `discolike-4` (discolike.com home page) |
| Read in a web-search excerpt of the page, page not opened in full | all the others |

An excerpt can leave out nearby caveats. So treat "search excerpt" facts as leads to confirm, not as final. Upgrading them to "page" is the first thing to do when a fact matters for a decision.

## Where sources disagree or are weak

- **Apollo plans and credits.** Third-party articles disagree on the free plan (for example 75 credits a month versus other credit mixes, and unlimited versus fair-use email credits) and on the size of the contact database (210M+, 240M+, 275M+ and 280M+ appear in different places). So `facts.json` holds only the filter claim from Apollo's own page and **no pricing or counts**. Check apollo.io/pricing.
- **TheirStack counts.** Job-posting and company counts differ between its own pages (for example 207M versus 259M job postings). No counts are in `facts.json`. The one price (`theirstack-4`) is what the pricing page showed in a search excerpt.
- **Ocean.io's 10-seed limit** is stated in Clay's docs for the Clay integration. Ocean.io's own limit may differ. `ocean-2` says so.
- **Apify actors.** Many LinkedIn post-search actors are community-made, priced differently ($1.50 to $5 per 1,000 posts in the listings seen) and some were marked "under maintenance". No single actor is recommended on purpose. Check the maintainer, last update and reviews.
- **Apify Google Maps pricing** is pay per event with paid add-ons. A listing showed "from $1.50 per 1,000 scraped places" but a clean source for that exact figure was not kept, so it is not in `facts.json`.
- **DiscoLike** statements are the vendor's own marketing. A DiscoLike versus Ocean.io comparison page exists, but vendors write their own comparisons, so none is used here.
- **Reddit, Stack Overflow and Hacker News scrapers** were not researched. Route 6 mentions forums as a place to look by hand. No forum scraper or its terms are claimed.

## Law and platform rules (not legal advice)

- **LinkedIn** (`linkedin-1`): from LinkedIn's own help page on prohibited software. It was read in a search excerpt. Whether any given scraping is lawful in a given country is a separate question this skill does not answer.
- **GDPR Article 9** (`gdpr-1`): the text of the Article as published on legislation.gov.uk (UK GDPR version) and gdpr-text.com. The UK and EU versions differ in small ways. Not legal advice.
- **ICO page** (`gdpr-2`): the ICO page is about training generative AI on scraped data. It is used only for the general point that scraped web content can contain personal data and needs a lawful basis. It is not a ruling on lead lists.
- **"Public does not mean free to use"** is the skill's plain-words summary of the two points above. It is a warning, not a legal conclusion.

## Related work

A third-party skill on a similar topic exists (ColdIQ's "lead-sources-guide" on skills.sh). It was not copied. This skill differs by asking about the buyer first, returning one or two routes with sources and dates, and carrying the safety warnings.

## What this skill does not check

- Whether a tool still works today, or whether its data is good for your buyer.
- Contact data and email validity (out of scope on purpose).
- Anything about a specific company, person or list.

## How to refresh

1. Open each source link in `facts.json`.
2. Fix the claim if the page changed. Set `how` to `page` if you read the whole page.
3. Update `last_checked`.
4. Run `python3 -m unittest tests/test_lead_source_finder.py`.
