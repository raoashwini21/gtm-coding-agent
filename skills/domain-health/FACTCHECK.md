# FACTCHECK — domain-health

Hard gates. Read before quoting a blocklist code, a limit, or a sender rule. The Spamhaus, SURBL, URIBL and Gmail sections were checked against the sources named on each line on 2026-11-17. The "DNS and SPF" section is standard behaviour from the RFCs, cited from the RFC text and not re-fetched on that date. Re-check before quoting a number older than a few months: lists change their codes and terms.

## Spamhaus DBL (domain blocklist)

Zone `dbl.spamhaus.org`. Query `<domain>.dbl.spamhaus.org` as an A record. NXDOMAIN means not listed.

| Code | Meaning | Class here |
|---|---|---|
| 127.0.1.2 | spam / low-reputation domain | `fix_now` |
| 127.0.1.4 | phishing domain | `fix_now` |
| 127.0.1.5 | malware domain | `fix_now` |
| 127.0.1.6 | botnet C&C domain | `fix_now` |
| 127.0.1.102 to 127.0.1.106 | abused legitimate domain (spam, redirector, phish, malware, botnet) | `fix_now` |
| 127.0.1.255 | error: IP queried, the DBL lists domains only | not a listing |
| 127.255.255.252 | error: typo in the list name | not a listing |
| 127.255.255.254 | error: query came through a public/open resolver | not a listing |
| 127.255.255.255 | error: too many queries | not a listing |

Sources: docs.spamhaus.com (Available Zones, DBL return codes); spamhaus.org/news/article/788 and /807 (the 127.255.255.x error range, "must not be interpreted as reputation data"); check.spamhaus.org/faqs/dnsbl-usage (the DBL lists domains only, never IPs).

Usage terms: the free public mirrors are free if use is non-commercial and queries do not come from a public resolver or an IP with generic rDNS (spamhaus.org FAQ, DNSBL usage). Other public DNS servers are blocked from querying Spamhaus data. Removal from the DBL is free, and listings expire after the domain stops matching the criteria (check.spamhaus.org/faqs/domain-blocklist).

Unknown 127.0.1.x codes are reported as "listed (code X)" at `worth_fixing`, not guessed.

## SURBL (multi.surbl.org)

Query `<domain>.multi.surbl.org` as an A record. The answer is `127.0.0.N`, where N is a bitmask, and the bits add up when a domain is on several lists.

| Bit | List | Class here |
|---|---|---|
| 8 | PH, phishing | `fix_now` |
| 16 | MW, malware | `fix_now` |
| 128 | CR, cracked (hacked legitimate) sites | `fix_now` |
| 64 | ABUSE, spam and abuse | `worth_fixing` |
| 4 | DM, disposable email domains | `ignore` |
| 1 | not a listing: your access is blocked | not a listing |

Example: 127.0.0.80 is MW (16) plus ABUSE (64). Sources: surbl.org/lists and surbl.org/guidelines (result 127.0.0.1 means your access is blocked, "sign up for Sponsored Data Service"); SURBL's list announcement for the CR sublist and the migration of the older sublists into ABUSE (bit 64); the Rspamd RBL module's SURBL return bits (128, 64, 16, 8, 1).

SURBL also publishes a click-tracker list (CT) in multi. This script does not assign it a meaning; a code carrying an unrecognised bit is reported as "other list (code X)" at `worth_fixing`.

## URIBL (multi.uribl.com)

Query `<domain>.multi.uribl.com` as an A record. Bitmask `127.0.0.N`.

| Bit | List | Class here |
|---|---|---|
| 2 | black (spam) | `fix_now` |
| 4 | grey | `ignore` |
| 8 | red (young domain, or hides its owner; being watched) | `ignore` |
| 1 | not a listing: the query was refused or the nameserver was blocked for high volume | not a listing |

Source: uribl.com/about (bit table; "Query blocked, possibly due to high volume"); uribl.com/refused ("All queries that we refuse, we return a 127.0.0.1 response to"). 127.0.0.255 has also been reported by third parties as a blocked response; the script treats it as not a listing too.

## DNS and SPF (RFC behaviour, not re-fetched on 2026-11-17)

- SPF allows at most 10 DNS-lookup terms per evaluation: `include`, `a`, `mx`, `ptr`, `exists`, and `redirect` each count one, `ip4`, `ip6` and `all` count none. Over 10 is a permanent error, and SPF counts as a fail (RFC 7208, section 4.6.4). The script counts these terms through nested includes. It does not count the extra lookups that an `mx` or `a` term triggers internally, so the count can be a little low for records that use many `mx` terms.
- More than one `v=spf1` record on a name is a permanent error (RFC 7208, section 3.2).
- More than one DMARC record on `_dmarc.<domain>` means DMARC is ignored (RFC 7489, section 6.6.3).
- A DKIM record with an empty `p=` is a revoked key (RFC 6376, section 3.6.1).
- `example.com` is reserved by IANA and always resolves. The script looks it up first, and refuses to report if it does not resolve (offline, captive portal, filtering resolver).

## Sender rules

- Gmail, all senders to personal Gmail accounts: SPF or DKIM. Bulk senders (close to 5,000 or more messages a day to personal Gmail accounts): SPF, DKIM, and DMARC. DMARC is recommended, not required, for everyone else. Source: support.google.com/mail/answer/81126 (Email sender guidelines), checked 2026-11-17.
- Google says a sender who reaches the bulk threshold once is permanently treated as a bulk sender (Google's sender-guidelines FAQ, as quoted by third parties; not re-read on the primary page in this check).
- A DKIM key of at least 1024 bits is the minimum, 2048 recommended. Source: a secondary summary of Google's guidance, not the primary page. The script therefore treats a 1024-bit key as fine and only flags keys far shorter than that.

## What this skill cannot know

- Which DKIM selector a sending tool uses. It cannot be discovered from the domain.
- Whether a blocklist listing is hurting delivery. A listing on a list the receiver does not use does nothing. A clean result everywhere does not guarantee inbox placement.
- Blocklists of sending IP addresses. Those need the sending IPs, not the domain, and are not in this skill.
- Anything about the mailbox content, warmup, sending volume, or spam-complaint rate. Those decide delivery as much as DNS does.
