#!/usr/bin/env python3
"""check_domain.py - read-only DNS health check for cold-email domains.

Checks SPF, DMARC, MX, DKIM (for selectors you give it, plus a few common
ones) and three domain blocklists, then prints a plain-English
"fix now / worth fixing / ignore / not checked" list per domain.

Rules this script keeps:
  * Read-only. DNS lookups only. No API keys, no sending, no writes.
  * Standard library only. Nothing to install.
  * A lookup that failed is "not checked", never "missing" and never "listed".
  * Blocklist error codes (blocked, rate limited, open resolver) are never
    read as a listing.

Usage:
  python3 check_domain.py example.com other.org
  python3 check_domain.py example.com:google,selector1 --format json
  python3 check_domain.py --file domains.txt --out report.md
  python3 check_domain.py example.com --fixture recorded_dns.json   # offline test
"""
import argparse
import base64
import datetime
import json
import os
import random
import re
import socket
import struct
import sys
import time

VERSION = "1.0.0"
MAX_DOMAINS = 100  # hard cap per run: keeps blocklist usage small

DOMAIN_RE = re.compile(
    r"^(?=.{1,253}$)([a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?\.)+(xn--[a-z0-9-]{1,59}|[a-z]{2,63})$"
)
SELECTOR_RE = re.compile(r"^[a-z0-9]([a-z0-9_-]{0,62}[a-z0-9])?$")

# Selectors worth a guess when none are supplied. A miss here does NOT mean
# DKIM is missing: a selector is a name the sending tool picks.
COMMON_SELECTORS = [
    "default", "google", "selector1", "selector2", "k1", "k2", "s1", "s2",
    "dkim", "mail", "smtp", "mandrill", "mte1", "mxvault", "everlytickey1",
]

# Resolvers that Spamhaus, SURBL and URIBL answer with an error code.
PUBLIC_RESOLVERS = {
    "1.1.1.1", "1.0.0.1", "8.8.8.8", "8.8.4.4", "9.9.9.9", "149.112.112.112",
    "208.67.222.222", "208.67.220.220", "94.140.14.14", "94.140.15.15",
}

BLOCKLISTS = [
    {"name": "Spamhaus DBL", "zone": "dbl.spamhaus.org",
     "lookup": "https://check.spamhaus.org"},
    {"name": "SURBL multi", "zone": "multi.surbl.org",
     "lookup": "https://surbl.org (use the lookup on the site)"},
    {"name": "URIBL multi", "zone": "multi.uribl.com",
     "lookup": "https://lookup.uribl.com"},
]

LEVEL_ORDER = {"fix_now": 0, "worth_fixing": 1, "ignore": 2, "not_checked": 3}
LEVEL_TITLES = {
    "fix_now": "Fix now",
    "worth_fixing": "Worth fixing",
    "ignore": "Fine / ignore",
    "not_checked": "Not checked",
}


# --------------------------------------------------------------------------
# Minimal DNS client (UDP, TCP fallback). Returns plain values.
# --------------------------------------------------------------------------
QTYPES = {"A": 1, "NS": 2, "CNAME": 5, "MX": 15, "TXT": 16}


def system_nameservers():
    servers = []
    try:
        with open("/etc/resolv.conf") as f:
            for line in f:
                parts = line.split()
                if len(parts) >= 2 and parts[0] == "nameserver" and ":" not in parts[1]:
                    servers.append(parts[1])
    except OSError:
        pass
    return servers or ["9.9.9.9"]


def _read_name(d, off):
    labels, end, hops = [], None, 0
    while True:
        if off >= len(d):
            raise ValueError("truncated name")
        n = d[off]
        if n == 0:
            off += 1
            break
        if n & 0xC0 == 0xC0:
            ptr = ((n & 0x3F) << 8) | d[off + 1]
            if end is None:
                end = off + 2
            off = ptr
            hops += 1
            if hops > 20:
                raise ValueError("name loop")
            continue
        off += 1
        labels.append(d[off:off + n].decode("ascii", "replace"))
        off += n
    return ".".join(labels), (end if end is not None else off)


