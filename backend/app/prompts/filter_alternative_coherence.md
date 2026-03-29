You are validating whether shortlisted products are plausible real-world substitutes for the base product.

Base product:
{product_json}

Shortlisted candidates:
{docs_json}

Return strict JSON with:
{
  "accepted_sources": ["candidate barcode"],
  "rejected_sources": [
    {
      "source": "candidate barcode",
      "reason": "short explanation"
    }
  ]
}

Rules:
- Accept a candidate only if it is a believable substitute in everyday shopping, use, and product function.
- Prioritize same product use-case, same eating occasion, and similar product type.
- Reject candidates that are semantically far even if they have a better Eco-Score.
- Example: a chocolate spread and a tomato puree are not substitutes.
- Only use source ids that appear in the shortlisted candidates.
