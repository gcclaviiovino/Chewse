You are generating a concise user-facing explanation for a deterministic score.

Mode: {mode}
Product payload:
{product_json}

Score payload:
{score_json}

Return strict JSON with:
{
  "explanation_short": "one short paragraph",
  "why_bullets": [
    "Fact: ...",
    "Assumption: ...",
    "Advice: ..."
  ]
}

Rules:
- Keep the explanation concise and useful.
- Separate facts, assumptions, and advice in the bullets.
- Do not invent unavailable product facts.
