from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional


@dataclass
class CategoryPreference:
    category: str
    markdown: str


class PreferencesMemoryService:
    """Simple markdown-based preference memory for MVP usage."""

    _SECTION_PATTERN = re.compile(r"^##\s*category:\s*(.+?)\s*$", re.IGNORECASE)

    def __init__(self, backend_dir: Path) -> None:
        self.base_dir = backend_dir / "data" / "agent_memory"
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def load_category_preferences(self, user_id: str, category: str) -> Optional[str]:
        sections = self._read_sections(user_id)
        return sections.get(self._normalize_category(category))

    def upsert_category_preferences(self, user_id: str, category: str, markdown_block: str) -> None:
        if not markdown_block or not markdown_block.strip():
            return
        sections = self._read_sections(user_id)
        normalized_category = self._normalize_category(category)
        sections[normalized_category] = self._normalize_markdown_block(markdown_block)
        self._write_sections(user_id, sections)

    def has_category_preferences(self, user_id: str, category: str) -> bool:
        data = self.load_category_preferences(user_id, category)
        return bool(data and data.strip())

    @staticmethod
    def _normalize_category(category: str) -> str:
        normalized = (category or "unknown").strip().lower()
        normalized = normalized.replace("_", "-")
        normalized = re.sub(r"\s+", "-", normalized)
        return normalized or "unknown"

    @staticmethod
    def _normalize_user_id(user_id: str) -> str:
        candidate = (user_id or "default").strip().lower()
        candidate = re.sub(r"[^a-z0-9_-]", "_", candidate)
        return candidate or "default"

    @staticmethod
    def _normalize_markdown_block(markdown_block: str) -> str:
        lines = [line.rstrip() for line in markdown_block.splitlines() if line.strip()]
        return "\n".join(lines)

    def _memory_path(self, user_id: str) -> Path:
        safe_user_id = self._normalize_user_id(user_id)
        return self.base_dir / "{}.md".format(safe_user_id)

    def _read_sections(self, user_id: str) -> Dict[str, str]:
        path = self._memory_path(user_id)
        if not path.exists():
            return {}

        sections: Dict[str, str] = {}
        current_key: Optional[str] = None
        current_lines: list[str] = []

        for raw_line in path.read_text(encoding="utf-8").splitlines():
            header_match = self._SECTION_PATTERN.match(raw_line.strip())
            if header_match:
                if current_key and current_lines:
                    sections[current_key] = "\n".join(current_lines).strip()
                current_key = self._normalize_category(header_match.group(1))
                current_lines = []
                continue
            if current_key is not None:
                current_lines.append(raw_line)

        if current_key and current_lines:
            sections[current_key] = "\n".join(current_lines).strip()

        return sections

    def _write_sections(self, user_id: str, sections: Dict[str, str]) -> None:
        path = self._memory_path(user_id)
        lines: list[str] = ["# User preferences memory", ""]
        lines.append("Last updated: {}".format(datetime.now(timezone.utc).isoformat()))
        lines.append("")

        for key in sorted(sections.keys()):
            value = (sections[key] or "").strip()
            if not value:
                continue
            lines.append("## category: {}".format(key))
            lines.append(value)
            lines.append("")

        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")
