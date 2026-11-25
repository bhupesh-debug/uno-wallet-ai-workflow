"""Time study: what the workflow saves, and what is estimated vs measured.

MEASURED (this run, wall clock): pipeline runtime per week — data load,
prompt build, mock generation, review gate. Measured with
time.perf_counter() in run_all.py.

ESTIMATED (labelled as such everywhere it appears): the manual baseline.
Nobody timed a founder writing this memo by hand, and this project does
not pretend otherwise. The baseline is a task breakdown with minutes per
task — the author's estimate, built from the shape of the work (the
candidate's JPMorgan reporting work had the same shape: pull numbers,
reconcile, write, proofread). It is an estimate to be replaced by a real
timing the first week the workflow runs in production.

REVIEW TIME is also an estimate (10 minutes per week) until measured.

What is NOT claimed: a measured manual error rate. No human did these
eight weeks by hand under observation, so there is no manual error rate
to compare against. Instead the report gives (a) the memo's measured
field accuracy from the evaluation harness, and (b) the review gate's
seeded-error detection rate — both measured, both labelled.
"""
import time

# Manual baseline: task breakdown in minutes (ESTIMATE — see module docstring).
MANUAL_TASKS = [
    ("Pull the week's numbers from each source", 25),
    ("Compute week-over-week deltas and check them", 20),
    ("Write the memo (headline, table, insights, actions)", 45),
    ("Proofread numbers against sources", 15),
]

REVIEW_MINUTES_ESTIMATE = 10  # human review-gate time per week (ESTIMATE)


def manual_baseline_minutes():
    return sum(m for _, m in MANUAL_TASKS)


def measure_pipeline_time(fn, *args, **kwargs):
    """Run fn and return (result, seconds)."""
    start = time.perf_counter()
    result = fn(*args, **kwargs)
    return result, time.perf_counter() - start


def time_saved_report(pipeline_seconds_per_week, review_minutes=REVIEW_MINUTES_ESTIMATE):
    """Return the time-saved figures. pipeline_seconds is MEASURED;
    the manual baseline and review time are ESTIMATES (see docstring)."""
    manual = manual_baseline_minutes()
    pipeline_min = pipeline_seconds_per_week / 60.0
    total_workflow = pipeline_min + review_minutes
    saved = manual - total_workflow
    return {
        "manual_minutes_per_week_estimate": manual,
        "pipeline_minutes_per_week_measured": round(pipeline_min, 3),
        "review_minutes_per_week_estimate": review_minutes,
        "saved_minutes_per_week": round(saved, 2),
        "saved_hours_per_week": round(saved / 60.0, 2),
        "saved_hours_per_year_52w": round(saved * 52 / 60.0, 1),
        "time_reduction_pct": round(100.0 * saved / manual, 1) if manual else 0.0,
    }
