---
name: domain-health
version: 1.0.0
description: Check the DNS health of cold-email sending domains and hand back a plain-English "fix now / worth fixing / ignore / not checked" list per domain. Read-only DNS lookups, no keys, nothing sent. Covers SPF (one record, lookup count, policy), DMARC (exists, policy, reports), MX, DKIM (for selectors you give it, plus a few common guesses), and three domain blocklists with severity, so a harmless listing is not treated like a hacked site. Use when the user says "domain health", "check my domains", "is my domain ok", "SPF", "DMARC", "DKIM", "blacklisted", "blocklist", "deliverability check", or "why are my emails going to spam".
---

# domain-health

A domain check that tells you what to fix, not just what it found.

Cold email lives or dies on the sending domain. This skill reads the public DNS for each domain and tells the person, in one short list per domain, what to fix now, what is worth fixing, what is fine, and what it could not check. It only reads. It never changes DNS, never sends, and never needs a key. A human changes the records.

Origin: built as an add-on to Shawn Villaron's [gtm-coding-agent](https://github.com/shawnla90/gtm-coding-agent) (MIT) and follows the same skill format. The checks and the script are independent of the rest of the repo.

## Inputs

- A list of domains, one per run or one per line in a file. Use the registered domain (`example.com`), not a subdomain, because the blocklists work on registered domains.
- Optional DKIM selectors, per domain: `example.com:google,selector1`. A selector is a name the sending tool picks, so it has to come from the person. See "DKIM selectors" below.
- Nothing else. No API keys, no accounts.

## Run

```bash
python3 skills/domain-health/check_domain.py example.com other.org
python3 skills/domain-health/check_domain.py example.com:google,s1 --out report.md
python3 skills/domain-health/check_domain.py --file domains.txt --format json
```

Standard library only; Python 3.8 or newer. The script stops with a clear message instead of reporting if the DNS resolver cannot find `example.com`, because every "does not exist" verdict would be wrong. Before reading the results, confirm the run was not skipped.

Tests, offline: `python3 -m unittest tests/test_domain_health.py`. A recorded-answer demo: `python3 skills/domain-health/check_domain.py good-example.com broken-example.com --fixture tests/fixtures/domain_health_demo.json`.

## What it checks, and how each result is classed

| Check | Result | Class |
|---|---|---|
| SPF | No record | `fix_now` |
| SPF | More than one record | `fix_now` (SPF fails outright) |
| SPF | More than 10 DNS lookups, or an include with no SPF record | `fix_now` |
| SPF | 8 to 10 lookups | `worth_fixing` |
| SPF | Ends in `+all` | `fix_now` |
| SPF | Ends in `?all`, or has no `all` | `worth_fixing` |
| SPF | One record, under 8 lookups, ends `~all` or `-all` | `ignore` (fine) |
| DMARC | No record, bad `p=`, or more than one record | `fix_now` |
| DMARC | `p=none` | `worth_fixing` (fine to start; do not stay) |
| DMARC | No `rua=` reports address | `worth_fixing` |
| DMARC | `quarantine` or `reject` with reports | `ignore` (fine) |
| MX | No MX, or a null MX | `worth_fixing` (replies cannot arrive) |
| MX | An MX host with no address | `worth_fixing` |
| DKIM | A selector you gave has no key | `fix_now` |
| DKIM | Key published, or revoked (empty `p=`) | `ignore` / `worth_fixing` |
| DKIM | No selector given and none of the common guesses found a key | `not_checked`, never "missing" |
| Spamhaus DBL | Spam, phishing, malware, botnet, or abused-legit codes | `fix_now` |
| SURBL multi | Phishing, malware, or cracked bits | `fix_now` |
| SURBL multi | Abuse bit only | `worth_fixing` |
| SURBL multi | Disposable-email bit only | `ignore` |
| URIBL multi | Black | `fix_now` |
| URIBL multi | Grey or red only | `ignore` (watched, not judged bad) |
| Any list | Blocked, rate limited, or public-resolver error code | `not_checked`, never "listed" |
| Any lookup | Timeout or server error | `not_checked`, never "missing" |

The return codes behind the blocklist rows are in `FACTCHECK.md`. Read it before quoting a code or a limit.

## Reading the result with the person

1. Start with the summary table, then the `Fix now` list for each domain. Quote the finding and its "How" line as written.
2. Treat `not_checked` as a to-do, not as a pass. DKIM with no selector is the usual one.
3. A blocklist listing is a reason to look, not automatically a reason to panic. SURBL and URIBL matter most when the domain appears in the links of the emails. A listing as phishing, malware, or "cracked" usually means the website was hacked. Find out why before asking for removal.
4. DMARC `p=none` on a new domain is a normal starting point. Say so, and say when to move on (after reading reports for a few weeks).
5. Any DNS change is the person's call. Offer the record text; do not apply it.

## DKIM selectors

DKIM cannot be checked from the domain alone. The public key lives at `<selector>._domainkey.<domain>`, and the selector is a name the sending tool chose.

- If the person gives selectors, check exactly those. A missing key for a selector they gave is a real `fix_now`.
- If they give none, the script tries a short list of common names (`google`, `selector1`, `selector2`, `k1`, `s1`, `default`, and a few more). A hit is reported. A miss is `not_checked`, because the tool may use a name that is not on the list.
- To find the real selector: the DKIM setup page of the sending tool, or the `DKIM-Signature` header of a sent email (`d=<domain>; s=<selector>`).
- Microsoft 365 publishes DKIM as a CNAME to a TXT; the lookup follows it.

## Safety

- Read-only. DNS lookups only. No keys, no accounts, no sending, no DNS writes.
- Input is validated: only real-looking domain names and selector names go into a lookup, and a run is capped at 100 domains.
- Blocklist lookups are paced (about 0.3 s apart). Do not loop this over thousands of domains. The free public mirrors have usage terms: Spamhaus's free use is for non-commercial use and not from a public resolver, and SURBL and URIBL block heavy use. For large or commercial volume, read each list's terms and use their data-feed options.
- Use your own network's resolver. The script skips blocklists, and says so, if the resolver is 1.1.1.1, 8.8.8.8, 9.9.9.9 or similar. Those get error codes from the lists, not answers.
- A report lists domains the person owns. Do not run it against someone else's domain to build a profile of them.

## Do

- Say which checks ran and which did not, every time.
- Keep `not_checked` visible. A silent skip looks like a pass.
- Give the "How" line next to each fix, and let the person decide.
- Re-run after a DNS change, and wait for the record's TTL (often minutes to an hour) before judging.
- Use the tests and the recorded demo when changing the script, so a change cannot turn a lookup failure into "missing".

## Don't

- Don't read an error code (`127.255.255.254`, `127.255.255.255`, `127.0.0.1` from SURBL or URIBL) as a listing.
- Don't say DKIM is missing because a guessed selector found nothing.
- Don't say a domain does not exist unless the check on `example.com` passed first (the script enforces this).
- Don't add `+all`, or a second SPF record, or a second DMARC record, as a fix.
- Don't promise a blocklist removal or a delivery result. The list decides, and a clean DNS is not a guarantee of inbox placement.
- Don't change DNS on the person's behalf.

## Related

- `FACTCHECK.md` in this folder: verified return codes, limits, and where each came from
- `../../skills/README.md` for the other skills
- `../../skills/moltsets-reachability/SKILL.md` for grading the addresses on a list, which this skill does not do (it checks the domain, not the person)
