"""python -m unittest -v      (needs data/items.json, data/visible_key.json, data/score.py)"""
import json
import os
import subprocess
import sys
import tempfile
import threading
import unittest
from collections import Counter
from http.server import BaseHTTPRequestHandler, HTTPServer

from eval.common import ROOT, load_data
from eval.mocks import GoldBackend
from rotasolve.extract import parse_output
from rotasolve.llm import LLM, BudgetExceeded, ItemBudget
from rotasolve.parse import parse_item
from rotasolve.pipeline import Config, solve_item
from rotasolve.schema import canon

ITEMS, KEY, SC = load_data()


class Parsing(unittest.TestCase):
    def test_every_header_parses(self):
        for it in ITEMS:
            r = parse_item(it)
            self.assertEqual(len(r.names), it["n_staff"])
            self.assertEqual(len(r.stations), it["n_stations"])
            self.assertEqual(len(r.holders), it["n_stations"])
            self.assertEqual(r.blocks[0], "07:00")

    def test_canon_is_strict_and_exact(self):
        r = parse_item(ITEMS[0])
        n0, n1 = r.names[0], r.names[1]
        self.assertEqual(canon("at", [n0.lower(), "7:00"], r), ("AT", n0, "07:00"))
        self.assertIsNone(canon("AT", ["Nobody", "07:00"], r))
        self.assertIsNone(canon("AT", [n0, "08:00"], r))
        self.assertIsNone(canon("BEFORE", [n0, n0], r))
        self.assertIsNone(canon("BEFORE", [n0], r))
        a = canon("BETWEEN", [n0, r.names[3], r.names[2]], r)
        b = canon("BETWEEN", [n0, r.names[2], r.names[3]], r)
        self.assertEqual(a, b)

    def test_swapped_argument_order_is_repaired(self):
        r = parse_item(ITEMS[0])
        n0, st, tm = r.names[0], r.stations[0], r.blocks[1]
        self.assertEqual(canon("STATION_BEFORE", [n0, st], r), ("STATION_BEFORE", st, n0))
        self.assertEqual(canon("AT", [tm, n0], r), ("AT", n0, tm))
        self.assertEqual(canon("STATION", [st, n0], r), ("STATION", n0, st))
        self.assertIsNone(canon("AT", [n0, st], r))      # genuinely wrong types stay rejected

    def test_output_parser_is_forgiving(self):
        r = parse_item(ITEMS[0])
        n0 = r.names[0]
        txt = f"Sure!\nL1: NONE\nl2 - AT({n0}, 09:00)\nL3: garbage(\nL4: AT(Nobody, 09:00)\n"
        res = parse_output(txt, r, {0, 1, 2, 3})
        self.assertEqual(res, {0: None, 1: ("AT", n0, "09:00")})   # L3/L4 cast no vote


class Routing(unittest.TestCase):
    def test_every_real_constraint_lands_in_a_section_that_allows_it(self):
        from eval.gold import gold_constraints
        from rotasolve.route import ALLOWED, route
        n = 0
        for it in ITEMS:
            r = parse_item(it)
            for i, c in gold_constraints(r).items():
                self.assertIn(c[0], ALLOWED[route(r.lines[i], r)], r.lines[i])
                n += 1
        self.assertGreater(n, 500)

    def test_plans_fit_budgets(self):
        from rotasolve.pipeline import FLAT_PLANS, MULTIVIEW_PLANS, ROUTED_PLANS
        for plans in (ROUTED_PLANS, FLAT_PLANS, MULTIVIEW_PLANS):
            for name, cap in (("1x", 1), ("3x", 3), ("10x", 10)):
                self.assertTrue(1 <= len(plans[name]) <= cap)


class Voting(unittest.TestCase):
    def test_acceptance_threshold(self):
        from rotasolve.pipeline import consensus
        c = ("AT", "A", "07:00")
        votes = {0: [(c, 1.0), (None, 1.0), (None, 1.0)], 1: [(None, 1.0)] * 3, 2: [(c, 1.0), (c, 1.0), (None, 1.0)]}
        maj, _ = consensus(votes, 0.5)
        low, _ = consensus(votes, 0.33)
        self.assertEqual(set(maj), {2})            # majority: 2 of 3 needed
        self.assertEqual(set(low), {0, 2})         # lenient: one of 3 is enough
        self.assertNotIn(1, low)                   # an all-NONE line stays NONE


