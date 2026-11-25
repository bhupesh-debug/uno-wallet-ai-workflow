"""The weekly-reporting workflow: data in, structured memo out, human review.

Pipeline:
  raw weekly rows  ->  build_prompt()  ->  LLM client (mock by default)
  -> memo text with a ##STRUCTURED## block  ->  review_gate() re-derives
  every number from the raw data  ->  approve / edit / reject  ->  audit log.

The human review gate is not optional: nothing leaves this workflow
without a reviewer decision recorded in the audit log. The gate is
rule-based — it recomputes the ground truth from the source data and
compares it field by field, so it catches invented or stale numbers
whether they came from the mock, a real LLM, or a copy-paste error.
"""
import json
import re
from pathlib import Path

import numpy as np
import pandas as pd

from src.evaluate import compute_ground_truth
from src.llm_client import KPI_LABELS, KPI_ORDER

STRUCT_RE = re.compile(r"^##STRUCTURED##\s*$", re.MULTILINE)
FIELD_RE = re.compile(r"^([a-z_]+):\s*(.*)$")


def build_prompt(week_row, prior_row, feedback_rows):
    """Render the raw numbers as prompt text. The client gets raw values
    only — no pre-computed deltas, so it has to do the arithmetic."""
    week = week_row["week"]
    lines = [
        f"Write a weekly performance memo for week {week}.",
        "Current week vs prior week. A metric may be missing (n/a) — if so,",
        "say so and never invent it. A negative value is a data fault.",
        "",
        "METRICS (current week, prior week in brackets):",
    ]
    for k in KPI_ORDER:
        cur = week_row[k]
        pri = prior_row[k] if prior_row is not None else np.nan
        cur_s = "n/a" if pd.isna(cur) else (str(int(cur)) if float(cur).is_integer() else f"{cur:.2f}")
        pri_s = "n/a" if (prior_row is None or pd.isna(pri)) else (str(int(pri)) if float(pri).is_integer() else f"{pri:.2f}")
        lines.append(f"- {k}: {cur_s} (prior: {pri_s})")
    lines.append("")
    lines.append("USER FEEDBACK THIS WEEK (theme: text):")
    if len(feedback_rows) == 0:
        lines.append("(none)")
    for _, fb in feedback_rows.iterrows():
        lines.append(f"FEEDBACK {fb['theme']}: {fb['text']}")
    return "\n".join(lines)


def parse_structured(memo_text):
    """Parse the ##STRUCTURED## block into a dict of raw strings."""
    m = STRUCT_RE.search(memo_text)
    if not m:
        return {}
    out = {}
    for line in memo_text[m.end():].splitlines():
        fm = FIELD_RE.match(line.strip())
        if fm:
            out[fm.group(1)] = fm.group(2).strip()
    return out


def run_workflow(week, metrics_df, feedback_df, client):
    """Run one week through the client. Returns (memo_text, prompt)."""
    row = metrics_df.loc[metrics_df["week"] == week]
    if len(row) == 0:
        raise ValueError(f"week {week} not in metrics data")
    week_row = row.iloc[0]
    idx = metrics_df.index[metrics_df["week"] == week][0]
    prior_row = metrics_df.iloc[idx - 1] if idx > 0 else None
    fb = feedback_df.loc[feedback_df["week"] == week]
    prompt = build_prompt(week_row, prior_row, fb)
    memo = client.generate(prompt)
    return memo, prompt


def corrupt_field(memo_text, field, new_value):
    """Test helper: replace one structured-block field's value wholesale.
    Used by the seeded-error test so a corruption is always a real change
    (a naive prepend can be a no-op when the value already contains it)."""
    pattern = re.compile(rf"^{re.escape(field)}: .*$", re.MULTILINE)
    return pattern.sub(f"{field}: {new_value}", memo_text, count=1)


def review_gate(memo_text, week_row, prior_row, feedback_df_week):
    """Re-derive the ground truth and compare field by field.

    Returns a dict: {decision, issues, checked, passed}.
    decision is 'approve' when there are no issues, else 'needs_fix'.
    Every issue names the field, the memo value, and the true value.
    """
    truth = compute_ground_truth(week_row, prior_row, feedback_df_week)
    fields = parse_structured(memo_text)
    issues = []
    checked = 0

    def _f(tok):
        if tok in (None, "", "n/a"):
            return None
        try:
            return float(tok)
        except ValueError:
            return "UNPARSEABLE"

    for k in KPI_ORDER:
        # Value check.
        checked += 1
        memo_val = _f(fields.get(k))
        true_val = truth["kpis"].get(k)
        if memo_val == "UNPARSEABLE" or (memo_val is None) != (true_val is None) or (
            memo_val is not None and true_val is not None and abs(memo_val - true_val) > 0.01
        ):
            issues.append(f"{k}: memo says {fields.get(k)} but source data says "
                          f"{'n/a' if true_val is None else true_val}")
        # % change check.
        checked += 1
        memo_ch = _f(fields.get(f"{k}_change_pct"))
        true_ch = truth["changes"].get(k)
        if memo_ch == "UNPARSEABLE" or (memo_ch is None) != (true_ch is None) or (
            memo_ch is not None and true_ch is not None and abs(memo_ch - true_ch) > 0.1
        ):
            issues.append(f"{k}_change_pct: memo says {fields.get(f'{k}_change_pct')} "
                          f"but recomputed value is {'n/a' if true_ch is None else round(true_ch, 1)}")
    # Top mover check — any tied metric is acceptable.
    checked += 1
    if fields.get("top_mover", "n/a") not in truth["top_movers"]:
        issues.append(f"top_mover: memo says {fields.get('top_mover')} but acceptable "
                      f"answers are {truth['top_movers']}")
    # Flags check — memo must carry exactly the expected set.
    checked += 1
    memo_flags = set() if fields.get("flags") in (None, "none", "") else set(fields["flags"].split(","))
    if memo_flags != set(truth["flags"]):
        issues.append(f"flags: memo says {sorted(memo_flags)} but expected {sorted(truth['flags'])}")
    # Feedback theme check.
    checked += 1
    if fields.get("top_feedback_theme", "n/a") != truth["top_feedback_theme"]:
        issues.append(f"top_feedback_theme: memo says {fields.get('top_feedback_theme')} "
                      f"but expected {truth['top_feedback_theme']}")
    return {
        "decision": "approve" if not issues else "needs_fix",
        "issues": issues,
        "checked": checked,
        "passed": checked - len(issues),
    }


def write_audit_log(entries, path):
    """Append review decisions to a JSONL audit log. Each entry records
    week, adapter, decision, issue count, reviewer and review minutes.
    In this demo the reviewer is the demo run itself — the log is the
    record of what the gate decided, not a claim that a founder used it."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        for e in entries:
            f.write(json.dumps(e) + "\n")
    return path
