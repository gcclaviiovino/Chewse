You are drafting a deep rationale for a deterministic score.

Mode: {mode}
Product payload:
{product_json}

Score payload:
{score_json}

Return strict JSON with:
{
  "facts": ["short factual statements grounded in product data"],
  "assumptions": ["uncertainties or inferred assumptions"],
  "advice_candidates": ["practical advice candidates"],
  "draft_summary": "deep internal rationale"
}

Rules:
- Facts must be explicitly supported by product data.
- Assumptions must be clearly marked as uncertain.
- Do not change the score.
