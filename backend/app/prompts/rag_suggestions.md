You are generating practical product alternatives grounded in shortlisted Open Food Facts candidate products.

Product payload:
{product_json}

User query:
{user_query}

Retrieved candidate products:
{docs_json}

Return strict JSON with:
{
  "suggestions": [
    {
      "title": "short title",
      "suggestion": "practical alternative suggestion",
      "rationale": "why this candidate is more sustainable and still similar",
      "sources": ["candidate barcode"]
    }
  ]
}

Rules:
- Only use candidate barcodes that appear in the retrieved candidate products.
- Prioritize alternatives that remain close in category, ingredients, format, and usage.
- Prefer candidates with a better Eco-Score and lower emissions when available.
- If the shortlist is weak or too different from the original product, return an empty suggestions array.
