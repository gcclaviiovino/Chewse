Extract product information from the provided food image and optional user notes.

Return strict JSON only with this schema:
{
  "product_name": "string | null",
  "brand": "string | null",
  "barcode": "string | null",
  "ingredients_text": "string | null",
  "nutriments": {
    "energy-kcal_100g": "number | null",
    "fat_100g": "number | null",
    "saturated-fat_100g": "number | null",
    "carbohydrates_100g": "number | null",
    "sugars_100g": "number | null",
    "fiber_100g": "number | null",
    "proteins_100g": "number | null",
    "salt_100g": "number | null"
  },
  "packaging": "string | null",
  "origins": "string | null",
  "labels_tags": ["string"],
  "categories_tags": ["string"],
  "quantity": "string | null",
  "confidence": 0.0
}

Rules:
- Read only what is visible or directly inferable from the image.
- If a field is unknown, set it to null or [].
- Do not add prose outside JSON.
- User notes: {user_notes}
- Image path reference: {image_path}