def parse_response(d):
    """Return (rcode, truncated, [(type, value), ...]) from a DNS reply."""
    _tid, flags, qd, an, _ns, _ar = struct.unpack("!HHHHHH", d[:12])
    rcode, tc = flags & 15, bool(flags & 0x200)
    off = 12
    for _ in range(qd):
        _, off = _read_name(d, off)
        off += 4
    recs = []
    for _ in range(an):
        _, off = _read_name(d, off)
        rtype, _cls, _ttl, rl = struct.unpack("!HHIH", d[off:off + 10])
        off += 10
        rd = d[off:off + rl]
        if rtype == 1 and rl == 4:
            recs.append(("A", ".".join(str(b) for b in rd)))
        elif rtype == 16:
            s, i = b"", 0
            while i < len(rd):
                n = rd[i]
                s += rd[i + 1:i + 1 + n]
                i += 1 + n
            recs.append(("TXT", s.decode("utf-8", "replace")))
        elif rtype == 15:
            pref = struct.unpack("!H", rd[:2])[0]
            host, _ = _read_name(d, off + 2)
            recs.append(("MX", (pref, host.lower())))
        elif rtype == 2:
            host, _ = _read_name(d, off)
            recs.append(("NS", host.lower()))
        elif rtype == 5:
            host, _ = _read_name(d, off)
            recs.append(("CNAME", host.lower()))
        off += rl
    return rcode, tc, recs


def build_query(name, qtype):
    tid = random.randint(0, 65535)
    header = struct.pack("!HHHHHH", tid, 0x0100, 1, 0, 0, 0)
    qname = b"".join(bytes([len(p)]) + p.encode("ascii") for p in name.rstrip(".").split(".")) + b"\0"
    return tid, header + qname + struct.pack("!HH", QTYPES[qtype], 1)


class DnsResolver:
    """Real resolver. query() never raises: errors come back in the result."""

    def __init__(self, servers=None, timeout=4.0):
        self.servers = servers or system_nameservers()
        self.timeout = timeout
        self.uses_public_resolver = bool(set(self.servers) & PUBLIC_RESOLVERS)

    def _udp(self, server, packet, tid):
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(self.timeout)
        try:
            s.sendto(packet, (server, 53))
            while True:
                data = s.recv(4096)
                if len(data) >= 12 and struct.unpack("!H", data[:2])[0] == tid:
                    return data
        finally:
            s.close()

    def _tcp(self, server, packet, tid):
        s = socket.create_connection((server, 53), timeout=self.timeout)
        try:
            s.sendall(struct.pack("!H", len(packet)) + packet)
            raw = b""
            while len(raw) < 2:
                chunk = s.recv(2 - len(raw))
                if not chunk:
                    raise OSError("closed")
                raw += chunk
            want = struct.unpack("!H", raw)[0]
            data = b""
            while len(data) < want:
                chunk = s.recv(want - len(data))
                if not chunk:
                    raise OSError("closed")
                data += chunk
            return data
        finally:
            s.close()

    def query(self, name, qtype):
        tid, packet = build_query(name, qtype)
        last_error = "no answer"
        for server in self.servers:
            for _attempt in range(2):
                try:
                    data = self._udp(server, packet, tid)
                    rcode, tc, recs = parse_response(data)
                    if tc:
                        data = self._tcp(server, packet, tid)
                        rcode, tc, recs = parse_response(data)
                except (OSError, ValueError, struct.error) as exc:
                    last_error = "%s: %s" % (server, exc.__class__.__name__)
                    continue
                if rcode in (0, 3):
                    return {"rcode": rcode,
                            "records": [v for t, v in recs if t == qtype],
                            "error": None}
                last_error = "%s: DNS error code %d" % (server, rcode)
                break
        return {"rcode": None, "records": [], "error": last_error}


class FixtureResolver:
    """Replays recorded answers so the checks can be tested offline.

    JSON file: {"example.com|TXT": ["v=spf1 ... -all"],
                "example.com|MX": [[10, "mx.example.com"]],
                "bad.example|A": "ERROR",
                "gone.example|TXT": "NXDOMAIN"}
    A key that is not listed behaves like NXDOMAIN.
    """

    uses_public_resolver = False

    def __init__(self, data):
        self.data = data

    def query(self, name, qtype):
        v = self.data.get("%s|%s" % (name.lower(), qtype), "NXDOMAIN")
        if v == "ERROR":
            return {"rcode": None, "records": [], "error": "fixture error"}
        if v == "NXDOMAIN":
            return {"rcode": 3, "records": [], "error": None}
        recs = [tuple(x) if isinstance(x, list) else x for x in v]
        return {"rcode": 0, "records": recs, "error": None}