class Budget(unittest.TestCase):
    def test_guard_blocks_extra_calls(self):
        llm = LLM(lambda i, m: "")
        b = ItemBudget("x", 2)
        llm.complete(b, []); llm.complete(b, [])
        with self.assertRaises(BudgetExceeded):
            llm.complete(b, [])

    def test_backend_error_still_counts(self):
        def boom(i, m): raise RuntimeError("net")
        b = ItemBudget("x", 1)
        self.assertEqual(LLM(boom).complete(b, []), "")
        self.assertEqual(b.used, 1)

    def test_all_budgets_respected_with_gold_reader(self):
        for name, cap in (("1x", 1), ("3x", 3), ("10x", 10)):
            llm = LLM(GoldBackend(ITEMS))
            for it in ITEMS[:12]:
                _, info = solve_item(it, name, llm, Config())
                self.assertTrue(1 <= info["calls"] <= cap, (name, info))


class EndToEnd(unittest.TestCase):
    def test_gold_reader_scores_perfectly(self):
        llm = LLM(GoldBackend(ITEMS))
        ans = {it["id"]: solve_item(it, "1x", llm)[0] for it in ITEMS}
        res = SC.score(KEY, ans, ITEMS)
        self.assertEqual(res["macro_exact_match"], 1.0)


class PromptFlags(unittest.TestCase):
    def test_examples_can_be_omitted(self):
        from rotasolve.prompt import build_messages
        r = parse_item(ITEMS[0])
        with_ex = build_messages(r, list(range(len(r.lines))), examples=True)[1]["content"]
        no_ex = build_messages(r, list(range(len(r.lines))), examples=False)[1]["content"]
        self.assertIn("Worked examples", with_ex)
        self.assertNotIn("Worked examples", no_ex)
        self.assertLess(len(no_ex), len(with_ex))


class Launcher(unittest.TestCase):
    def test_run_shebang_is_lf_python3(self):
        raw = open(os.path.join(ROOT, "run"), "rb").read()
        self.assertTrue(raw.startswith(b"#!/usr/bin/env python3\n"))
        self.assertNotIn(b"\r", raw.split(b"\n", 1)[0])


class HttpContract(unittest.TestCase):
    """Real OpenAI client -> local fake endpoint: headers, sampling, budget at the 'proxy'."""

    def test_wire_format_and_budget(self):
        gold = GoldBackend(ITEMS)
        seen = []

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a): pass

            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                iid = self.headers.get("X-Item-Id")
                seen.append((iid, body))
                text = gold(iid, body["messages"]) if iid else ""
                out = json.dumps({"id": "x", "object": "chat.completion", "created": 0, "model": body["model"],
                                  "choices": [{"index": 0, "finish_reason": "stop",
                                               "message": {"role": "assistant", "content": text}}]}).encode()
                self.send_response(200); self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(out))); self.end_headers(); self.wfile.write(out)

        srv = HTTPServer(("127.0.0.1", 0), H)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        with tempfile.TemporaryDirectory() as d:
            sub = os.path.join(d, "items.json"); out = os.path.join(d, "answers.json")
            json.dump(ITEMS[:6], open(sub, "w"))
            env = {k: v for k, v in os.environ.items() if "KEY" not in k and "BASE_URL" not in k}
            env.update(OPENROUTER_BASE_URL=f"http://127.0.0.1:{srv.server_port}/v1",
                       OPENROUTER_API_KEY="test", MODEL="ibm-granite/granite-4.2-8b")
            p = subprocess.run([sys.executable, os.path.join(ROOT, "run"), sub, "--budget", "3x", "--out", out],
                               env=env, capture_output=True, text=True)
            srv.shutdown()
            self.assertEqual(p.returncode, 0, p.stderr)
            answers = json.load(open(out))
        self.assertEqual(set(answers), {it["id"] for it in ITEMS[:6]})
        per_item = Counter(i for i, _ in seen)
        self.assertEqual(set(per_item), set(answers))            # every item got >= 1 call
        self.assertTrue(all(1 <= n <= 3 for n in per_item.values()), per_item)
        for iid, body in seen:
            self.assertTrue(iid)
            self.assertEqual(body["temperature"], 1.0)
            self.assertEqual(body["top_p"], 0.95)
            self.assertEqual(body["reasoning"], {"enabled": False})
            self.assertEqual(body["model"], "ibm-granite/granite-4.2-8b")


if __name__ == "__main__":
    unittest.main()
