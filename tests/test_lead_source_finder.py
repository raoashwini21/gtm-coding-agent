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


class AskMode(unittest.TestCase):
    def feed(self, lines):
        it = iter(lines)
        said = []
        def read(prompt=""):
            try:
                return next(it)
            except StopIteration:
                raise EOFError
        return read, said.append, said

    def test_answers_match_what_was_typed(self):
        read, say, _ = self.feed(["1", "1,2", "3", "2", "1", "2"])
        a = R.ask_answers(read, say)
        self.assertEqual(a, dict(audience="business", footprints=["linkedin", "map"], customers="none",
                                 narrowness="niche", volume="small_once", region="other", sensitive=False))
        R.recommend(a)  # must be accepted as valid

    def test_bad_input_is_asked_again(self):
        read, say, said = self.feed(["9", "abc", "", "2", "1", "1", "1", "1", "1", "1"])
        a = R.ask_answers(read, say)
        self.assertEqual(a["audience"], "people")
        self.assertGreaterEqual(sum("Please type a number" in s for s in said), 3)

    def test_multi_pick_rejects_out_of_range_and_dedupes(self):
        read, say, _ = self.feed(["1", "7", "2,2,2", "1", "1", "1", "1"])
        a = R.ask_answers(read, say)
        self.assertEqual(a["footprints"], ["map"])

    def test_sensitive_question_only_when_topic_chosen(self):
        read, say, said = self.feed(["2", "4", "3", "3", "1", "1", "1"])
        a = R.ask_answers(read, say)
        self.assertTrue(a["sensitive"])
        self.assertTrue(any("sensitive" in s for s in said))
        read, say, said = self.feed(["1", "1", "3", "1", "1", "2"])
        a = R.ask_answers(read, say)
        self.assertFalse(a["sensitive"])
        self.assertFalse(any("sensitive" in s for s in said))

    def test_every_option_is_a_valid_answer(self):
        for q in R.QUESTIONS:
            for _, val in q["options"]:
                if q["key"] in R.ENUMS:
                    self.assertIn(val, R.ENUMS[q["key"]])
                if q["key"] == "footprints":
                    self.assertIn(val, R.FOOTPRINTS)
        self.assertEqual({v for _, v in R.QUESTIONS[1]["options"]}, R.FOOTPRINTS)

    def test_main_ask_mode_and_stopping(self):
        import io, contextlib
        read, _, _ = self.feed(["1", "2", "3", "2", "1", "2"])
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = R.main([], read=read)
        self.assertEqual(code, 0)
        self.assertIn("Maps, directories", out.getvalue())
        read, _, _ = self.feed(["1", "2"])  # runs out of input halfway
        err = io.StringIO()
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(err):
            code = R.main([], read=read)
        self.assertEqual(code, 130)
        self.assertIn("Nothing was saved", err.getvalue())

    def test_answers_and_ask_together_is_refused(self):
        import io, contextlib
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            R.main(["--answers", "x.json", "--ask"])


class Robustness(unittest.TestCase):
    def test_malformed_answers_raise_value_error_never_crash(self):
        good = ans()
        bad = [[], "x", None, 5, {}, {"audience": ["a"]},
               dict(good, footprints=[["x"]]), dict(good, footprints=[{"a": 1}]),
               dict(good, customers={"a": 1}), dict(good, footprints="linkedin"),
               dict(good, sensitive="yes")]
        for b in bad:
            with self.subTest(str(b)[:40]):
                with self.assertRaises(ValueError):
                    R.recommend(b)

    def test_bad_answers_file_exits_2_with_message(self):
        import io, contextlib, tempfile, os
        for content in ("[]", '"x"', "null", "5", "{}", "{bad json", ""):
            with self.subTest(content), tempfile.TemporaryDirectory() as d:
                f = os.path.join(d, "a.json")
                open(f, "w").write(content)
                err = io.StringIO()
                with contextlib.redirect_stderr(err):
                    code = R.main(["--answers", f])
                self.assertEqual(code, 2)
                self.assertIn("Cannot", err.getvalue())
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            self.assertEqual(R.main(["--answers", "/no/such/file.json"]), 2)

    def test_sensitive_topic_changes_first_step_and_hides_scraper_facts(self):
        a = SCENARIOS[0][1]
        r = R.recommend(a)
        md = R.render(a, r)
        self.assertIn("Do not build a list of individuals", md)
        self.assertNotIn("community-built actors", md)
        self.assertIn("left out on purpose", md)
        plain = dict(a, sensitive=False)
        md2 = R.render(plain, R.recommend(plain))
        self.assertIn("community-built actors", md2)
        self.assertNotIn("Do not build a list of individuals", md2)

    def test_json_mode_keeps_stdout_pure_json(self):
        import io, contextlib
        it = iter(["1", "1", "3", "1", "1", "2"])
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = R.main(["--format", "json"], read=lambda p="": next(it))
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out.getvalue())["routes"], [1])
        self.assertIn("Who do you sell to", err.getvalue())

    def test_missing_facts_file_gives_message_not_traceback(self):
        import io, contextlib
        orig = R.HERE
        try:
            R.HERE = Path("/no/such/dir")
            it = iter(["1", "1", "3", "1", "1", "2"])
            err = io.StringIO()
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(err):
                code = R.main([], read=lambda p="": next(it))
            self.assertEqual(code, 2)
            self.assertIn("facts.json", err.getvalue())
        finally:
            R.HERE = orig

    def test_closed_pipe_is_silent_even_with_tiny_output_buffers(self):
        """Piping into `head` must not print Python errors. macOS pipes use small buffers, so force one."""
        import subprocess
        hack = ("import sys, io, runpy\n"
                "sys.stdout = io.TextIOWrapper(io.BufferedWriter(io.FileIO(1, 'w', closefd=False), 512), encoding='utf-8')\n"
                "sys.argv = ['recommend.py']\n"
                "runpy.run_path(%r, run_name='__main__')\n" % str(SKILL_DIR / "recommend.py"))
        for _ in range(3):
            p = subprocess.Popen([sys.executable, "-c", hack], stdin=subprocess.PIPE,
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            p.stdout.close()  # the reader has gone away before anything is written
            try:
                p.stdin.write("1\n2\n3\n2\n1\n2\n")
                p.stdin.close()
            except BrokenPipeError:
                pass
            err = p.stderr.read()
            p.wait(timeout=30)
            self.assertEqual(p.returncode, 0, err)
            self.assertNotIn("Exception ignored", err)
            self.assertNotIn("Traceback", err)
            self.assertNotIn("BrokenPipe", err)



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