def resolver_problem(res):
    """Return a plain-English problem if the resolver cannot be trusted, else None.

    example.com is reserved by IANA and always has an address. If the resolver
    cannot find it, every "domain does not exist" verdict below would be false
    (offline, captive-portal Wi-Fi, a filtering or broken resolver).
    """
    r = res.query("example.com", "A")
    if r["error"]:
        return "DNS lookups are failing (%s)." % r["error"]
    if r["rcode"] == 3 or not r["records"]:
        return "the resolver says example.com does not exist, so it is not giving real answers."
    return None


# --------------------------------------------------------------------------
# Findings
# --------------------------------------------------------------------------
def finding(level, check, message, fix=None):
    return {"level": level, "check": check, "message": message, "fix": fix}


def worst(levels):
    return min(levels, key=lambda lv: LEVEL_ORDER[lv])


def txt_lookup(res, name):
    r = res.query(name, "TXT")
    return r["records"], r["rcode"], r["error"]


# --------------------------------------------------------------------------
# SPF
# --------------------------------------------------------------------------
def _spf_only(txts):
    return [t for t in txts if re.match(r"(?i)^v=spf1(\s|$)", t.strip())]


def spf_walk(res, domain, st, depth=0):
    """Count DNS-lookup terms; return the policy qualifier of the final 'all'."""
    if domain in st["seen"] or depth > 10:
        st["errors"].append("SPF include loop or too deep at %s" % domain)
        return None
    st["seen"].add(domain)
    txts, rcode, err = txt_lookup(res, domain)
    if err:
        st["unchecked"].append("%s (%s)" % (domain, err))
        return None
    recs = _spf_only(txts)
    if not recs:
        st["errors"].append("%s has no SPF record but is referenced" % domain)
        return None
    if len(recs) > 1 and depth > 0:
        st["errors"].append("%s (included from the main record) has more than one SPF record" % domain)
    policy = None
    redirect_policy = None
    for term in recs[0].split()[1:]:
        t = term.lower()
        q = ""
        if t[:1] in "+-~?":
            q, t = t[0], t[1:]
        mech = re.split(r"[:/=]", t, maxsplit=1)[0]
        val = t.split(":", 1)[1] if ":" in t else (t.split("=", 1)[1] if "=" in t else "")
        if mech == "include" and val:
            st["lookups"] += 1
            spf_walk(res, val, st, depth + 1)
        elif mech == "redirect" and val:
            st["lookups"] += 1
            redirect_policy = spf_walk(res, val, st, depth + 1)
        elif mech in ("a", "mx", "ptr", "exists"):
            st["lookups"] += 1
        elif mech == "all":
            policy = q or "+"
    return policy if policy is not None else redirect_policy


def check_spf(res, domain):
    out = []
    txts, rcode, err = txt_lookup(res, domain)
    if err:
        return [finding("not_checked", "SPF", "Could not look up TXT records (%s)." % err)]
    recs = _spf_only(txts)
    if not recs:
        return [finding("fix_now", "SPF",
                        "No SPF record. Receiving servers cannot confirm who may send for this domain.",
                        "Add one TXT record at the domain: v=spf1 include:<your sending provider> ~all "
                        "(your sending tool's setup page gives the exact include).")]
    if len(recs) > 1:
        out.append(finding("fix_now", "SPF",
                           "%d SPF records found. More than one makes SPF fail outright." % len(recs),
                           "Merge them into a single v=spf1 record."))
    st = {"lookups": 0, "seen": set(), "errors": [], "unchecked": []}
    policy = spf_walk(res, domain, st)
    n = st["lookups"]
    if n > 10:
        out.append(finding("fix_now", "SPF",
                           "SPF needs %d DNS lookups; the limit is 10. Over the limit, SPF returns an error "
                           "and counts as a fail." % n,
                           "Remove includes you no longer use, or flatten the record."))
    elif n >= 8:
        out.append(finding("worth_fixing", "SPF",
                           "SPF uses %d of the 10 allowed DNS lookups. Adding one more tool could break it." % n,
                           "Remove unused includes before adding new ones."))
    for e in st["errors"]:
        out.append(finding("fix_now", "SPF", e + ".", "Fix or remove that include."))
    if st["unchecked"]:
        out.append(finding("not_checked", "SPF",
                           "Could not follow part of the SPF chain: " + "; ".join(st["unchecked"]) + "."))
    if policy == "+":
        out.append(finding("fix_now", "SPF",
                           "The record ends in +all (or has no qualifier), which allows anyone to send as this domain.",
                           "End the record with ~all, or -all once every sender is listed."))
    elif policy == "?":
        out.append(finding("worth_fixing", "SPF",
                           "The record ends in ?all, which says nothing about unlisted senders.",
                           "Change to ~all, or -all once every sender is listed."))
    elif policy is None and not st["errors"] and not st["unchecked"]:
        out.append(finding("worth_fixing", "SPF",
                           "The record has no 'all' ending, so unlisted senders get no verdict.",
                           "Add ~all (or -all) at the end."))
    if not any(f["level"] in ("fix_now", "worth_fixing") for f in out) and not st["unchecked"]:
        word = {"-": "-all (strict)", "~": "~all (soft fail, the usual choice)"}.get(policy, "")
        out.append(finding("ignore", "SPF", "SPF is fine: one record, %d of 10 lookups, ends %s." % (n, word)))
    return out


