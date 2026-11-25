# Add-on skills for gtm-coding-agent

Free, small skills for GTM work, built on top of [Shawn Tenam's gtm-coding-agent](https://github.com/shawnla90/gtm-coding-agent) (MIT). I picked his repo because it was the simplest one to build on. Each skill follows his skill format and lives in its own folder under `skills/`. The credit for the repo and the format is his, and his LICENSE is kept.

| Skill | What it does | Read more |
|---|---|---|
| [`domain-health`](skills/domain-health/) | Checks the DNS health of your cold email domains and tells you what to fix. | Below |
| [`lead-source-finder`](skills/lead-source-finder/) | Helps you decide where to find the right leads (database, lookalikes, maps, hiring signals, or people who write about a topic), before you build the list. | [Jump down](#lead-source-finder) |

---

# domain-health

A free, read-only DNS health check for cold email domains: SPF, DKIM, DMARC, MX and blocklists.You give it your domains, and it tells you what to fix.

Built as an add-on to [Shawn Tenam's gtm-coding-agent](https://github.com/shawnla90/gtm-coding-agent) (MIT). It follows the same skill format. Credit for the repo and the format is his.

## Why it exists

Buying domains for cold email is the easy part. The DNS setup after it is where things quietly go wrong: a missing record, a record that is there twice, a blocklist listing you never saw. Checking it by hand means several websites and a lot of guessing about which problems matter.

This runs all the checks in one go and sorts the results into a short list: **fix now**, **worth fixing**, **ignore**, and **not checked**.

## Quick start

You need Python 3 and a Terminal. Nothing to install.

```
git clone https://github.com/raoashwini21/gtm-coding-agent
cd gtm-coding-agent
python3 skills/domain-health/check_domain.py yourdomain.com
```

Check several domains at once: `python3 skills/domain-health/check_domain.py one.com two.com`

Add your DKIM selector (see below) like this: `yourdomain.com:selector1`

Using Claude Code? Open the repo and say "check the health of yourdomain.com".

## What you get

This is real output from the demo data (`tests/fixtures/domain_health_demo.json`), not a real domain.

| Domain | Fix now | Worth fixing | Not checked |
|---|---|---|---|
| good-example.com | 0 | 0 | 0 |
| broken-example.com | 5 | 2 | 0 |

For each domain you get the details. Here is the broken one, with a "How" line under each fix:

### broken-example.com

**Fix now**
- SPF: 2 SPF records found. More than one makes SPF fail outright.
  - How: Merge them into a single v=spf1 record.
- SPF: The record ends in +all (or has no qualifier), which allows anyone to send as this domain.
  - How: End the record with ~all, or -all once every sender is listed.
- DMARC: No DMARC record. Gmail requires one from bulk senders (5,000+ a day to personal Gmail) and recommends it for everyone.
  - How: Add a TXT record at _dmarc.broken-example.com: v=DMARC1; p=none; rua=mailto:<an inbox you read>
- DKIM: None of the selectors you gave (selector9) has a DKIM key published.
  - How: Copy the DKIM record from your sending tool's setup page and publish it as a TXT (or CNAME) record at <selector>._domainkey.broken-example.com.
- Spamhaus DBL: Listed as: spam domain.
  - How: Look the domain up and request removal at https://check.spamhaus.org. First find out why: an unfamiliar listing often means a hacked site or an unknown sender. Matters most when this domain appears in the links or the From address of your emails.

**Worth fixing**
- MX: No MX record. Replies to this domain cannot be delivered, and some receivers distrust a sender domain that cannot receive mail.
  - How: Point MX at your mailbox provider (Google Workspace, Microsoft 365, ...).
- SURBL multi: Listed as: spam/abuse.
  - How: Look the domain up and request removal at https://surbl.org (use the lookup on the site). First find out why: an unfamiliar listing often means a hacked site or an unknown sender. Matters most when this domain appears in the links or the From address of your emails.


## What it checks, in plain words

| Check | What it means | What it looks for |
|---|---|---|
| **SPF** | The list of servers allowed to send email for your domain | Exactly one record, under 10 lookups (nested ones count), sensible ending |
| **DKIM** | A signature that shows the email really came from you | A published key for the selector you give it, and a key that is not too weak |
| **DMARC** | What receivers should do when SPF and DKIM checks fail | A record exists, a valid policy, a reports address |
| **MX** | Where replies to your domain get delivered | Mail servers set up and reachable |
| **Spamhaus DBL, SURBL, URIBL** | Blocklists of domains tied to spam, phishing or malware | Whether you are listed, and in which category |

## How to read the list

- **Fix now:** something that is broken, or a serious listing. Do these first.
- **Worth fixing:** it works, but it is weak or risky. For example DMARC set to `p=none` is a fine start, not a place to stay.
- **Ignore / fine:** all good, or a minor note that does not usually affect delivery.
- **Not checked:** the tool could not be sure, so it says so instead of guessing. Treat it as a to-do. It is not a pass.

A blocklist listing is not always an emergency. A listing for phishing, malware or a hacked site is serious. A minor abuse-category listing may not matter much. The list tells you which kind you have. It does not tell you why you were listed or remove the listing: for that, use the list's own site, which the "How" line points to.

## DKIM selectors

DKIM cannot be checked from the domain alone. The key sits under a name your sending tool picked, called a selector, and the domain does not reveal it.

- Find it in your sending tool's DKIM setup page, or in the raw headers of a sent email (`DKIM-Signature: d=yourdomain.com; s=selector1`).
- Pass it like this: `yourdomain.com:selector1`.
- If you give none, the tool tries a few common names. A hit is shown. A miss is **not checked**, never "missing", because your tool may use a different name.

## Safe by design

- Read-only. It only looks up public DNS. It sends no email, changes no records and needs no keys or accounts.
- It only accepts valid-looking domain names, and a run is capped at 100 domains.
- Blocklist lookups are spaced out. Do not run it over thousands of domains. The free blocklist services have usage terms (for example, Spamhaus's free use is for non-commercial use), so read them for large or commercial volume.
- It refuses to report if your DNS cannot find `example.com`, because every "domain does not exist" result would then be wrong.
- It skips the blocklists, and says so, when your DNS is a public one (1.1.1.1, 8.8.8.8, 9.9.9.9). Those lists answer such servers with an error code, not real data.

## Limits

- It does not change your DNS. You make the fixes.
- A clean report does not guarantee inbox placement. Warmup, volume, content and complaint rates matter too.
- It checks domains, not sending IP addresses.
- The SPF lookup count follows the terms in your record, including nested includes. It does not count the extra lookups that `mx` and `a` terms trigger inside the lookup, so it can read a little low for records with many of those.
- Tested on Python 3.13 on Linux, with real DNS answers served from a local test server. It has also run live against a real domain. It is **not tested on Windows**. Windows has no `/etc/resolv.conf`, so it falls back to a public resolver (9.9.9.9) and skips the blocklists. Pass `--resolver` with your router's or provider's DNS address to get around that.

## Run the tests

```
python3 -m unittest tests/test_domain_health.py
```

They run offline against recorded DNS answers.

## More detail

- [`SKILL.md`](skills/domain-health/SKILL.md): the instructions for coding agents, with the full classification table
- [`FACTCHECK.md`](skills/domain-health/FACTCHECK.md): the verified blocklist return codes, limits, and where each came from

## Credit and license

Built on [Shawn Tenam's gtm-coding-agent](https://github.com/shawnla90/gtm-coding-agent). These skills follow his skill format, and the original MIT LICENSE is kept. The scripts and the tests are independent of the rest of the repo.

---

# lead-source-finder

Not sure where to find the right leads? Answer six plain questions about your buyer and get one or two routes, with the exact first step for each.

It is a decision helper for the step before the list. It does not fetch contact details, check emails or run any scraper. Once you have the list, use whatever contact tool you already use.

## Why it exists

No single tool finds every kind of buyer. A database finds companies on LinkedIn. A map scraper finds a dentist. A lookalike tool needs customers to copy. A post scraper finds people who write about one topic. Picking the wrong one wastes a week, so this asks about the buyer first.

## The six routes

1. Business database filters (Apollo-style)
2. Lookalikes of your best customers (needs 5 or more customers)
3. Niche companies found by website wording
4. Maps, directories and job boards, via scraping
5. Hiring and tools-used signals
6. People who write or engage about a topic

## Use it

```
git clone https://github.com/raoashwini21/gtm-coding-agent
cd gtm-coding-agent
python3 skills/lead-source-finder/recommend.py --answers answers.json
```

Or open the repo in Claude Code and say "where should I find leads for my buyer?". Every tool fact has a source link and a "last checked" date, and the report adds the LinkedIn, GDPR and weak-signal warnings that apply. Tests: `python3 -m unittest tests/test_lead_source_finder.py`.

More: [`README.md`](skills/lead-source-finder/README.md), [`SKILL.md`](skills/lead-source-finder/SKILL.md), [`FACTCHECK.md`](skills/lead-source-finder/FACTCHECK.md). Not legal advice.
