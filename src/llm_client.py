"""Pluggable LLM client for the weekly-reporting workflow.

Two adapters, one interface:

- MockLLMAdapter — DETERMINISTIC. Parses the structured prompt text,
  computes week-over-week deltas with plain arithmetic, and assembles the
  memo from templates. It is NOT a language model. The demo runs on this
  adapter. It exists so the workflow, the review gate and the evaluation
  harness can be built, tested and measured without any API key.
- RealAPIAdapter — an OpenAI-compatible chat-completions client. The API
  key is read ONLY from the UNO_LLM_API_KEY environment variable at call
  time. It is NEVER hardcoded, NEVER written to a file, NEVER printed.
  Without the variable set, calling it raises a clear RuntimeError.
  No real LLM call is made anywhere in this project unless the user sets
  the variable themselves and selects this adapter explicitly.

Both adapters return the memo as text with a machine-readable
``##STRUCTURED##`` block that the review gate and the evaluator parse.
The structured block is the contract: prose is for humans, the block is
what gets checked.
"""
import json
import os
import re
import urllib.request

ACCURACY_RISK_THRESHOLD = 90.0

# Order matters: the mock's top-mover tie-break follows this list.
KPI_ORDER = [
    "signups",
    "activations",
    "active_users",
    "transactions",
    "gmv_usd",
    "points_earned",
    "rec_accuracy_pct",
    "failed_recs",
    "support_tickets",
]

KPI_LABELS = {
    "signups": "Signups",
    "activations": "Activations",
    "active_users": "Active users",
    "transactions": "Transactions",
    "gmv_usd": "GMV ($)",
    "points_earned": "Points earned",
    "rec_accuracy_pct": "Recommendation accuracy (%)",
    "failed_recs": "Failed recommendations",
    "support_tickets": "Support tickets",
}

_LINE_RE = re.compile(
    r"^-\s+(\w+):\s+([-\d\.]+|n/a)\s+\(prior:\s+([-\d\.]+|n/a)\)\s*$"
)
_FEEDBACK_RE = re.compile(r"^FEEDBACK\s+(\w+):\s+(.*)$")


def _num(tok):
    if tok == "n/a":
        return None
    try:
        return float(tok)
    except ValueError:
        return None


def _fmt(val):
    if val is None:
        return "n/a"
    if float(val).is_integer():
        return str(int(val))
    return f"{val:.2f}"


def _pct_change(cur, prior):
    if cur is None or prior is None or prior == 0:
        return None
    return (cur - prior) / abs(prior) * 100.0


class LLMClient:
    """Interface: generate(prompt) -> memo text."""

    def generate(self, prompt):
        raise NotImplementedError