# --------------------------------------------------------------------------
# DMARC
# --------------------------------------------------------------------------
def check_dmarc(res, domain):
    txts, rcode, err = txt_lookup(res, "_dmarc." + domain)
    if err:
        return [finding("not_checked", "DMARC", "Could not look up _dmarc TXT (%s)." % err)]
    recs = [t for t in txts if re.match(r"(?i)^v=DMARC1\s*;?", t.strip())]
    if not recs:
        return [finding("fix_now", "DMARC",
                        "No DMARC record. Gmail requires one from bulk senders (5,000+ a day to personal Gmail) and recommends it for everyone.",
                        "Add a TXT record at _dmarc.%s: v=DMARC1; p=none; rua=mailto:<an inbox you read>" % domain)]
    out = []
    if len(recs) > 1:
        out.append(finding("fix_now", "DMARC",
                           "%d DMARC records found. Receivers ignore DMARC when there is more than one." % len(recs),
                           "Keep a single v=DMARC1 record."))
    tags = {}
    for part in recs[0].split(";"):
        if "=" in part:
            k, v = part.split("=", 1)
            tags[k.strip().lower()] = v.strip()
    p = tags.get("p", "").lower()
    if p not in ("none", "quarantine", "reject"):
        out.append(finding("fix_now", "DMARC", "The policy (p=) is missing or invalid: %r." % tags.get("p", ""),
                           "Set p=none, p=quarantine or p=reject."))
    elif p == "none":
        out.append(finding("worth_fixing", "DMARC",
                           "Policy is p=none: monitoring only, spoofed mail is still delivered. Fine while you are "
                           "starting out, not a place to stay.",
                           "Read the reports for a few weeks, then move to p=quarantine."))
    if "rua" not in tags:
        out.append(finding("worth_fixing", "DMARC",
                           "No rua= address, so you never see DMARC reports (spoofing or failing senders).",
                           "Add rua=mailto:<an inbox you read> (or a DMARC report service)."))
    if tags.get("pct") not in (None, "100"):
        out.append(finding("ignore", "DMARC", "pct=%s: the policy applies to only part of the mail." % tags["pct"]))
    if not any(f["level"] in ("fix_now", "worth_fixing") for f in out):
        out.append(finding("ignore", "DMARC", "DMARC is fine: p=%s, reports go to %s." % (p, tags.get("rua", "-"))))
    return out


# --------------------------------------------------------------------------
# MX
# --------------------------------------------------------------------------
def check_mx(res, domain):
    r = res.query(domain, "MX")
    if r["error"]:
        return [finding("not_checked", "MX", "Could not look up MX (%s)." % r["error"])]
    mxs = [tuple(x) for x in r["records"]]
    if not mxs:
        return [finding("worth_fixing", "MX",
                        "No MX record. Replies to this domain cannot be delivered, and some receivers distrust "
                        "a sender domain that cannot receive mail.",
                        "Point MX at your mailbox provider (Google Workspace, Microsoft 365, ...).")]
    if len(mxs) == 1 and mxs[0][1] in ("", "."):
        return [finding("worth_fixing", "MX",
                        "MX is a null MX ('0 .'): the domain says it accepts no mail, so replies will bounce.",
                        "Replace it with your mailbox provider's MX records if this domain sends cold email.")]
    out, unchecked = [], False
    for _pref, host in sorted(mxs)[:5]:
        a = res.query(host, "A")
        if a["error"]:
            unchecked = True
        elif not a["records"]:
            # an MX host may be IPv6-only, but that is rare; call it out for a look
            out.append(finding("worth_fixing", "MX", "MX host %s has no IPv4 address." % host,
                               "Check the host name for a typo."))
    if unchecked:
        out.append(finding("not_checked", "MX", "Could not resolve one or more MX hosts."))
    if not out:
        out.append(finding("ignore", "MX", "MX is fine: %s." % ", ".join(h for _, h in sorted(mxs))))
    return out


