"""Offline tests for skills/lead-source-finder. No network. All buyers below are made up."""
import json
import re
import sys
import unittest
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parents[1] / "skills" / "lead-source-finder"
sys.path.insert(0, str(SKILL_DIR))

import recommend as R  # noqa: E402


def ans(**kw):
    base = dict(audience="business", footprints=["linkedin"], customers="none",
                narrowness="broad", volume="small_once", region="other", sensitive=False)
    base.update(kw)
    return base


# (name, answers, expected first route, routes that must be present, routes that must be absent)
SCENARIOS = [
    ("mental-offloading app users (people, found from posts)",
     ans(audience="people", footprints=["topic"], narrowness="very_narrow", region="eu_uk", sensitive=True),
     6, {6}, {1, 2}),
    ("real estate company, has 5+ happy customers",
     ans(footprints=["linkedin", "map"], customers="5plus", narrowness="niche"),
     2, {2}, set()),
    ("real estate company, no customers yet",
     ans(footprints=["linkedin", "map"], customers="none", narrowness="niche"),
     4, {4, 1}, {2}),
    ("HR software for mid-size companies, broad, thousands a month",
     ans(footprints=["linkedin"], narrowness="broad", volume="large_ongoing"),
     1, {1}, {2, 6}),
    ("local dental clinics, listed on maps",
     ans(footprints=["map"], narrowness="niche"),
     4, {4}, {1, 2, 6}),
    ("sales-training company, buyers are teams hiring SDRs",
     ans(footprints=["tool_or_hiring"], narrowness="niche"),
     5, {5}, {2}),
    ("software for HVAC contractors, their site uses telling words",
     ans(footprints=["website_words"], narrowness="very_narrow"),
     3, {3}, {2}),
    ("RevOps consultants who write about a topic, few customers",
     ans(footprints=["topic", "linkedin"], customers="few", narrowness="very_narrow", region="eu_uk"),
     6, {6}, {2}),
    ("agencies listed in a directory, EU",
     ans(footprints=["directory"], narrowness="niche", region="eu_uk"),
     4, {4}, {6}),
    ("vague answers from someone selling to people",
     ans(audience="people", footprints=["linkedin"], narrowness="broad"),
     6, {6}, set()),
]


class Scenarios(unittest.TestCase):
    def test_ten_scenarios(self):
        self.assertEqual(len(SCENARIOS), 10)
        for name, a, first, present, absent in SCENARIOS:
            with self.subTest(name):
                r = R.recommend(a)
                self.assertEqual(r["routes"][0], first, r)
                self.assertTrue(present <= set(r["routes"]), r)
                self.assertFalse(absent & set(r["routes"]), r)
                self.assertLessEqual(len(r["routes"]), 2)
                self.assertIn("Contact data is out of scope", r["note"])

    def test_vague_is_flagged(self):
        r = R.recommend(SCENARIOS[-1][1])
        self.assertEqual(r["status"], "vague")

    def test_lookalikes_need_customers(self):
        for c in ("few", "none"):
            r = R.recommend(ans(footprints=["linkedin", "website_words"], customers=c, narrowness="niche"))
            self.assertNotIn(2, r["routes"])
            self.assertIn(2, r["skipped"])

    def test_route6_always_warns_about_weak_signal_and_linkedin(self):
        r = R.recommend(SCENARIOS[0][1])
        text = " ".join(r["warnings"])
        self.assertIn("weak buying signal", text)
        self.assertIn("Section 8.2", text)

    def test_gdpr_only_for_eu_uk_scraping_routes(self):
        eu = R.recommend(ans(footprints=["directory"], narrowness="niche", region="eu_uk"))
        us = R.recommend(ans(footprints=["directory"], narrowness="niche", region="other"))
        self.assertTrue(any("EU/UK" in w for w in eu["warnings"]))
        self.assertFalse(any("EU/UK" in w for w in us["warnings"]))
        db = R.recommend(ans(footprints=["linkedin"], region="eu_uk"))
        self.assertFalse(any("EU/UK" in w for w in db["warnings"]))

    def test_sensitive_topic_warning(self):
        r = R.recommend(SCENARIOS[0][1])
        self.assertTrue(any("special-category" in w for w in r["warnings"]))
        plain = R.recommend(ans(footprints=["topic"], narrowness="very_narrow"))
        self.assertFalse(any("special-category" in w for w in plain["warnings"]))

    def test_people_audience_gets_privacy_note(self):
        r = R.recommend(SCENARIOS[0][1])
        self.assertTrue(any("individuals" in w for w in r["warnings"]))

    def test_bad_answers_are_rejected_not_guessed(self):
        for bad in (ans(customers="lots"), ans(footprints=[]), ans(footprints=["tiktok"]),
                    ans(region="mars"), ans(audience="aliens")):
            with self.assertRaises(ValueError):
                R.recommend(bad)

    def test_render_has_steps_and_sources(self):
        a = SCENARIOS[1][1]
        md = R.render(a, R.recommend(a))
        for needle in ("Why it fits", "What it can't find", "First step", "[source](", "2026-11-25"):
            self.assertIn(needle, md)


class FactSheet(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = json.loads((SKILL_DIR / "facts.json").read_text())

    def test_every_fact_has_source_date_and_how(self):
        for f in self.data["facts"]:
            with self.subTest(f["id"]):
                srcs = [f["source"]] if isinstance(f["source"], str) else f["source"]
                self.assertTrue(srcs)
                for s in srcs:
                    self.assertTrue(s.startswith("https://"), s)
                self.assertRegex(f["last_checked"], r"^\d{4}-\d{2}-\d{2}$")
                self.assertIn(f["how"], ("page", "search excerpt"))
                self.assertTrue(f["claim"].strip())

    def test_ids_unique(self):
        ids = [f["id"] for f in self.data["facts"]]
        self.assertEqual(len(ids), len(set(ids)))

    def test_routes_only_reference_real_facts(self):
        ids = {f["id"] for f in self.data["facts"]}
        for r, info in R.ROUTES.items():
            for fid in info["facts"]:
                self.assertIn(fid, ids, f"route {r} cites missing fact {fid}")

    def test_warnings_cite_facts_that_exist(self):
        ids = {f["id"] for f in self.data["facts"]}
        for w in (R.WARN_LINKEDIN, R.WARN_GDPR, R.WARN_SENSITIVE):
            for fid in re.findall(r"\b(?:linkedin|gdpr)-\d\b", w):
                self.assertIn(fid, ids)

    def test_no_personal_data_in_repo_files(self):
        for p in SKILL_DIR.glob("*"):
            if p.suffix in (".json", ".md", ".py"):
                text = p.read_text()
                self.assertIsNone(re.search(r"[\w.+-]+@[\w-]+\.[\w.]+", text), f"email-like text in {p.name}")


class Freshness(unittest.TestCase):
    def test_fresh_and_stale(self):
        import check_freshness as F
        facts = [{"id": "a", "last_checked": "2026-11-25"}, {"id": "b", "last_checked": "2026-08-01"},
                 {"id": "c", "last_checked": "not-a-date"}]
        out = F.stale_facts(facts, F.dt.date(2026, 12, 20), 60)
        self.assertEqual([i for i, _, _ in out], ["b", "c"])

    def test_exit_codes(self):
        import check_freshness as F
        self.assertEqual(F.main(["--today", "2026-12-01"]), 0)
        self.assertEqual(F.main(["--today", "2027-03-01"]), 1)
        self.assertEqual(F.main(["--today", "bad"]), 2)


if __name__ == "__main__":
    unittest.main()
