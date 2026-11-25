"""Run the whole pipeline: data -> workflow (mock LLM) -> review gate ->
evaluation -> seeded-error test -> charts + metrics JSON + example memo.

Charts regenerate with this script (PNGs are gitignored and excluded
from any GitHub push). All data is synthetic; the demo runs on the mock
LLM adapter — no API key, no real model call.
Usage: python run_all.py   (from the project root)
"""
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from src.data_gen import generate, save_synthetic
from src.evaluate import compute_ground_truth, evaluate_memo
from src.llm_client import MockLLMAdapter
from src.time_study import measure_pipeline_time, time_saved_report
from src.workflow import (corrupt_field, parse_structured, review_gate,
                          run_workflow, write_audit_log)

ROOT = Path(__file__).resolve().parent
CHARTS = ROOT / "reports" / "charts"
CHARTS.mkdir(parents=True, exist_ok=True)

plt.rcParams.update({"figure.dpi": 150, "font.size": 10})
NAVY, GREEN, GOLD, RED = "#1A3A6B", "#2E7D5B", "#8A6D00", "#B03A2E"


def main():
    metrics_df, feedback_df = generate()
    save_synthetic(metrics_df, feedback_df, ROOT / "data" / "synthetic")

    client = MockLLMAdapter()
    weeks = list(metrics_df["week"])
    per_week = []
    audit_entries = []
    total_pipeline_seconds = 0.0

    for week in weeks:
        idx = metrics_df.index[metrics_df["week"] == week][0]
        week_row = metrics_df.iloc[idx]
        prior_row = metrics_df.iloc[idx - 1] if idx > 0 else None
        fb_week = feedback_df.loc[feedback_df["week"] == week]

        (memo, _prompt), seconds = measure_pipeline_time(
            run_workflow, week, metrics_df, feedback_df, client)
        total_pipeline_seconds += seconds

        truth = compute_ground_truth(week_row, prior_row, fb_week)
        ev = evaluate_memo(parse_structured(memo), truth)
        gate = review_gate(memo, week_row, prior_row, fb_week)
        per_week.append({
            "week": week,
            "field_accuracy": round(ev["field_accuracy"], 4),
            "fields_correct": ev["fields_correct"],
            "fields_total": ev["fields_total"],
            "insight_match": ev["insight_match"],
            "flags_correct": ev["flags_correct"],
            "error_cases": ev["errors"],
            "gate_decision": gate["decision"],
            "gate_issues": gate["issues"],
            "pipeline_seconds": round(seconds, 3),
        })
        audit_entries.append({
            "week": week, "adapter": client.name, "decision": gate["decision"],
            "issues": len(gate["issues"]), "reviewer": "demo-run",
            "review_minutes_estimate": 10,
            "note": "Demo run — not a founder adoption record.",
        })
        if week == weeks[-1]:
            (ROOT / "reports" / "weekly_memo_example.md").write_text(
                memo + "\n\n---\n_Review-gate decision: "
                f"{gate['decision']} ({len(gate['issues'])} issues)._\n",
                encoding="utf-8")

    write_audit_log(audit_entries, ROOT / "reports" / "adoption_log.jsonl")

    # ---- Seeded-error test: corrupt 3 fields in the latest memo, gate must catch all 3.
    latest = weeks[-1]
    idx = metrics_df.index[metrics_df["week"] == latest][0]
    memo_clean, _ = run_workflow(latest, metrics_df, feedback_df, client)
    corrupted = corrupt_field(memo_clean, "signups", "99999")
    corrupted = corrupt_field(corrupted, "transactions_change_pct", "42.0")
    clean_flags = parse_structured(memo_clean).get("flags", "none")
    corrupted = corrupt_field(
        corrupted, "flags",
        "none" if clean_flags != "none" else "RISK_ACCURACY_LOW")
    gate_corrupt = review_gate(corrupted, metrics_df.iloc[idx],
                               metrics_df.iloc[idx - 1],
                               feedback_df.loc[feedback_df["week"] == latest])
    seeded = {"seeded_errors": 3,
              "caught": len(gate_corrupt["issues"]),
              "issues": gate_corrupt["issues"]}

    # ---- Aggregate metrics ----
    n_weeks = len(per_week)
    total_fields = sum(w["fields_total"] for w in per_week)
    total_correct = sum(w["fields_correct"] for w in per_week)
    timing = time_saved_report(total_pipeline_seconds / n_weeks)

    metrics = {
        "adapter": client.name,
        "weeks": n_weeks,
        "field_accuracy_overall": round(total_correct / total_fields, 4) if total_fields else 0.0,
        "fields_correct": total_correct,
        "fields_total": total_fields,
        "insight_match_weeks": sum(1 for w in per_week if w["insight_match"]),
        "flags_correct_weeks": sum(1 for w in per_week if w["flags_correct"]),
        "gate_approve_weeks": sum(1 for w in per_week if w["gate_decision"] == "approve"),
        "total_error_cases": sum(len(w["error_cases"]) for w in per_week),
        "seeded_error_test": seeded,
        "timing": timing,
        "per_week": per_week,
        "disclosures": {
            "data": "All data synthetic (seeded generator). No real Uno Wallet data.",
            "llm": "Demo runs on the deterministic mock adapter. No real LLM was called; no API key exists.",
            "manual_baseline": "Manual time is an ESTIMATE from a task breakdown, not a measured observation.",
            "manual_error_rate": "Not measured — no human did these weeks by hand under observation.",
            "adoption_log": "Demo-run record only; real founder adoption is unproven and needs 4 weeks of live use.",
        },
    }
    (ROOT / "reports" / "metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")

    # ---- Charts ----
    w_labels = [w["week"][-3:] for w in per_week]

    fig, ax = plt.subplots(figsize=(8, 4))
    ax.bar(["Manual (estimate)", "Workflow\n(pipeline + review)"],
           [timing["manual_minutes_per_week_estimate"],
            timing["pipeline_minutes_per_week_measured"] + timing["review_minutes_per_week_estimate"]],
           color=[RED, GREEN])
    ax.set_ylabel("Minutes per week")
    ax.set_title("Weekly reporting time: manual estimate vs AI workflow")
    for i, v in enumerate([timing["manual_minutes_per_week_estimate"],
                           timing["pipeline_minutes_per_week_measured"] + timing["review_minutes_per_week_estimate"]]):
        ax.text(i, v + 2, f"{v:.1f} min", ha="center")
    fig.tight_layout(); fig.savefig(CHARTS / "time_saved.png"); plt.close(fig)

    fig, ax = plt.subplots(figsize=(8, 4))
    accs = [w["field_accuracy"] * 100 for w in per_week]
    ax.bar(w_labels, accs, color=[GREEN if a >= 99 else GOLD for a in accs])
    ax.set_ylim(0, 105)
    ax.set_ylabel("Field accuracy (%)")
    ax.set_title("Memo field accuracy vs ground truth, by week (evaluation harness)")
    for i, a in enumerate(accs):
        ax.text(i, a + 1, f"{a:.0f}%", ha="center")
    fig.tight_layout(); fig.savefig(CHARTS / "accuracy_by_week.png"); plt.close(fig)

    fig, ax = plt.subplots(figsize=(8, 4))
    last = per_week[-1]
    truth = compute_ground_truth(metrics_df.iloc[-1], metrics_df.iloc[-2],
                                 feedback_df.loc[feedback_df["week"] == weeks[-1]])
    items = sorted(((k, v) for k, v in truth["changes"].items() if v is not None),
                   key=lambda kv: kv[1])
    ax.barh([k.replace("_", " ") for k, _ in items], [v for _, v in items],
            color=[GREEN if v >= 0 else RED for _, v in items])
    ax.set_xlabel("Week-over-week change (%)")
    ax.set_title(f"WoW movers — {weeks[-1]} (ground truth)")
    fig.tight_layout(); fig.savefig(CHARTS / "wow_movers_latest.png"); plt.close(fig)

    fig, ax = plt.subplots(figsize=(8, 4))
    ax.bar(["Seeded errors", "Caught by review gate"],
           [seeded["seeded_errors"], seeded["caught"]], color=[NAVY, GREEN])
    ax.set_ylabel("Count")
    ax.set_title("Review gate: seeded-error detection (corrupted memo test)")
    for i, v in enumerate([seeded["seeded_errors"], seeded["caught"]]):
        ax.text(i, v + 0.1, str(v), ha="center")
    fig.tight_layout(); fig.savefig(CHARTS / "gate_seeded_errors.png"); plt.close(fig)

    print(f"weeks: {n_weeks}")
    print(f"field accuracy: {metrics['field_accuracy_overall']:.1%} "
          f"({total_correct}/{total_fields})")
    print(f"insight match: {metrics['insight_match_weeks']}/{n_weeks} weeks; "
          f"flags correct: {metrics['flags_correct_weeks']}/{n_weeks} weeks")
    print(f"gate approvals: {metrics['gate_approve_weeks']}/{n_weeks} weeks")
    print(f"seeded errors caught: {seeded['caught']}/{seeded['seeded_errors']}")
    print(f"time saved: {timing['saved_minutes_per_week']} min/week "
          f"({timing['saved_hours_per_year_52w']} h/year) — manual baseline is an estimate")
    print(f"total error cases: {metrics['total_error_cases']}")
    return metrics


if __name__ == "__main__":
    main()