# --------------------------------------------------------------------------
# DKIM
# --------------------------------------------------------------------------
def _dkim_record(txts):
    for t in txts:
        if re.search(r"(?i)(^|;)\s*v=DKIM1", t) or re.search(r"(^|;)\s*p=", t):
            return t
    return None


def check_dkim(res, domain, selectors, given):
    found, revoked, unchecked = [], [], []
    for sel in selectors:
        txts, rcode, err = txt_lookup(res, "%s._domainkey.%s" % (sel, domain))
        if err:
            unchecked.append(sel)
            continue
        rec = _dkim_record(txts)
        if not rec:
            continue
        m = re.search(r"(?:^|;)\s*p=([^;]*)", rec)
        key = re.sub(r"\s+", "", m.group(1)) if m else ""
        if not key:
            revoked.append(sel)
            continue
        try:
            size = len(base64.b64decode(key + "=" * (-len(key) % 4)))
        except Exception:
            size = 0
        found.append((sel, size))
    out = []
    for sel, size in found:
        if size and size < 150:
            out.append(finding("worth_fixing", "DKIM",
                               "Selector '%s' has a very short (weak) key." % sel,
                               "Generate a 2048-bit key in your sending tool."))
        else:
            bits = "about 1024-bit" if size < 200 else ("about 2048-bit" if size < 400 else "4096-bit or larger")
            note = " (2048 is preferred, but 1024 still works)" if size and size < 200 else ""
            out.append(finding("ignore", "DKIM", "Selector '%s' is published, key is %s%s." % (sel, bits, note)))
    for sel in revoked:
        out.append(finding("worth_fixing", "DKIM",
                           "Selector '%s' is published with an empty key (p=), which means it was revoked." % sel,
                           "Publish a fresh key from your sending tool, or stop using that selector."))
    if not found and not revoked:
        if unchecked and len(unchecked) == len(selectors):
            out.append(finding("not_checked", "DKIM", "Could not look up DKIM selectors."))
        elif given:
            out.append(finding("fix_now", "DKIM",
                               "None of the selectors you gave (%s) has a DKIM key published." % ", ".join(selectors),
                               "Copy the DKIM record from your sending tool's setup page and publish it as a "
                               "TXT (or CNAME) record at <selector>._domainkey.%s." % domain))
        else:
            out.append(finding("not_checked", "DKIM",
                               "None of the common selectors found a key. That does not mean DKIM is missing: "
                               "the selector is a name your sending tool picked, and it cannot be discovered "
                               "from the domain.",
                               "Get the selector from your sending tool (it is in the DKIM setup page or the "
                               "raw headers of a sent email, d=%s s=<selector>) and re-run with "
                               "%s:<selector>." % (domain, domain)))
    return out


# --------------------------------------------------------------------------
# Blocklists (domain-based lists only)
# --------------------------------------------------------------------------
def _dbl(ip):
    if ip.startswith("127.255.255.") or ip == "127.0.1.255":
        return "error", None, None
    table = {
        "127.0.1.2": ("fix_now", "spam domain"),
        "127.0.1.4": ("fix_now", "phishing domain"),
        "127.0.1.5": ("fix_now", "malware domain"),
        "127.0.1.6": ("fix_now", "botnet command-and-control domain"),
        "127.0.1.102": ("fix_now", "legitimate site abused for spam"),
        "127.0.1.103": ("fix_now", "abused redirector domain"),
        "127.0.1.104": ("fix_now", "legitimate site abused for phishing"),
        "127.0.1.105": ("fix_now", "legitimate site abused for malware"),
        "127.0.1.106": ("fix_now", "legitimate site abused as botnet C&C"),
    }
    if ip in table:
        return "listed", table[ip][0], table[ip][1]
    return "listed", "worth_fixing", "listed (code %s)" % ip


