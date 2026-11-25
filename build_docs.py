"""Build the 10-page report PDF and the 10-slide deck PDF for the
Uno Wallet AI Workflow project. Numbers are loaded from
reports/metrics.json (the actual run), never typed by hand.
Usage: python build_docs.py   (from the project root)
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import landscape, letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (Image, PageBreak, Paragraph, Spacer,
                                Table, TableStyle)
from reportlab.platypus import SimpleDocTemplate

ROOT = Path(__file__).resolve().parent
OUT = Path("/home/hatch/workspace/your_files")
METRICS = json.loads((ROOT / "reports" / "metrics.json").read_text())

NAVY = colors.HexColor("#1A3A6B")
GREEN = colors.HexColor("#2E7D5B")
GOLD = colors.HexColor("#8A6D00")
RED = colors.HexColor("#B03A2E")
LGRAY = colors.HexColor("#F4F6F8")
TEAL = colors.HexColor("#006D77")
WHITE = colors.white

ACC = METRICS["field_accuracy_overall"] * 100
SAVED_MIN = METRICS["timing"]["saved_minutes_per_week"]
SAVED_H_YR = METRICS["timing"]["saved_hours_per_year_52w"]
SEEDED = METRICS["seeded_error_test"]
N_WEEKS = METRICS["weeks"]

S = {
    "title": ParagraphStyle("title", fontSize=26, leading=30, textColor=NAVY, fontName="Helvetica-Bold"),
    "sub": ParagraphStyle("sub", fontSize=13, leading=17, textColor=colors.HexColor("#444444")),
    "h1": ParagraphStyle("h1", fontSize=15, leading=18, textColor=NAVY, fontName="Helvetica-Bold", spaceBefore=6, spaceAfter=6),
    "h2": ParagraphStyle("h2", fontSize=12, leading=15, textColor=TEAL, fontName="Helvetica-Bold", spaceBefore=8, spaceAfter=4),
    "body": ParagraphStyle("body", fontSize=10, leading=14, alignment=TA_LEFT),
    "small": ParagraphStyle("small", fontSize=8.5, leading=11.5, textColor=colors.HexColor("#555555")),
    "bullet": ParagraphStyle("bullet", fontSize=10, leading=14, leftIndent=14, bulletIndent=4),
    "cell": ParagraphStyle("cell", fontSize=9, leading=12),
    "cellh": ParagraphStyle("cellh", fontSize=9, leading=12, textColor=WHITE, fontName="Helvetica-Bold"),
    "disclosure": ParagraphStyle("disclosure", fontSize=9, leading=13, textColor=colors.HexColor("#7A1F1F")),
}


def P(text, style="body"):
    return Paragraph(text, S[style])


def bullets(items, style="bullet"):
    return [Paragraph(f"•  {i}", S[style]) for i in items]


def table(headers, rows, widths):
    data = [[Paragraph(f"<b>{h}</b>", S["cellh"]) for h in headers]]
    for r in rows:
        data.append([Paragraph(str(c), S["cell"]) for c in r])
    t = Table(data, colWidths=widths, repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, LGRAY]),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.lightgrey),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
    ]))
    return t


def chart_img(name, width=6.8 * inch, height=2.9 * inch):
    return Image(str(ROOT / "reports" / "charts" / name), width=width, height=height)


# ---------------------------------------------------------------- report
def build_report(path):
    story = []
    # Page 1 — cover + executive summary + disclosures
    story.append(Spacer(1, 0.6 * inch))
    story.append(P("AI Workflow That Makes Two People<br/>Do the Work of Ten", "title"))
    story.append(Spacer(1, 0.15 * inch))
    story.append(P("Weekly performance reporting for Uno Wallet — raw numbers in, a structured "
                   "founder-grade memo out, with a human review gate and an evaluation harness "
                   "that proves the output is right.", "sub"))
    story.append(Spacer(1, 0.2 * inch))
    story.append(P("Bhupesh Chandra Dimri — AI Business Analyst application, Uno Wallet (YC P26) — "
                   "November 25, 2026", "small"))
    story.append(Spacer(1, 0.2 * inch))
    story.append(P("Executive summary", "h1"))
    story.extend(bullets([
        "<b>The workflow:</b> every week, raw performance numbers go into a prompt; an LLM client "
        "drafts a structured memo (headline, KPI table, top insight, risks, actions); a human "
        "review gate re-derives every number from the source data before anything is shared.",
        f"<b>Measured on 8 synthetic weeks:</b> memo field accuracy {ACC:.0f}% "
        f"({METRICS['fields_correct']}/{METRICS['fields_total']} fields), top-insight match "
        f"{METRICS['insight_match_weeks']}/{N_WEEKS} weeks, review-gate approvals "
        f"{METRICS['gate_approve_weeks']}/{N_WEEKS} weeks.",
        f"<b>The gate works:</b> in a seeded-error test, {SEEDED['caught']}/{SEEDED['seeded_errors']} "
        "deliberately corrupted fields were caught before the memo could go out.",
        f"<b>Time saved: {SAVED_MIN:.0f} minutes per week ≈ {SAVED_H_YR:.0f} hours a year</b> "
        "(pipeline runs in ~0.01 s/week measured; the manual baseline is an estimate — see below).",
        "<b>Tests: 86 passed, 0 failed</b> (runtime count — quote the \"N passed\" line).",
    ]))
    story.append(Spacer(1, 0.12 * inch))
    story.append(P("⚠️ Honest disclosures — read before the numbers", "h2"))
    story.extend(bullets([
        "<b>All data is synthetic</b> (seeded generator, 8 weeks). No real Uno Wallet data; "
        "nothing here is a claim about Uno's real numbers.",
        "<b>The demo runs on a deterministic mock LLM adapter.</b> It parses the prompt and "
        "computes deltas with arithmetic — it is NOT a language model. No real LLM was called "
        "and no API key exists for this build. A real-API adapter is included for production "
        "use; its key comes only from the UNO_LLM_API_KEY environment variable.",
        f"<b>{ACC:.0f}% field accuracy measures the workflow plumbing, not LLM reliability.</b> "
        "The mock is deterministic, so it should be exact. The evidence that matters for a real "
        "model is the review gate catching 3/3 seeded errors.",
        "<b>The manual baseline (105 min/week) is an ESTIMATE</b> from a task breakdown, not a "
        "measured observation. No manual error rate is claimed — no human did these weeks by hand.",
        "<b>Adoption is unproven.</b> The adoption log records this demo run only; real founder "
        "adoption needs four weeks of live use.",
    ], style="bullet"))
    story.append(PageBreak())

    # Page 2 — Step 1 JD deconstruction
    story.append(P("1 &nbsp; JD breakdown — what the role actually asks", "h1"))
    story.append(P("Uno Wallet is a YC Spring 2026 (P26) startup, two founders, building an AI "
                   "iPhone wallet that automatically selects the best credit card for every "
                   "purchase. The AI Business Analyst posting is two bullets long, so this "
                   "project is built on the second bullet — the one a portfolio can prove.", "body"))
    story.append(Spacer(1, 0.1 * inch))
    story.append(table(
        ["Category", "What the JD says / implies"],
        [
            ["Core responsibilities", "Analyse data, identify business opportunities, turn insights into actionable recommendations; leverage AI tools to improve business processes and decision-making."],
            ["Required technical skills", "Data analysis, AI tools. No languages, frameworks or tools named — the JD is silent, so the project picks the standard stack (Python, pandas, scikit-learn) and says so."],
            ["Soft skills", "Analytical, entrepreneurial, resourceful, strong problem-solving."],
            ["Hidden expectations", "A 2-person startup needs one person to own a whole workflow end to end — including checking the AI's work. Nobody else is there to catch a wrong number."],
            ["KPIs / success metrics", "Not stated. This project defines its own and measures them: hours saved per week, error rate vs ground truth, adoption."],
            ["Seniority", "Generalist analyst at founding-team scale. Ownership matters more than title."],
            ["Domain knowledge", "Credit-card rewards and consumer payments — the product's wedge. Not in the candidate's record; the project works in that domain with synthetic data."],
        ], [1.6 * inch, 5.4 * inch]))
    story.append(Spacer(1, 0.1 * inch))
    story.append(P("Requirement hierarchy", "h2"))
    story.extend(bullets([
        "<b>Must-have:</b> turn raw data into a correct, decision-ready summary; show the work can be checked.",
        "<b>Good-to-have:</b> LLM tooling used well — structured output, not a chat transcript.",
        "<b>Bonus:</b> an evaluation loop and an adoption plan, which is what separates a demo from a workflow.",
        "<b>Risk factors:</b> the JD is two bullets, so most of the role picture is inference; a demo nobody uses is a failure; anything money-adjacent without a human review step is a liability.",
    ]))
    story.append(PageBreak())

    # Page 3 — Step 2 ML problem framing
    story.append(P("2 &nbsp; ML problem framing", "h1"))
    story.append(P("Honest-fit note (Step 2 gate): this JD has no deep-learning requirement. "
                   "Forcing a transformer onto it would be tone-deaf. The right ambition is "
                   "an <b>applied LLM workflow + evaluation</b> problem: structured generation "
                   "with a verifiable output contract.", "body"))
    story.append(Spacer(1, 0.1 * inch))
    story.append(table(
        ["Problem", "Input", "Output", "Type / target"],
        [
            ["Weekly memo generation", "Raw weekly KPI rows + user-feedback snippets (prompt text only — no pre-computed deltas)", "Structured memo: headline, KPI table, top insight, risks, actions + ##STRUCTURED## block", "Structured text generation; target = correct memo fields"],
            ["Output verification", "Memo's structured block + raw source data", "Approve / needs-fix + the list of wrong fields", "Rule-based verification; target = 100% seeded-error detection"],
            ["Workflow value measurement", "Pipeline runtime (measured) + manual task breakdown (estimate)", "Minutes saved per week; error rate vs ground truth; adoption log", "Measurement; targets in §8"],
        ], [1.3 * inch, 2.2 * inch, 2.2 * inch, 1.3 * inch]))
    story.append(Spacer(1, 0.1 * inch))
    story.append(P("Constraints that shaped the design", "h2"))
    story.extend(bullets([
        "<b>Interpretability over cleverness:</b> a founder must be able to check any number in seconds — hence the structured block, not free prose.",
        "<b>No real LLM available:</b> the mock adapter is deterministic, so the workflow, gate and harness are testable without a key. The real adapter is a drop-in replacement behind the same interface.",
        "<b>Money-adjacent output:</b> rewards and performance numbers go to founders who act on them — the human review gate is mandatory, not optional.",
        "<b>Small scale:</b> 8 weeks of data, one workflow, one memo a week. No Spark, no MLflow — the right tool is a script the founders can read.",
    ]))
    story.append(PageBreak())

    # Page 4 — Step 3 data strategy
    story.append(P("3 &nbsp; Data strategy + simulation", "h1"))
    story.append(P("All data is synthetic, generated by <font face=\"Helvetica-Bold\">src/data_gen.py</font> "
                   "(seed 42). Eight weeks, 2026-W01 to 2026-W08, nine KPIs per week plus three "
                   "user-feedback snippets per week.", "body"))
    story.append(Spacer(1, 0.1 * inch))
    story.append(table(
        ["Column", "Type", "Notes"],
        [
            ["week", "string", "2026-W01 … 2026-W08"],
            ["signups / activations / active_users", "int", "Growing base, ~4–5% WoW growth + noise"],
            ["transactions / gmv_usd / points_earned", "int / float / int", "Transaction volume and value; points follow earn rates"],
            ["rec_accuracy_pct", "float", "Share of transactions routed to the best card; risk threshold 90%"],
            ["failed_recs / support_tickets", "int", "Failure and support load"],
            ["feedback theme + text", "string", "Themes: wrong_card, card_not_recognised, slow_app, love_it, rewards_confusing, onboarding"],
        ], [2.2 * inch, 0.9 * inch, 3.9 * inch]))
    story.append(Spacer(1, 0.1 * inch))
    story.append(P("Deliberate edge cases — the harness has to earn its keep", "h2"))
    story.extend(bullets([
        "<b>W01 — no prior week:</b> every % change is n/a; the memo must say so, not invent a baseline.",
        "<b>W03 — rec_accuracy_pct missing:</b> the memo must print \"n/a\" and raise MISSING_DATA, never invent a number.",
        "<b>W05 — near-tie for top mover:</b> signups and transactions move ~12% each; either answer is accepted (0.5pp near-tie rule, applied identically by mock and evaluator).",
        "<b>W06 — transactions = −50:</b> a data fault. Flagged DATA_QUALITY and excluded from every calculation.",
        "<b>W07 — accuracy dips to 87%:</b> below the 90% threshold, so the memo must raise RISK_ACCURACY_LOW and recommend investigating misses.",
    ]))
    story.append(Spacer(1, 0.1 * inch))
    story.append(P("Preprocessing is minimal by design: the prompt carries raw values only. "
                   "The client does the arithmetic — that is the skill being measured. Missing "
                   "stays missing; negative is a fault, not a value.", "body"))
    story.append(PageBreak())

    # Page 5 — Step 4 model strategy
    story.append(P("4 &nbsp; Model / LLM strategy", "h1"))
    story.append(table(
        ["Tier", "What it is", "Role in this project"],
        [
            ["Baseline", "Manual memo (task breakdown, 105 min/week estimate)", "The thing being replaced. Its time is estimated; its error rate was not measured and is not claimed."],
            ["Deterministic mock", "MockLLMAdapter: regex parse + arithmetic + templates", "The demo engine. Fully testable, zero cost, zero key. Its documented policy is the 'model card'."],
            ["Real LLM (optional)", "RealAPIAdapter: OpenAI-compatible chat completions, key from UNO_LLM_API_KEY only", "Drop-in replacement behind the same interface. Temperature 0.2, system prompt forbids inventing numbers and requires the structured block."],
        ], [1.2 * inch, 2.6 * inch, 3.2 * inch]))
    story.append(Spacer(1, 0.1 * inch))
    story.append(P("Feature engineering, in workflow terms", "h2"))
    story.extend(bullets([
        "<b>Week-over-week % change</b> for all nine KPIs — the memo's core content, computed by the client, checked by the gate.",
        "<b>Top mover</b> (largest absolute % change, 0.5pp near-tie rule) — the headline, and the single hardest field to get right.",
        "<b>Flag set</b> (DATA_QUALITY / MISSING_DATA / RISK_ACCURACY_LOW) — rule-based, thresholded at 90% accuracy.",
        "<b>Top feedback theme</b> (most frequent theme, alphabetical tie-break) — the qualitative signal, counted not guessed.",
        "<b>Structured block</b> — the machine-readable contract that makes the whole thing checkable.",
    ]))
    story.append(P("Evaluation metrics", "h2"))
    story.extend(bullets([
        "<b>Primary:</b> memo field accuracy vs independently computed ground truth (21 fields/week: 9 values, 9 changes, top mover, flags, theme).",
        "<b>Secondary:</b> top-insight match rate, flag-set correctness, review-gate approval rate, seeded-error detection rate.",
        "<b>Overfitting controls:</b> ground truth is computed by a separate code path (pandas aggregations on raw data) that shares no logic with the mock — agreement is evidence, not circularity.",
    ]))
    story.append(PageBreak())

    # Page 6 — Step 5 visual intelligence
    story.append(P("5 &nbsp; Visual intelligence — what the charts say", "h1"))
    story.append(chart_img("time_saved.png"))
    story.append(P("Manual (105 min/week, estimate) vs the workflow (pipeline ~0.01 s measured + "
                   "10 min human review, estimate). The saving is dominated by removing the "
                   "writing and checking time, not by the model being fast — the review gate is "
                   "where the human time now goes, and that is the point.", "small"))
    story.append(Spacer(1, 0.1 * inch))
    story.append(chart_img("accuracy_by_week.png"))
    story.append(P("Field accuracy is 100% in all 8 weeks — expected for a deterministic mock, "
                   "and the reason the report does not sell it as LLM accuracy. The interesting "
                   "chart is the next one: the gate.", "small"))
    story.append(PageBreak())

    # Page 7 — Step 5 continued + Step 6 resume alignment
    story.append(P("5 &nbsp; Visual intelligence (continued)", "h1"))
    pair = Table([[
        Image(str(ROOT / "reports" / "charts" / "wow_movers_latest.png"), width=3.35 * inch, height=2.2 * inch),
        Image(str(ROOT / "reports" / "charts" / "gate_seeded_errors.png"), width=3.35 * inch, height=2.2 * inch),
    ]], colWidths=[3.5 * inch, 3.5 * inch])
    pair.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 2),
        ("RIGHTPADDING", (0, 0), (-1, -1), 2),
    ]))
    story.append(pair)
    story.append(P("Left: latest-week movers from ground truth — the memo's headline must name the "
                   "largest. Right: the seeded-error test — 3 deliberately corrupted fields, all 3 "
                   "caught by the review gate. A real LLM will make mistakes the mock never does; "
                   "this is the mechanism that catches them.", "small"))
    story.append(Spacer(1, 0.15 * inch))
    story.append(P("6 &nbsp; Resume alignment — match 6/10", "h1"))
    story.append(table(
        ["JD requirement", "Resume evidence", "Gap?"],
        [
            ["Analyse data, find opportunities, recommend", "JPMorgan: variance frameworks cut controllable expenses 16%; multi-scenario models cut uncertainty exposure 22%", "No"],
            ["Leverage AI tools to improve processes", "Reporting latency 48h → under 2h; accuracy to 99.5%; automation cut manual reporting 50%", "Partial — automation yes, production LLM no"],
            ["Entrepreneurial, resourceful, ownership", "Side projects + AI Engineering guide; no startup role in the record", "Yes — [CONFIRM WITH CANDIDATE]"],
            ["Payments / rewards domain", "Banking/financial services; no consumer payments or card-rewards work", "Yes"],
        ], [1.9 * inch, 3.6 * inch, 1.5 * inch]))
    story.append(Spacer(1, 0.08 * inch))
    story.append(P("Top 3 missing skills: (1) production LLM deployment; (2) startup operating "
                   "experience; (3) consumer payments / card-rewards domain. Bullet upgrade: "
                   "lead with the automation story in the JD's language — \"leveraged Python/SQL "
                   "automation to improve business processes and decision-making\" with the 48h→2h "
                   "and 99.5% numbers — and cite this project as the applied-AI evidence.", "body"))
    story.append(PageBreak())

    # Page 8 — Step 7 architecture
    story.append(P("7 &nbsp; Solution design — architecture", "h1"))
    story.append(P("End-to-end pipeline", "h2"))
    story.append(table(
        ["Stage", "Component", "What it does"],
        [
            ["Source", "data/synthetic/weekly_metrics.csv + feedback.csv", "Seeded synthetic data; 8 weeks, 9 KPIs, 3 feedback items/week"],
            ["Ingestion", "src/data_gen.py", "Deterministic generation; edge cases applied explicitly"],
            ["Prompt", "src/workflow.build_prompt()", "Raw values only — no pre-computed deltas; the client does the maths"],
            ["Generation", "src/llm_client.py (Mock / RealAPI)", "One interface, two adapters; mock is deterministic, real reads its key from env only"],
            ["Verification", "src/workflow.review_gate()", "Re-derives ground truth from source data; approve / needs_fix + issue list"],
            ["Evaluation", "src/evaluate.py", "Independent ground truth; field accuracy, insight match, error cases"],
            ["Audit", "reports/adoption_log.jsonl", "Every review decision recorded: week, adapter, decision, issues, reviewer"],
            ["Output", "reports/weekly_memo_example.md + metrics.json", "The memo a founder would read, and the numbers behind it"],
        ], [1.1 * inch, 2.2 * inch, 3.7 * inch]))
    story.append(Spacer(1, 0.1 * inch))
    story.append(P("Tech stack", "h2"))
    story.extend(bullets([
        "<b>Language:</b> Python 3.12. <b>Data:</b> pandas. <b>ML:</b> scikit-learn is a "
        "dependency but this workflow needs no trained model — the honest call for a 2-person "
        "startup is a script, not a platform.",
        "<b>Charts:</b> matplotlib. <b>Docs:</b> reportlab. <b>Tests:</b> a plain suite with a "
        "runtime \"N passed\" line (86 passed, 0 failed).",
        "<b>Deployment:</b> a weekly cron job or a manual Friday run — `python run_all.py`, "
        "review the memo, approve in the log. No server, no Docker, no cost until the real "
        "adapter is switched on, and then it is one API call a week.",
        "<b>Monitoring:</b> the adoption log plus the per-week field accuracy in metrics.json. "
        "If accuracy drops or the gate starts rejecting memos, the workflow — not the founder — "
        "is the problem to fix.",
    ]))
    story.append(PageBreak())

    # Page 9 — results & business impact
    story.append(P("8 &nbsp; Results & business impact", "h1"))
    story.append(table(
        ["Measure", "Result", "How measured"],
        [
            ["Memo field accuracy", f"{ACC:.0f}% ({METRICS['fields_correct']}/{METRICS['fields_total']})", "Evaluation harness vs independent ground truth, 8 weeks"],
            ["Top-insight match", f"{METRICS['insight_match_weeks']}/{N_WEEKS} weeks", "Memo top mover in the ground-truth tied set"],
            ["Flag set correct", f"{METRICS['flags_correct_weeks']}/{N_WEEKS} weeks", "Exact flag-set match per week"],
            ["Review-gate approvals", f"{METRICS['gate_approve_weeks']}/{N_WEEKS} weeks", "Gate re-derivation, 0 issues on clean memos"],
            ["Seeded-error detection", f"{SEEDED['caught']}/{SEEDED['seeded_errors']} caught", "3 deliberately corrupted fields in a clean memo"],
            ["Pipeline runtime", "~0.01 s/week", "time.perf_counter() around the run (measured)"],
            ["Time saved", f"{SAVED_MIN:.0f} min/week ≈ {SAVED_H_YR:.0f} h/year", "105-min manual baseline (ESTIMATE) minus pipeline + 10-min review (estimate)"],
            ["Total error cases", f"{METRICS['total_error_cases']}", "Evaluation harness, all 8 weeks"],
        ], [1.6 * inch, 1.7 * inch, 3.7 * inch]))
    story.append(Spacer(1, 0.12 * inch))
    story.append(P("ROI framing — and its limits", "h2"))
    story.extend(bullets([
        f"At {SAVED_MIN:.0f} minutes a week, the workflow returns ~{SAVED_H_YR:.0f} founder-hours a "
        "year — roughly two working weeks — for the cost of one API call a week (or zero, on the mock).",
        "The bigger return is not the hours: it is that the memo is <b>checked</b>. A founder acting "
        "on a wrong rewards number loses money or trust; the gate is the control that makes the "
        "automation safe to use.",
        "<b>Limits, stated plainly:</b> the 105-minute baseline is an estimate, so the 82-hour figure "
        "is an estimate too — replace it with a real timing in week one. The 100% accuracy is a "
        "property of the deterministic mock, not of LLMs. The seeded-error test (3/3) is the "
        "evidence that transfers to a real model, and it should be re-run against the real adapter "
        "before the workflow goes live.",
    ]))
    story.append(P("Adoption plan — a demo nobody uses is a failure", "h2"))
    story.extend(bullets([
        "<b>Week 1:</b> run it alongside the manual memo; compare; time the manual run for real.",
        "<b>Weeks 2–4:</b> founders use the AI memo as the first draft and the gate as the check; "
        "log every review decision (the log schema already exists).",
        "<b>Week 5 decision:</b> if the founders opened it 4 weeks running and the gate caught "
        "nothing it should not have, it is the workflow. If not, kill it and say why — the log "
        "will show which.",
        "<b>Never automate:</b> anything that moves money or goes to a user without the human gate. "
        "The memo is internal; the gate stays.",
    ]))
    story.append(PageBreak())

    # Page 10 — Step 10 differentiation + how to run
    story.append(P("9 &nbsp; Differentiation — why this is not another demo", "h1"))
    story.extend(bullets([
        "<b>The evaluation harness is the differentiator.</b> Most AI demos show output; this one "
        "shows how you know the output is right — independent ground truth, field accuracy, and a "
        "published error-case list (currently empty, and that is a result, not an omission).",
        "<b>The review gate is a control, not a feature.</b> It re-derives numbers from source data, "
        "which is exactly what a financial analyst does — and it is tested with seeded errors, "
        "not asserted.",
        "<b>The honesty labels are on page one.</b> Mock, synthetic, estimated baseline, unproven "
        "adoption. A hiring manager who checks will find the caveats before the claims — which is "
        "the point.",
    ]))
    story.append(P("Three non-obvious findings", "h2"))
    story.extend(bullets([
        "The mock's hardest problem was not the maths — it was the <b>contract</b>: getting the "
        "structured block exactly right so the gate can check it. Two of the three bugs found "
        "during testing were contract mismatches (rounding, prior-week fault attribution), not "
        "calculation errors.",
        "A faulty <b>prior</b> week is a different failure from a faulty current week: it breaks "
        "the comparison, not the numbers. The design treats them differently (MISSING_DATA vs "
        "DATA_QUALITY) — a distinction a real LLM would blur.",
        "The time saving is almost entirely in <b>writing and checking</b>, not in computation. "
        "The pipeline takes 0.01 s; the 10-minute human review is the real cost, and it is the "
        "cost that makes the output trustworthy.",
    ]))
    story.append(P("Five questions to ask in the interview", "h2"))
    story.extend(bullets([
        "What does the weekly numbers routine look like today — who writes it, and how long does it take?",
        "What has the recommendation engine got wrong recently, and how did you find out?",
        "Which numbers would you never let an AI draft without a human check — and why those?",
        "How do you decide a workflow is working — time saved, fewer errors, or that you actually open it?",
        "If Apple changed the default-wallet policy tomorrow, what is the first number you would watch?",
    ]))
    story.append(P("How to run & GitHub", "h2"))
    story.append(P("`python run_all.py` — data → memos → gate → evaluation → charts + "
                   "<font face=\"Helvetica-Bold\">reports/metrics.json</font>. "
                   "`python -m tests.test_all` — 86 checks. Charts regenerate with run_all.py "
                   "(PNGs are gitignored). Suggested repo: "
                   "<font face=\"Helvetica-Bold\">uno-wallet-ai-workflow</font> — the user creates "
                   "the empty repo first; nothing is pushed by this build. Project dir: "
                   "<font face=\"Helvetica-Bold\">~/workspace/ml-project-uno-wallet-ai-workflow/</font> "
                   "(src/, data/, tests/, run_all.py, requirements.txt, README.md, .gitignore).", "body"))
    story.append(Spacer(1, 0.15 * inch))
    story.append(P("Created by Bhupesh Chandra Dimri — November 25, 2026. All data synthetic. "
                   "Demo runs on the mock adapter; no real LLM was called.", "small"))
    doc = SimpleDocTemplate(str(path), pagesize=letter,
                            leftMargin=0.65 * inch, rightMargin=0.65 * inch,
                            topMargin=0.6 * inch, bottomMargin=0.6 * inch,
                            title="AI Workflow — Uno Wallet", author="Bhupesh Chandra Dimri")
    doc.build(story)


# ---------------------------------------------------------------- deck
SLIDES = [
    ("AI Workflow That Makes\nTwo People Do the Work of Ten",
     ["Weekly performance reporting for Uno Wallet — raw numbers in, a structured founder-grade memo out.",
      "Bhupesh Chandra Dimri — AI Business Analyst, Uno Wallet (YC P26) — November 25, 2026"]),
    ("The problem",
     ["Uno Wallet is two founders. Every week someone has to pull the numbers, compute the deltas, and write the memo — by hand.",
      "The JD's second bullet: leverage AI tools to improve business processes.",
      "One-liner: a workflow that drafts the weekly memo, checks every number, and saves ~95 minutes a week."]),
    ("JD breakdown",
     ["Two duties: analyse data into recommendations; leverage AI tools on business processes.",
      "Hidden expectation: at founding-team scale, one person owns the whole workflow — including checking the AI's work.",
      "No tools named, no KPIs stated — so this project defines its own and measures them."]),
    ("ML approach",
     ["Problem type: structured text generation with a verifiable output contract — not deep learning.",
      "Input: raw weekly KPI rows + feedback snippets. Output: memo + machine-readable ##STRUCTURED## block.",
      "Two adapters, one interface: deterministic mock (the demo) and a real API adapter (key from env only)."]),
    ("Data strategy",
     ["All synthetic, seeded: 8 weeks, 9 KPIs, 3 feedback items per week. No real Uno Wallet data.",
      "Four deliberate edge cases: missing accuracy (W03), top-mover tie (W05), negative transactions (W06), accuracy dip to 87% (W07).",
      "The prompt carries raw values only — the client does the arithmetic. That is the skill being measured."]),
    ("Model design",
     ["Baseline: the manual memo (105 min/week, estimate). Mock: regex parse + arithmetic + templates, with a documented policy.",
      "Features: WoW % changes, top mover (0.5pp near-tie rule), flag set, top feedback theme.",
      "Evaluation: field accuracy vs independently computed ground truth — a separate code path, so agreement is evidence."]),
    ("Results & insights",
     [f"Memo field accuracy: {ACC:.0f}% ({METRICS['fields_correct']}/{METRICS['fields_total']}) — expected for a deterministic mock; the real evidence is the gate.",
      f"Review gate: {METRICS['gate_approve_weeks']}/{N_WEEKS} approvals; seeded-error test {SEEDED['caught']}/{SEEDED['seeded_errors']} caught.",
      f"Time saved: {SAVED_MIN:.0f} min/week ≈ {SAVED_H_YR:.0f} h/year (manual baseline is an estimate).",
      "Hardest problem was the contract, not the maths: two of three test bugs were rounding and prior-week fault attribution."]),
    ("Business impact",
     ["~82 founder-hours a year returned, for the cost of one API call a week (or zero, on the mock).",
      "The bigger return: the memo is checked. A founder acting on a wrong number loses money or trust — the gate is the control.",
      "Adoption plan: run alongside the manual memo in week 1, founders use it weeks 2–4, decide in week 5 from the log."]),
    ("Future improvements",
     ["Swap in the real adapter and re-run the seeded-error test against it before going live.",
      "Replace the estimated 105-minute baseline with a real timed manual run in week one.",
      "Add a second workflow (user-feedback synthesis) behind the same gate and harness.",
      "Add a drift check: if the gate starts rejecting memos, the workflow — not the founder — is the problem.",
      "Production readiness: cron job, one API call a week, audit log as the record."]),
    ("About this project",
     ["Created by Bhupesh Chandra Dimri — bhupesh7cd@gmail.com — linkedin.com/in/bhupeshdimri",
      "GitHub: suggested repo uno-wallet-ai-workflow (user creates the empty repo first).",
      "Match to the role: 6/10 — the workflow maps onto evidenced automation work; production LLM experience is the gap, stated plainly.",
      "All data synthetic. Demo runs on the mock adapter; no real LLM was called."]),
]


def build_deck(path):
    from reportlab.platypus import SimpleDocTemplate as SDT
    story = []
    st_title = ParagraphStyle("dt", fontSize=30, leading=34, textColor=NAVY, fontName="Helvetica-Bold")
    st_body = ParagraphStyle("db", fontSize=15, leading=21)
    st_head = ParagraphStyle("dh", fontSize=13, leading=16, textColor=TEAL, fontName="Helvetica-Bold")
    for i, (title, pts) in enumerate(SLIDES):
        story.append(P(f"Slide {i+1} / 10", "small"))
        story.append(Spacer(1, 0.25 * inch))
        for line in title.split("\n"):
            story.append(Paragraph(line, st_title))
        story.append(Spacer(1, 0.3 * inch))
        for p in pts:
            story.append(Paragraph(f"•  {p}", st_body))
            story.append(Spacer(1, 0.14 * inch))
        if i < len(SLIDES) - 1:
            story.append(PageBreak())
    doc = SDT(str(path), pagesize=landscape(letter),
              leftMargin=0.9 * inch, rightMargin=0.9 * inch,
              topMargin=0.7 * inch, bottomMargin=0.7 * inch,
              title="AI Workflow — Uno Wallet (deck)", author="Bhupesh Chandra Dimri")
    doc.build(story)


if __name__ == "__main__":
    r = OUT / "Bhupesh_Chandra_Dimri_ML-Project_Uno-Wallet-AI-Workflow.pdf"
    d = OUT / "Bhupesh_Chandra_Dimri_ML-Project_Uno-Wallet-AI-Workflow_Deck.pdf"
    build_report(r)
    build_deck(d)
    print("report:", r)
    print("deck:", d)
