# FACTCHECK: lead-source-finder

Checked on **2026-11-25**. Every claim in `facts.json` has a source link. This file says how each was read and what is not settled. Open the link before you rely on a number.

## How the facts were read

| Read how | Facts |
|---|---|
| Fetched the page | `discolike-1` to `discolike-3` (discolike.com home page) |
| Read in a web-search excerpt of the page, page not opened in full | all the others |

An excerpt can leave out nearby caveats. So treat "search excerpt" facts as leads to confirm, not as final. Upgrading them to "page" is the first thing to do when a fact matters for a decision.

## Where sources disagree or are weak

- **Apollo plans, credits and database size.** Third-party articles disagree on all three, so `facts.json` holds only the filter claim and the lookalike feature from Apollo's own pages, with **no prices or counts**.
- **TheirStack counts.** Job-posting and company counts differ between its own pages, so no counts are in `facts.json`.
- **Ocean.io's 10-seed limit** is stated in Clay's docs for the Clay integration. Ocean.io's own limit may differ. `ocean-2` says so.
- **Apify actors.** Many actors are community-made and some were marked "under maintenance" or "Deprecated". No single actor is recommended on purpose. Check the maintainer, last update and reviews.
- **DiscoLike** statements are the vendor's own marketing. A DiscoLike versus Ocean.io comparison page exists, but vendors write their own comparisons, so none is used here.
- **Route 6 tools by platform.** LinkedIn (Apify actors, PhantomBuster, Clay, Sales Navigator), X (Apify actors) and YouTube (Data API quota) have tool facts. **Reddit has rules but no scraper is named**, because Reddit's own position is that commercial use needs an agreement; third-party summaries disagree on details, so no price is stated. Stack Overflow, Hacker News, Facebook, Instagram and TikTok were not researched.
- **Reddit rules** (`reddit-1`, `reddit-2`) come from third-party summaries, not Reddit's own pages. Open Reddit's Data API Terms before relying on them.
- **X API pricing and the X API route** were not checked. `x-2` only says what X's terms say about scraping.
- **YouTube**: only API quota facts. YouTube's rules on using commenters as leads were not checked. The report says so.
- **Trigify** was left out. Sources disagreed on its status (one said "before the shutdown"). Check it yourself if you want it.
- **Alert tools** (`listen-1`, `listen-2`) come from listing sites and G2, not the vendors' own pages.

- **Routes 1 to 5 tool lists (added 2026-11-25).** Added ZoomInfo, Cognism, Clay, Crunchbase (route 1), Apollo, Clay, Landbase, Dealfront lookalikes (route 2), Clay, Exa Websets, Parallel FindAll (route 3), Outscraper, Google Places API and more Apify actors (route 4), BuiltWith, Wappalyzer, Bloomberry, PredictLeads, Coresignal (route 5). All were read in search excerpts, not full pages.
- **Competitor claims.** Several facts come from a rival's page (Clay on Apollo, UpLead on credits, TheirStack on Coresignal and PredictLeads, Parallel on Exa, a competitor on Outscraper). They are labelled `competitor claim` in the report. Use them as questions to test, not as verdicts.
- **Database sizes are not stated** for ZoomInfo, Apollo, Lusha or Cognism because vendors' pages disagree.
- **No prices anywhere (decided 2026-11-25).** The skill decides where to look, not what it costs, and prices change and disagree between sources. Every dollar figure was removed from `facts.json`, and the report points people to each vendor's own pricing page. "What does it cost per 1,000?" stays as a question in the checklist.
- **Left out on purpose:** Seamless.AI, RocketReach, UpLead and similar contact-data tools (contact data is out of scope), and Trigify (unclear status).

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
