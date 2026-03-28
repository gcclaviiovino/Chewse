You are generating practical product suggestions grounded in retrieved Open Food Facts snippets.

Product payload:
{product_json}

User query:
{user_query}

Retrieved docs:
{docs_json}

Return strict JSON with:
{
  "suggestions": [
    {
      "title": "short title",
      "suggestion": "practical suggestion",
      "rationale": "why this helps",
      "sources": ["barcode or source id"]
    }
  ]
}

Rules:
- Suggestions must be practical and grounded in the retrieved docs.
- If docs are weak, return an empty suggestions array.
