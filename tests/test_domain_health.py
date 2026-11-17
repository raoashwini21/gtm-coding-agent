"""Offline tests for skills/domain-health/check_domain.py. No network: DNS answers are replayed."""
import struct
import sys
import unittest
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parents[1] / "skills" / "domain-health"
sys.path.insert(0, str(SKILL_DIR))

import check_domain as C  # noqa: E402

GOOD_DKIM = "v=DKIM1; k=rsa; p=" + "A" * 392  # ~294 bytes decoded, about 2048-bit


def run(data, domain="example.com", selectors=None, blocklists=True):
    res = C.FixtureResolver(data)
    return C.check_domain(res, domain, selectors, blocklists=blocklists)["findings"]


def levels(findings, check):
    return [f["level"] for f in findings if f["check"] == check]


def healthy(**extra):
    d = {
        "example.com|TXT": ["v=spf1 include:_spf.mail.test ~all"],
        "_spf.mail.test|TXT": ["v=spf1 ip4:192.0.2.0/24 -all"],
        "_dmarc.example.com|TXT": ["v=DMARC1; p=quarantine; rua=mailto:dmarc@example.com"],
        "example.com|MX": [[10, "mx1.mail.test"]],
        "mx1.mail.test|A": ["192.0.2.10"],
        "google._domainkey.example.com|TXT": [GOOD_DKIM],
    }
    d.update(extra)
    return d


class WireFormatTests(unittest.TestCase):
    def test_parse_txt_and_mx_with_compression(self):
        # header: id, flags(response, rd, ra), qd=1, an=2
        header = struct.pack("!HHHHHH", 1, 0x8180, 1, 2, 0, 0)
        question = b"\x07example\x03com\x00" + struct.pack("!HH", 16, 1)
        txt = b"\xc0\x0c" + struct.pack("!HHIH", 16, 1, 60, 12) + b"\x0bv=spf1 -all"[:12]
        mx = b"\xc0\x0c" + struct.pack("!HHIH", 15, 1, 60, 9) + struct.pack("!H", 10) + b"\x03mx1\xc0\x0c"
        rcode, tc, recs = C.parse_response(header + question + txt + mx)
        self.assertEqual((rcode, tc), (0, False))
        self.assertIn(("TXT", "v=spf1 -all"), recs)
        self.assertIn(("MX", (10, "mx1.example.com")), recs)

    def test_txt_with_several_strings_is_joined(self):
        header = struct.pack("!HHHHHH", 1, 0x8180, 1, 1, 0, 0)
        question = b"\x01a\x00" + struct.pack("!HH", 16, 1)
        rdata = b"\x03abc\x03def"
        rr = b"\xc0\x0c" + struct.pack("!HHIH", 16, 1, 60, len(rdata)) + rdata
        _, _, recs = C.parse_response(header + question + rr)
        self.assertEqual(recs, [("TXT", "abcdef")])

    def test_name_loop_is_rejected(self):
        with self.assertRaises(ValueError):
            C._read_name(b"\xc0\x00", 0)


class InputTests(unittest.TestCase):
    def test_valid_targets(self):
        self.assertEqual(C.parse_target("Example.COM"), ("example.com", []))
        self.assertEqual(C.parse_target("example.com:google,s1"), ("example.com", ["google", "s1"]))

    def test_bad_domains_rejected(self):
        for bad in ["", "localhost", "exa mple.com", "example.com/path", "a..b.com", "-x.com",
                    "example.com;rm -rf", "http://example.com", "1.2.3.4"]:
            with self.assertRaises(ValueError, msg=bad):
                C.parse_target(bad)

    def test_bad_selector_rejected(self):
        with self.assertRaises(ValueError):
            C.parse_target("example.com:go ogle")


