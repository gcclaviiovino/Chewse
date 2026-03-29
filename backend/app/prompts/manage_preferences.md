You update a user's saved food preferences for one product category.

Category: {category}
Current saved preferences for this category:
{current_preferences_markdown}

Latest user message:
{user_message}

Task:
- Decide whether the latest user message contains actionable preference updates for this category.
- Apply the new message against the current saved preferences.
- Support adding preferences, removing preferences, replacing them, or explicitly setting that the user has no preferences.
- If the message is generic chit-chat or does not change preferences, do not update memory.

Output JSON only with this exact schema:
{
  "should_update": true,
  "final_preferences_markdown": "- vegan\n- no dairy"
}

Rules:
- `final_preferences_markdown` must be markdown bullets, one preference per line.
- Use short normalized labels such as `- vegan`, `- vegetarian`, `- no dairy`, `- no gluten`, `- no nuts`, `- no fish`, `- no beef`, `- no pork`, `- no palm oil`, `- no sugar`, `- senza plastica`, `- solo bio`, `- nessuna preferenza`.
- If the user explicitly says they have no preferences, return only `- nessuna preferenza`.
- If nothing should change, return:
{
  "should_update": false,
  "final_preferences_markdown": ""
}