class MockLLMAdapter(LLMClient):
    """Deterministic mock. Documented policy (this is the whole 'model'):

    1. Parse the `- metric: value (prior: value)` lines from the prompt.
    2. A negative value in the CURRENT week is a data fault: exclude it
       from every calculation and raise a DATA_QUALITY flag. A negative
       PRIOR value is excluded from the comparison instead (its change
       becomes n/a) and is covered by the MISSING_DATA flag — the fault
       belongs to the prior week's data, not this week's memo.
    3. A missing value ("n/a") stays "n/a" — never invented.
    4. Top mover = largest absolute % change among metrics valid in both
       weeks; ties break by KPI_ORDER (first listed wins).
    5. Flags: RISK_ACCURACY_LOW when rec_accuracy_pct < 90;
       DATA_QUALITY when any value is negative or unparseable;
       MISSING_DATA when any metric is n/a.
    6. Actions are fixed rules keyed to the flags and the top mover.
    """

    name = "mock"

    def generate(self, prompt):
        cur, prior, feedback_themes = self._parse(prompt)
        changes = {}
        issues = []
        for k in KPI_ORDER:
            c, p = cur.get(k), prior.get(k)
            if c is not None and c < 0:
                issues.append(f"DATA_QUALITY: {k} is negative ({_fmt(c)}) — excluded from calculations.")
                cur[k] = None
            if p is not None and p < 0:
                # Prior-week fault: exclude from the comparison, do not
                # flag this week's memo — MISSING_DATA covers the gap.
                prior[k] = None
            changes[k] = _pct_change(cur.get(k), prior.get(k))

        valid = {k: v for k, v in changes.items() if v is not None}
        top_mover = None
        if valid:
            # Near-tie rule: changes within 0.5pp of the largest are tied;
            # the first listed in KPI_ORDER wins. The evaluator applies the
            # same rule, so any tied metric is an acceptable answer.
            best = max(abs(v) for v in valid.values())
            top_mover = next(k for k in KPI_ORDER
                             if valid.get(k) is not None and abs(valid[k]) >= best - 0.5)

        flags = []
        if any("DATA_QUALITY" in i for i in issues):
            flags.append("DATA_QUALITY")
        if any(cur.get(k) is None or prior.get(k) is None for k in KPI_ORDER):
            flags.append("MISSING_DATA")
        acc = cur.get("rec_accuracy_pct")
        if acc is not None and acc < ACCURACY_RISK_THRESHOLD:
            flags.append("RISK_ACCURACY_LOW")

        top_theme = None
        if feedback_themes:
            counts = {}
            for t in feedback_themes:
                counts[t] = counts.get(t, 0) + 1
            top_theme = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[0][0]

        lines = ["# Weekly Performance Memo (AI draft — requires human review)",
                 ""]
        lines.append("## Headline")
        if top_mover:
            direction = "up" if changes[top_mover] > 0 else "down"
            lines.append(
                f"{KPI_LABELS[top_mover]} moved the most this week: "
                f"{direction} {abs(changes[top_mover]):.1f}% "
                f"({_fmt(cur[top_mover])} vs {_fmt(prior[top_mover])}).")
        else:
            lines.append("No week-over-week comparison was possible — no metric is valid in both weeks.")
        lines.append("")
        lines.append("## KPI table")
        for k in KPI_ORDER:
            ch = changes[k]
            ch_s = f"{ch:+.1f}%" if ch is not None else "n/a"
            lines.append(f"- {KPI_LABELS[k]}: {_fmt(cur.get(k))} (prior {_fmt(prior.get(k))}, {ch_s})")
        lines.append("")
        lines.append("## Top insight")
        if top_mover:
            lines.append(
                f"The largest move is {KPI_LABELS[top_mover]} "
                f"({changes[top_mover]:+.1f}% WoW). Check what drove it before acting on it.")
        else:
            lines.append("No insight available — see data-quality flags.")
        lines.append("")
        lines.append("## Risks and flags")
        if flags:
            for f in flags:
                lines.append(f"- {f}")
            for i in issues:
                lines.append(f"- {i}")
        else:
            lines.append("- None. All metrics present, valid, and within thresholds.")
        if top_theme:
            lines.append(f"- Top user-feedback theme this week: {top_theme}.")
        lines.append("")
        lines.append("## Recommended actions")
        if "RISK_ACCURACY_LOW" in flags:
            lines.append("- Investigate recommendation misses: pull the failed-recommendation list and find the pattern before the next release.")
        if "DATA_QUALITY" in flags:
            lines.append("- Fix the source data fault before publishing any number from this week.")
        if "MISSING_DATA" in flags:
            lines.append("- Chase the missing metric from its owner; do not publish a memo with 'n/a' in the headline table without noting it.")
        if top_mover and changes[top_mover] is not None and changes[top_mover] < -5:
            lines.append(f"- {KPI_LABELS[top_mover]} fell more than 5% — find the cause (one cause, not five) before deciding a response.")
        if not flags and top_mover:
            lines.append("- No urgent action. Keep the current plan and watch the top mover next week.")
        lines.append("")
        lines.append("##STRUCTURED##")
        for k in KPI_ORDER:
            lines.append(f"{k}: {_fmt(cur.get(k))}")
            ch = changes[k]
            lines.append(f"{k}_change_pct: {ch:.1f}" if ch is not None else f"{k}_change_pct: n/a")
        lines.append(f"top_mover: {top_mover if top_mover else 'n/a'}")
        lines.append(f"flags: {','.join(flags) if flags else 'none'}")
        lines.append(f"top_feedback_theme: {top_theme if top_theme else 'n/a'}")
        return "\n".join(lines)

    @staticmethod
    def _parse(prompt):
        cur, prior, themes = {}, {}, []
        for line in prompt.splitlines():
            m = _LINE_RE.match(line.strip())
            if m:
                cur[m.group(1)] = _num(m.group(2))
                prior[m.group(1)] = _num(m.group(3))
                continue
            fm = _FEEDBACK_RE.match(line.strip())
            if fm:
                themes.append(fm.group(1))
        return cur, prior, themes


class RealAPIAdapter(LLMClient):
    """OpenAI-compatible chat completions. Key from env only.

    Env vars:
      UNO_LLM_API_KEY   (required) — the API key. Never hardcoded.
      UNO_LLM_BASE_URL  (optional) — default https://api.openai.com/v1
      UNO_LLM_MODEL     (optional) — default gpt-4o-mini
    """

    name = "real-api"

    def __init__(self, model=None, base_url=None, timeout=60):
        self.model = model or os.environ.get("UNO_LLM_MODEL", "gpt-4o-mini")
        self.base_url = (base_url or os.environ.get("UNO_LLM_BASE_URL", "https://api.openai.com/v1")).rstrip("/")
        self.timeout = timeout

    def _api_key(self):
        key = os.environ.get("UNO_LLM_API_KEY")
        if not key:
            raise RuntimeError(
                "UNO_LLM_API_KEY is not set. Set the environment variable to "
                "use the real API adapter; the demo runs on the mock adapter "
                "and never needs a key."
            )
        return key

    def build_request(self, prompt):
        """Return (url, headers, body-bytes) — testable without network."""
        key = self._api_key()
        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        }
        body = json.dumps({
            "model": self.model,
            "temperature": 0.2,
            "messages": [
                {"role": "system",
                 "content": ("You are a careful business analyst. Write a weekly "
                             "performance memo from the data given. Never invent a "
                             "number. If a metric is missing, write 'n/a'. End the "
                             "memo with a ##STRUCTURED## block listing each metric, "
                             "its week-over-week % change, the top mover, flags, and "
                             "the top feedback theme.")},
                {"role": "user", "content": prompt},
            ],
        }).encode("utf-8")
        return url, headers, body

    def generate(self, prompt):
        url, headers, body = self.build_request(prompt)
        req = urllib.request.Request(url, data=body, headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
        return payload["choices"][0]["message"]["content"]
