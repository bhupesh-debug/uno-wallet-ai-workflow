"""Test suite. Prints a runtime 'N passed' line — quote that line,
never a count of check() call sites (checks inside loops run many times).
Run: python -m tests.test_all  (from the project root)
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np
import pandas as pd

from src.data_gen import KPI_COLUMNS, WEEKS, generate
from src.evaluate import compute_ground_truth, evaluate_memo
from src.llm_client import MockLLMAdapter, RealAPIAdapter
from src.time_study import (MANUAL_TASKS, manual_baseline_minutes,
                            time_saved_report)
from src.workflow import (build_prompt, corrupt_field, parse_structured,
                          review_gate, run_workflow)

PASSED = 0
FAILED = 0


def check(name, cond):
    global PASSED, FAILED
    if cond:
        PASSED += 1
    else:
        FAILED += 1
        print(f"FAIL: {name}")


def main():
    global PASSED, FAILED
    metrics_df, feedback_df = generate()
    client = MockLLMAdapter()

    # --- Data generation ---
    check("8 weeks", len(metrics_df) == 8 and list(metrics_df["week"]) == WEEKS)
    check("9 KPI columns", all(c in metrics_df.columns for c in KPI_COLUMNS))
    check("3 feedback rows per week",
          all((feedback_df["week"] == w).sum() == 3 for w in WEEKS))
    check("seed reproducible", generate()[0].equals(metrics_df))
    check("different seed differs", not generate(seed=7)[0].equals(metrics_df))
    check("W03 rec_accuracy missing",
          pd.isna(metrics_df.loc[metrics_df["week"] == "2026-W03", "rec_accuracy_pct"].iloc[0]))
    check("W06 transactions negative",
          metrics_df.loc[metrics_df["week"] == "2026-W06", "transactions"].iloc[0] == -50)
    check("W07 rec_accuracy 87.0",
          metrics_df.loc[metrics_df["week"] == "2026-W07", "rec_accuracy_pct"].iloc[0] == 87.0)
    w04 = metrics_df.loc[metrics_df["week"] == "2026-W04"].iloc[0]
    w05 = metrics_df.loc[metrics_df["week"] == "2026-W05"].iloc[0]
    ch_s = (w05["signups"] - w04["signups"]) / w04["signups"] * 100
    ch_t = (w05["transactions"] - w04["transactions"]) / w04["transactions"] * 100
    check("W05 signups/transactions near-tie (within 0.5pp)", abs(ch_s - ch_t) <= 0.5)
    check("all non-fault values non-negative except W06",
          all(v >= 0 for _, r in metrics_df.iterrows() for k, v in r.items()
              if k in KPI_COLUMNS and not pd.isna(v) and r["week"] != "2026-W06")
          and (metrics_df.loc[metrics_df["week"] == "2026-W06", "transactions"].iloc[0] < 0))

    # --- Prompt building ---
    row = metrics_df.iloc[7]
    prior = metrics_df.iloc[6]
    fb = feedback_df.loc[feedback_df["week"] == "2026-W08"]
    prompt = build_prompt(row, prior, fb)
    check("prompt has 9 metric lines",
          sum(1 for ln in prompt.splitlines() if ln.startswith("- ") and "(prior:" in ln) == 9)
    check("prompt carries feedback lines", "FEEDBACK" in prompt)
    check("prompt never pre-computes deltas", "%" not in prompt.split("METRICS")[1].split("USER FEEDBACK")[0]
          .replace("(prior:", ""))

    # --- Mock adapter: full workflow over all 8 weeks ---
    for week in WEEKS:
        idx = metrics_df.index[metrics_df["week"] == week][0]
        wr, pr = metrics_df.iloc[idx], metrics_df.iloc[idx - 1] if idx > 0 else None
        fb_w = feedback_df.loc[feedback_df["week"] == week]
        memo, _ = run_workflow(week, metrics_df, feedback_df, client)
        truth = compute_ground_truth(wr, pr, fb_w)
        ev = evaluate_memo(parse_structured(memo), truth)
        gate = review_gate(memo, wr, pr, fb_w)
        check(f"{week}: memo has structured block", "##STRUCTURED##" in memo)
        check(f"{week}: field accuracy >= 95%", ev["field_accuracy"] >= 0.95)
        check(f"{week}: insight match", ev["insight_match"])
        check(f"{week}: flags correct", ev["flags_correct"])
        check(f"{week}: review gate approves", gate["decision"] == "approve")

    # Edge-case behaviour, spelled out.
    memo_w03, _ = run_workflow("2026-W03", metrics_df, feedback_df, client)
    f03 = parse_structured(memo_w03)
    check("W03: rec_accuracy stays n/a (never invented)", f03.get("rec_accuracy_pct") == "n/a")
    check("W03: flags include MISSING_DATA", "MISSING_DATA" in f03.get("flags", ""))
    memo_w06, _ = run_workflow("2026-W06", metrics_df, feedback_df, client)
    f06 = parse_structured(memo_w06)
    check("W06: transactions excluded (n/a, not -50)", f06.get("transactions") == "n/a")
    check("W06: flags include DATA_QUALITY", "DATA_QUALITY" in f06.get("flags", ""))
    check("W06: top mover is not transactions", f06.get("top_mover") != "transactions")
    memo_w07, _ = run_workflow("2026-W07", metrics_df, feedback_df, client)
    f07 = parse_structured(memo_w07)
    check("W07: flags include RISK_ACCURACY_LOW", "RISK_ACCURACY_LOW" in f07.get("flags", ""))
    check("W07: memo recommends investigating misses",
          "Investigate recommendation misses" in memo_w07)
    memo_w05, _ = run_workflow("2026-W05", metrics_df, feedback_df, client)
    f05 = parse_structured(memo_w05)
    check("W05: top mover is one of the tied metrics",
          f05.get("top_mover") in ("signups", "transactions"))
    memo_w01, _ = run_workflow("2026-W01", metrics_df, feedback_df, client)
    f01 = parse_structured(memo_w01)
    check("W01: no prior week -> changes n/a",
          all(f01.get(f"{k}_change_pct") == "n/a" for k in KPI_COLUMNS))
    check("W01: top mover n/a", f01.get("top_mover") == "n/a")

    # --- Review gate: seeded errors must be caught ---
    memo_clean, _ = run_workflow("2026-W08", metrics_df, feedback_df, client)
    idx = metrics_df.index[metrics_df["week"] == "2026-W08"][0]
    wr, pr = metrics_df.iloc[idx], metrics_df.iloc[idx - 1]
    fb_w = feedback_df.loc[feedback_df["week"] == "2026-W08"]
    gate_clean = review_gate(memo_clean, wr, pr, fb_w)
    check("clean memo: gate finds 0 issues", len(gate_clean["issues"]) == 0)
    corrupted = corrupt_field(memo_clean, "signups", "99999")
    gate_c1 = review_gate(corrupted, wr, pr, fb_w)
    check("corrupted value: gate flags it",
          any("signups" in i for i in gate_c1["issues"]) and gate_c1["decision"] == "needs_fix")
    corrupted2 = corrupt_field(memo_clean, "transactions_change_pct", "42.0")
    gate_c2 = review_gate(corrupted2, wr, pr, fb_w)
    check("corrupted % change: gate flags it",
          any("transactions_change_pct" in i for i in gate_c2["issues"]))
    top = parse_structured(memo_clean).get("top_mover")
    wrong_top = "gmv_usd" if top != "gmv_usd" else "signups"
    corrupted3 = corrupt_field(memo_clean, "top_mover", wrong_top)
    gate_c3 = review_gate(corrupted3, wr, pr, fb_w)
    check("corrupted top mover: gate flags it",
          gate_c3["decision"] == "needs_fix"
          and any("top_mover" in i for i in gate_c3["issues"]))
    missing_block = memo_clean.split("##STRUCTURED##")[0]
    gate_nb = review_gate(missing_block, wr, pr, fb_w)
    check("memo without structured block: gate rejects",
          gate_nb["decision"] == "needs_fix" and len(gate_nb["issues"]) > 0)
    check("unknown week raises", _raises_value_error("2026-W99"))

    # --- Evaluation harness: ground truth independence ---
    toy_cur = pd.Series({"week": "2026-W09", **{k: 100.0 for k in KPI_COLUMNS}})
    toy_prior = pd.Series({"week": "2026-W08", **{k: 80.0 for k in KPI_COLUMNS}})
    toy_fb = pd.DataFrame([{"week": "2026-W09", "theme": "love_it", "text": "great"},
                           {"week": "2026-W09", "theme": "love_it", "text": "great"},
                           {"week": "2026-W09", "theme": "slow_app", "text": "slow"}])
    gt = compute_ground_truth(toy_cur, toy_prior, toy_fb)
    check("toy ground truth: all changes +25%", all(abs(gt["changes"][k] - 25.0) < 1e-9 for k in KPI_COLUMNS))
    check("toy ground truth: top movers are all tied", set(gt["top_movers"]) == set(KPI_COLUMNS))
    check("toy ground truth: top theme love_it", gt["top_feedback_theme"] == "love_it")
    check("toy ground truth: no flags", gt["flags"] == [])
    fields = {"top_mover": "signups", "flags": "none", "top_feedback_theme": "love_it"}
    for k in KPI_COLUMNS:
        fields[k] = "100"
        fields[f"{k}_change_pct"] = "25.0"
    ev_toy = evaluate_memo(fields, gt)
    check("toy memo: perfect field accuracy", ev_toy["field_accuracy"] == 1.0)
    bad = dict(fields)
    bad["signups"] = "101"
    ev_bad = evaluate_memo(bad, gt)
    check("toy memo: one wrong field -> 1 error case",
          len(ev_bad["errors"]) == 1 and ev_bad["errors"][0]["field"] == "signups")

    # --- Real API adapter: key handling (no network touched) ---
    os.environ.pop("UNO_LLM_API_KEY", None)
    adapter = RealAPIAdapter()
    try:
        adapter.generate("test prompt")
        check("real adapter without key raises", False)
    except RuntimeError as e:
        check("real adapter without key raises", "UNO_LLM_API_KEY" in str(e))
    os.environ["UNO_LLM_API_KEY"] = "sk-test-DO-NOT-USE"
    try:
        url, headers, body = adapter.build_request("test prompt")
        check("real adapter builds OpenAI-compatible URL", url.endswith("/chat/completions"))
        check("real adapter sends bearer auth", headers["Authorization"].startswith("Bearer sk-test"))
        check("real adapter body names a model", b"\"model\"" in body)
        check("real adapter body carries the prompt", b"test prompt" in body)
    finally:
        os.environ.pop("UNO_LLM_API_KEY", None)
    check("no API key in src/ or run_all.py after tests",
          "sk-test-DO-NOT-USE" not in "".join(
              p.read_text(encoding="utf-8", errors="ignore")
              for p in list(Path(__file__).resolve().parents[1].glob("src/*.py"))
              + [Path(__file__).resolve().parents[1] / "run_all.py"]))

    # --- Time study ---
    check("manual baseline is 105 minutes", manual_baseline_minutes() == 105)
    check("manual tasks sum to baseline",
          sum(m for _, m in MANUAL_TASKS) == manual_baseline_minutes())
    rep = time_saved_report(0.5)
    check("time saved positive", rep["saved_minutes_per_week"] > 90)
    check("time saved ~1.5h/week", 1.4 < rep["saved_hours_per_week"] < 1.8)
    check("yearly saving > 70h", rep["saved_hours_per_year_52w"] > 70)

    print(f"{PASSED} passed, {FAILED} failed")
    return 1 if FAILED else 0


def _raises_value_error(week):
    try:
        run_workflow(week, *generate(), MockLLMAdapter())
        return False
    except ValueError:
        return True


if __name__ == "__main__":
    raise SystemExit(main())