def _surbl(ip):
    if not ip.startswith("127.0.0."):
        return "listed", "worth_fixing", "listed (code %s)" % ip
    val = int(ip.rsplit(".", 1)[1])
    if val == 1:
        return "error", None, None
    bits = [(8, "phishing", "fix_now"), (16, "malware", "fix_now"), (128, "cracked (hacked) site", "fix_now"),
            (64, "spam/abuse", "worth_fixing"), (4, "disposable-email domain", "ignore")]
    labels, levels, rest = [], [], val
    for bit, label, level in bits:
        if val & bit:
            labels.append(label)
            levels.append(level)
            rest &= ~bit
    if rest:
        labels.append("other list (code %s)" % ip)
        levels.append("worth_fixing")
    return "listed", worst(levels), ", ".join(labels)


def _uribl(ip):
    if not ip.startswith("127.0.0."):
        return "listed", "worth_fixing", "listed (code %s)" % ip
    val = int(ip.rsplit(".", 1)[1])
    if val in (1, 255):
        return "error", None, None
    labels, levels = [], []
    if val & 2:
        labels.append("black list (spam)")
        levels.append("fix_now")
    if val & 4:
        labels.append("grey list (seen in mail, not judged bad)")
        levels.append("ignore")
    if val & 8:
        labels.append("red list (young domain or hidden owner, being watched)")
        levels.append("ignore")
    if not labels:
        labels, levels = ["listed (code %s)" % ip], ["worth_fixing"]
    return "listed", worst(levels), ", ".join(labels)


INTERPRET = {"dbl.spamhaus.org": _dbl, "multi.surbl.org": _surbl, "multi.uribl.com": _uribl}


def check_blocklists(res, domain, pause=0.0, force=False):
    if getattr(res, "uses_public_resolver", False) and not force:
        return [finding("not_checked", "Blocklists",
                        "Skipped: your DNS resolver is a public one (1.1.1.1, 8.8.8.8, 9.9.9.9 ...). Spamhaus, "
                        "SURBL and URIBL refuse those and answer with an error code, so the result would be "
                        "meaningless.",
                        "Run this from a network that uses its own resolver (your ISP's, or a local one), or "
                        "pass --resolver <that IP>.")]
    out = []
    for bl in BLOCKLISTS:
        r = res.query("%s.%s" % (domain, bl["zone"]), "A")
        if pause:
            time.sleep(pause)
        if r["error"]:
            out.append(finding("not_checked", bl["name"], "Lookup failed (%s)." % r["error"]))
            continue
        ips = r["records"]
        if r["rcode"] == 3 or not ips:
            out.append(finding("ignore", bl["name"], "Not listed."))
            continue
        statuses = [INTERPRET[bl["zone"]](ip) for ip in ips]
        listed = [s for s in statuses if s[0] == "listed"]
        if not listed:
            out.append(finding("not_checked", bl["name"],
                               "The list refused this query (blocked, rate limited, or public resolver). "
                               "That is not a listing.",
                               "Use your own resolver, or check by hand at %s." % bl["lookup"]))
            continue
        level = worst([s[1] for s in listed])
        what = "; ".join(sorted(set(s[2] for s in listed)))
        if level == "ignore":
            out.append(finding("ignore", bl["name"], "Listed as: %s. Usually not a delivery problem." % what))
        else:
            out.append(finding(level, bl["name"], "Listed as: %s." % what,
                               "Look the domain up and request removal at %s. First find out why: an unfamiliar "
                               "listing often means a hacked site or an unknown sender. Matters most when this "
                               "domain appears in the links or the From address of your emails." % bl["lookup"]))
    return out


# --------------------------------------------------------------------------
# Orchestration
# --------------------------------------------------------------------------
def parse_target(raw):
    """'example.com' or 'example.com:sel1,sel2' -> (domain, [selectors]) or raises ValueError."""
    raw = raw.strip().lower()
    domain, _, sels = raw.partition(":")
    if not DOMAIN_RE.match(domain):
        raise ValueError("not a valid domain name: %r" % raw[:80])
    selectors = []
    for s in [x for x in sels.split(",") if x]:
        if not SELECTOR_RE.match(s):
            raise ValueError("not a valid DKIM selector: %r" % s[:40])
        selectors.append(s)
    return domain, selectors