class SpfTests(unittest.TestCase):
    def test_healthy_is_fine(self):
        f = run(healthy(), blocklists=False)
        self.assertEqual(levels(f, "SPF"), ["ignore"])

    def test_missing_spf_is_fix_now(self):
        f = run(healthy(**{"example.com|TXT": ["some other txt"]}), blocklists=False)
        self.assertEqual(levels(f, "SPF"), ["fix_now"])

    def test_two_spf_records_is_fix_now_once(self):
        f = run(healthy(**{"example.com|TXT": ["v=spf1 -all", "v=spf1 ~all"]}), blocklists=False)
        self.assertEqual(levels(f, "SPF"), ["fix_now"])

    def test_over_ten_lookups_is_fix_now(self):
        txt = "v=spf1 " + " ".join("include:i%d.test" % i for i in range(11)) + " ~all"
        data = healthy(**{"example.com|TXT": [txt]})
        for i in range(11):
            data["i%d.test|TXT" % i] = ["v=spf1 -all"]
        f = run(data, blocklists=False)
        self.assertIn("fix_now", levels(f, "SPF"))

    def test_nested_lookups_are_counted(self):
        data = healthy(**{"example.com|TXT": ["v=spf1 include:a.test ~all"],
                          "a.test|TXT": ["v=spf1 " + " ".join("a:h%d.test" % i for i in range(9)) + " -all"]})
        # 1 include + 9 'a' terms = 10 lookups: at the limit, a warning, not a failure
        f = run(data, blocklists=False)
        self.assertEqual(levels(f, "SPF"), ["worth_fixing"])

    def test_plus_all_is_fix_now(self):
        f = run(healthy(**{"example.com|TXT": ["v=spf1 +all"]}), blocklists=False)
        self.assertIn("fix_now", levels(f, "SPF"))

    def test_question_all_is_worth_fixing(self):
        f = run(healthy(**{"example.com|TXT": ["v=spf1 ip4:192.0.2.1 ?all"]}), blocklists=False)
        self.assertEqual(levels(f, "SPF"), ["worth_fixing"])

    def test_include_without_spf_is_fix_now(self):
        f = run(healthy(**{"_spf.mail.test|TXT": ["nothing here"]}), blocklists=False)
        self.assertIn("fix_now", levels(f, "SPF"))

    def test_include_loop_does_not_hang(self):
        data = healthy(**{"example.com|TXT": ["v=spf1 include:a.test ~all"],
                          "a.test|TXT": ["v=spf1 include:example.com -all"]})
        f = run(data, blocklists=False)
        self.assertIn("fix_now", levels(f, "SPF"))

    def test_lookup_error_is_not_checked_not_missing(self):
        f = run(healthy(**{"example.com|TXT": "ERROR"}), blocklists=False)
        # TXT of the domain itself failed: no verdict anywhere that depends on it
        self.assertEqual(levels(f, "SPF"), ["not_checked"])


class DmarcTests(unittest.TestCase):
    def test_healthy(self):
        self.assertEqual(levels(run(healthy(), blocklists=False), "DMARC"), ["ignore"])

    def test_missing_is_fix_now(self):
        d = healthy()
        del d["_dmarc.example.com|TXT"]
        self.assertEqual(levels(run(d, blocklists=False), "DMARC"), ["fix_now"])

    def test_p_none_is_worth_fixing(self):
        d = healthy(**{"_dmarc.example.com|TXT": ["v=DMARC1; p=none; rua=mailto:a@example.com"]})
        self.assertEqual(levels(run(d, blocklists=False), "DMARC"), ["worth_fixing"])

    def test_no_rua_is_worth_fixing(self):
        d = healthy(**{"_dmarc.example.com|TXT": ["v=DMARC1; p=reject"]})
        self.assertEqual(levels(run(d, blocklists=False), "DMARC"), ["worth_fixing"])

    def test_bad_policy_is_fix_now(self):
        d = healthy(**{"_dmarc.example.com|TXT": ["v=DMARC1; p=banana; rua=mailto:a@example.com"]})
        self.assertIn("fix_now", levels(run(d, blocklists=False), "DMARC"))

    def test_duplicate_records_fix_now(self):
        d = healthy(**{"_dmarc.example.com|TXT": ["v=DMARC1; p=reject", "v=DMARC1; p=none"]})
        self.assertIn("fix_now", levels(run(d, blocklists=False), "DMARC"))


