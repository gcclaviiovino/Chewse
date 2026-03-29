from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional

from app.services.category_normalizer import canonicalize_category


@dataclass
class CategoryPreference:
    category: str
    markdown: str


class PreferencesMemoryService:
    """Simple markdown-based preference memory for MVP usage."""

    _SECTION_PATTERN = re.compile(r"^##\s*category:\s*(.+?)\s*$", re.IGNORECASE)
    _DEFAULT_NOTE = "Default preference: nessuna preferenza"

    def __init__(self, backend_dir: Path) -> None:
        self.base_dir = backend_dir / "data" / "agent_memory"
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def load_category_preferences(self, user_id: str, category: str) -> Optional[str]:
        sections = self._read_sections(user_id)
        return sections.get(self._normalize_category(category))

    def load_all_preferences(self, user_id: str) -> Dict[str, str]:
        return dict(self._read_sections(user_id))

    def render_memory_document(self, user_id: str) -> Optional[str]:
        sections = self.load_all_preferences(user_id)
        return self._render_sections_document(sections)

    def has_memory_file(self, user_id: str) -> bool:
        return self._memory_path(user_id).exists() or self._nested_memory_path(user_id).exists()

    def ensure_memory_file(self, user_id: str) -> None:
        primary_path = self._memory_path(user_id)
        if primary_path.exists():
            return

        nested_path = self._nested_memory_path(user_id)
        if nested_path.exists():
            sections = self._read_sections_from_path(nested_path)
            if sections:
                self._write_sections(user_id, sections)
                return

        primary_path.parent.mkdir(parents=True, exist_ok=True)
        primary_path.write_text(self._render_sections_file({}, include_default_note=True), encoding="utf-8")

    def upsert_category_preferences(self, user_id: str, category: str, markdown_block: str) -> None:
        if not markdown_block or not markdown_block.strip():
            return
        sections = self._read_sections(user_id)
        normalized_category = self._normalize_category(category)
        sections[normalized_category] = self._normalize_markdown_block(markdown_block)
        self._write_sections(user_id, sections)

    def delete_category_preferences(self, user_id: str, category: str) -> None:
        sections = self._read_sections(user_id)
        normalized_category = self._normalize_category(category)
        if normalized_category not in sections:
            return
        sections.pop(normalized_category, None)
        self._write_sections(user_id, sections)

    def replace_memory_document(self, user_id: str, memory_document: str) -> None:
        sections = self._read_sections_from_text(memory_document)
        self._write_sections(user_id, sections)

    def parse_memory_document(self, memory_document: str) -> Dict[str, str]:
        return self._read_sections_from_text(memory_document)

    def has_category_preferences(self, user_id: str, category: str) -> bool:
        data = self.load_category_preferences(user_id, category)
        return bool(data and data.strip())

    @staticmethod
    def _normalize_category(category: str) -> str:
        normalized = canonicalize_category(category)
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

    def _nested_memory_path(self, user_id: str) -> Path:
        safe_user_id = self._normalize_user_id(user_id)
        return self.base_dir / safe_user_id / "memory.md"

    def _read_sections(self, user_id: str) -> Dict[str, str]:
        primary_path = self._memory_path(user_id)
        nested_path = self._nested_memory_path(user_id)

        if primary_path.exists():
            return self._read_sections_from_path(primary_path)

        if nested_path.exists():
            sections = self._read_sections_from_path(nested_path)
            if sections:
                self._write_sections(user_id, sections)
            return sections

        return {}

    def _read_sections_from_path(self, path: Path) -> Dict[str, str]:
        if not path.exists():
            return {}

        return self._read_sections_from_text(path.read_text(encoding="utf-8"))

    def _read_sections_from_text(self, raw_text: str) -> Dict[str, str]:

        sections: Dict[str, str] = {}
        current_key: Optional[str] = None
        current_lines: list[str] = []

        for raw_line in raw_text.splitlines():
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
        rendered = self._render_sections_file(sections)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(rendered, encoding="utf-8")

    @classmethod
    def _render_sections_document(cls, sections: Dict[str, str]) -> Optional[str]:
        lines: list[str] = []
        for key in sorted(sections.keys()):
            value = (sections[key] or "").strip()
            if not value:
                continue
            lines.append("## category: {}".format(key))
            lines.append(value)
            lines.append("")
        rendered = "\n".join(lines).strip()
        return rendered or None

    @classmethod
    def _render_sections_file(cls, sections: Dict[str, str], include_default_note: bool = False) -> str:
        lines: list[str] = ["# User preferences memory", ""]
        lines.append("Last updated: {}".format(datetime.now(timezone.utc).isoformat()))
        lines.append("")
        if include_default_note and not sections:
            lines.append(cls._DEFAULT_NOTE)
            lines.append("")

        for key in sorted(sections.keys()):
            value = (sections[key] or "").strip()
            if not value:
                continue
            lines.append("## category: {}".format(key))
            lines.append(value)
            lines.append("")

        return "\n".join(lines).strip() + "\n"