def check_domain(res, domain, selectors=None, blocklists=True, pause=0.0, force_blocklists=False):
    given = bool(selectors)
    txts, rcode, err = txt_lookup(res, domain)
    if not err and rcode == 3:
        return {"domain": domain, "findings": [
            finding("fix_now", "Domain", "The domain does not exist in DNS (NXDOMAIN).",
                    "Check the spelling, and that the domain is registered and its nameservers are set.")]}
    findings = []
    findings += check_spf(res, domain)
    findings += check_dmarc(res, domain)
    findings += check_mx(res, domain)
    findings += check_dkim(res, domain, selectors or COMMON_SELECTORS, given)
    if blocklists:
        findings += check_blocklists(res, domain, pause=pause, force=force_blocklists)
    return {"domain": domain, "findings": findings}


def render_markdown(results, date):
    lines = ["# Domain health report", "",
             "%s. Read-only DNS lookups. Nothing was sent or changed." % date, "",
             "| Domain | Fix now | Worth fixing | Not checked |", "|---|---|---|---|"]
    for r in results:
        c = {lv: sum(1 for f in r["findings"] if f["level"] == lv) for lv in LEVEL_ORDER}
        lines.append("| %s | %d | %d | %d |" % (r["domain"], c["fix_now"], c["worth_fixing"], c["not_checked"]))
    for r in results:
        lines += ["", "## " + r["domain"]]
        for lv in ("fix_now", "worth_fixing", "ignore", "not_checked"):
            items = [f for f in r["findings"] if f["level"] == lv]
            if not items:
                continue
            lines += ["", "**%s**" % LEVEL_TITLES[lv]]
            for f in items:
                lines.append("- %s: %s" % (f["check"], f["message"]))
                if f["fix"] and lv != "ignore":
                    lines.append("  - How: %s" % f["fix"])
    lines.append("")
    return "\n".join(lines)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Read-only DNS health check for cold-email domains.")
    ap.add_argument("domains", nargs="*", help="example.com or example.com:selector1,selector2")
    ap.add_argument("--file", help="text file, one domain per line (same selector syntax); # for comments")
    ap.add_argument("--selectors", help="DKIM selectors for every domain, comma separated")
    ap.add_argument("--format", choices=("md", "json"), default="md")
    ap.add_argument("--out", help="write the report to this file instead of printing it")
    ap.add_argument("--resolver", help="DNS server IP to use (default: your system resolver)")
    ap.add_argument("--no-blocklists", action="store_true", help="skip the blocklist lookups")
    ap.add_argument("--force-blocklists", action="store_true",
                    help="query blocklists even through a public resolver (results will be errors)")
    ap.add_argument("--fixture", help="JSON of recorded DNS answers; for offline tests")
    ap.add_argument("--version", action="version", version=VERSION)
    args = ap.parse_args(argv)

    raw = list(args.domains)
    if args.file:
        with open(args.file) as f:
            raw += [ln.split("#")[0].strip() for ln in f if ln.split("#")[0].strip()]
    if not raw:
        ap.error("give at least one domain")
    if len(raw) > MAX_DOMAINS:
        ap.error("too many domains (%d); the limit is %d per run" % (len(raw), MAX_DOMAINS))
    global_sels = [s.strip().lower() for s in (args.selectors or "").split(",") if s.strip()]
    targets, seen = [], set()
    for item in raw:
        try:
            domain, sels = parse_target(item)
        except ValueError as exc:
            ap.error(str(exc))
        if domain in seen:
            continue
        seen.add(domain)
        sels = sels or global_sels
        for s in sels:
            if not SELECTOR_RE.match(s):
                ap.error("not a valid DKIM selector: %r" % s[:40])
        targets.append((domain, sels))

    if args.fixture:
        with open(args.fixture) as f:
            res = FixtureResolver(json.load(f))
        pause = 0.0
    else:
        res = DnsResolver([args.resolver] if args.resolver else None)
        problem = resolver_problem(res)
        if problem:
            sys.stderr.write("Stopped: %s\nNo domain was checked, because the results would be wrong. "
                             "Check your internet connection, or pass --resolver <a DNS server IP>.\n" % problem)
            return 2
        pause = 0.3
    results = [check_domain(res, d, s, blocklists=not args.no_blocklists, pause=pause,
                            force_blocklists=args.force_blocklists) for d, s in targets]
    date = datetime.date.today().isoformat()
    text = (json.dumps({"date": date, "results": results}, indent=2) if args.format == "json"
            else render_markdown(results, date))
    if args.out:
        with open(args.out, "w") as f:
            f.write(text + "\n")
        print("wrote %s" % args.out)
    else:
        print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