class MxTests(unittest.TestCase):
    def test_healthy(self):
        self.assertEqual(levels(run(healthy(), blocklists=False), "MX"), ["ignore"])

    def test_missing_mx(self):
        d = healthy()
        del d["example.com|MX"]
        self.assertEqual(levels(run(d, blocklists=False), "MX"), ["worth_fixing"])

    def test_null_mx(self):
        d = healthy(**{"example.com|MX": [[0, ""]]})
        self.assertEqual(levels(run(d, blocklists=False), "MX"), ["worth_fixing"])

    def test_mx_host_without_address(self):
        d = healthy()
        del d["mx1.mail.test|A"]
        self.assertEqual(levels(run(d, blocklists=False), "MX"), ["worth_fixing"])


class DkimTests(unittest.TestCase):
    def test_given_selector_found(self):
        f = run(healthy(), selectors=["google"], blocklists=False)
        self.assertEqual(levels(f, "DKIM"), ["ignore"])

    def test_given_selector_missing_is_fix_now(self):
        f = run(healthy(), selectors=["nope"], blocklists=False)
        self.assertEqual(levels(f, "DKIM"), ["fix_now"])

    def test_no_selector_and_none_found_is_not_checked(self):
        d = healthy()
        del d["google._domainkey.example.com|TXT"]
        f = run(d, blocklists=False)
        self.assertEqual(levels(f, "DKIM"), ["not_checked"])  # never "missing"

    def test_common_selector_guess_finds_it(self):
        self.assertEqual(levels(run(healthy(), blocklists=False), "DKIM"), ["ignore"])

    def test_revoked_key(self):
        d = healthy(**{"google._domainkey.example.com|TXT": ["v=DKIM1; k=rsa; p="]})
        self.assertEqual(levels(run(d, blocklists=False), "DKIM"), ["worth_fixing"])

    def test_1024_bit_key_is_fine(self):
        d = healthy(**{"google._domainkey.example.com|TXT": ["v=DKIM1; k=rsa; p=" + "A" * 216]})  # 162 bytes
        self.assertEqual(levels(run(d, blocklists=False), "DKIM"), ["ignore"])


class BlocklistTests(unittest.TestCase):
    def test_not_listed_is_clean(self):
        f = run(healthy())
        self.assertEqual(sorted(set(levels(f, "Spamhaus DBL"))), ["ignore"])

    def test_dbl_spam_is_fix_now(self):
        f = run(healthy(**{"example.com.dbl.spamhaus.org|A": ["127.0.1.2"]}))
        self.assertEqual(levels(f, "Spamhaus DBL"), ["fix_now"])

    def test_dbl_error_codes_are_never_a_listing(self):
        for code in ("127.255.255.254", "127.255.255.255", "127.255.255.252", "127.0.1.255"):
            f = run(healthy(**{"example.com.dbl.spamhaus.org|A": [code]}))
            self.assertEqual(levels(f, "Spamhaus DBL"), ["not_checked"], code)

    def test_surbl_blocked_is_not_a_listing(self):
        f = run(healthy(**{"example.com.multi.surbl.org|A": ["127.0.0.1"]}))
        self.assertEqual(levels(f, "SURBL multi"), ["not_checked"])

    def test_surbl_abuse_only_is_worth_fixing(self):
        f = run(healthy(**{"example.com.multi.surbl.org|A": ["127.0.0.64"]}))
        self.assertEqual(levels(f, "SURBL multi"), ["worth_fixing"])

    def test_surbl_combined_bits_use_worst(self):
        f = run(healthy(**{"example.com.multi.surbl.org|A": ["127.0.0.80"]}))  # 16 malware + 64 abuse
        self.assertEqual(levels(f, "SURBL multi"), ["fix_now"])

    def test_surbl_disposable_only_is_ignorable(self):
        f = run(healthy(**{"example.com.multi.surbl.org|A": ["127.0.0.4"]}))
        self.assertEqual(levels(f, "SURBL multi"), ["ignore"])

    def test_uribl_blocked_is_not_a_listing(self):
        f = run(healthy(**{"example.com.multi.uribl.com|A": ["127.0.0.1"]}))
        self.assertEqual(levels(f, "URIBL multi"), ["not_checked"])

    def test_uribl_black_is_fix_now_and_red_is_ignorable(self):
        f = run(healthy(**{"example.com.multi.uribl.com|A": ["127.0.0.2"]}))
        self.assertEqual(levels(f, "URIBL multi"), ["fix_now"])
        f = run(healthy(**{"example.com.multi.uribl.com|A": ["127.0.0.8"]}))
        self.assertEqual(levels(f, "URIBL multi"), ["ignore"])

    def test_lookup_failure_is_not_checked(self):
        f = run(healthy(**{"example.com.dbl.spamhaus.org|A": "ERROR"}))
        self.assertEqual(levels(f, "Spamhaus DBL"), ["not_checked"])

    def test_public_resolver_skips_blocklists(self):
        res = C.FixtureResolver(healthy())
        res.uses_public_resolver = True
        f = C.check_domain(res, "example.com")["findings"]
        self.assertEqual(levels(f, "Blocklists"), ["not_checked"])
        self.assertEqual(levels(f, "Spamhaus DBL"), [])

    def test_real_resolver_flags_public_servers(self):
        self.assertTrue(C.DnsResolver(["8.8.8.8"]).uses_public_resolver)
        self.assertTrue(C.DnsResolver(["1.1.1.1"]).uses_public_resolver)
        self.assertFalse(C.DnsResolver(["192.168.1.1"]).uses_public_resolver)


class ResolverSanityTests(unittest.TestCase):
    def test_working_resolver_passes(self):
        self.assertIsNone(C.resolver_problem(C.FixtureResolver({"example.com|A": ["93.184.216.34"]})))

    def test_resolver_that_denies_example_com_is_rejected(self):
        self.assertIn("not giving real answers", C.resolver_problem(C.FixtureResolver({})))

    def test_failing_resolver_is_rejected(self):
        self.assertIn("failing", C.resolver_problem(C.FixtureResolver({"example.com|A": "ERROR"})))

    def test_cli_stops_instead_of_reporting_false_nxdomain(self):
        orig = C.DnsResolver.query
        C.DnsResolver.query = lambda self, n, t: {"rcode": 3, "records": [], "error": None}
        try:
            self.assertEqual(C.main(["example.org", "--resolver", "192.0.2.1"]), 2)
        finally:
            C.DnsResolver.query = orig


class DomainLevelTests(unittest.TestCase):
    def test_nxdomain_stops_early(self):
        res = C.FixtureResolver({"gone.example|TXT": "NXDOMAIN"})
        f = C.check_domain(res, "gone.example")["findings"]
        self.assertEqual([x["check"] for x in f], ["Domain"])
        self.assertEqual(f[0]["level"], "fix_now")

    def test_dns_error_on_domain_is_not_nxdomain(self):
        res = C.FixtureResolver({"flaky.example|TXT": "ERROR"})
        f = C.check_domain(res, "flaky.example", blocklists=False)["findings"]
        self.assertNotIn("Domain", [x["check"] for x in f])
        self.assertEqual([x["level"] for x in f if x["check"] == "SPF"], ["not_checked"])

    def test_report_groups_by_level(self):
        d = healthy()
        del d["_dmarc.example.com|TXT"]
        res = C.FixtureResolver(d)
        md = C.render_markdown([C.check_domain(res, "example.com", blocklists=False)], "2026-11-17")
        self.assertIn("**Fix now**", md)
        self.assertIn("DMARC: No DMARC record", md)
        self.assertIn("| example.com | 1 |", md)


if __name__ == "__main__":
    unittest.main()
