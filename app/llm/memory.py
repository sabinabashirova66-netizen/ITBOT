"""Summary Buffer Memory: последние 5 сообщений дословно, остальное сжимается LLM."""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

RECENT_WINDOW = 5


@dataclass
class ConversationMemory:
    recent_messages: list[dict] = field(default_factory=list)
    summary: str = ""

    def add_message(self, role: str, content: str) -> None:
        self.recent_messages.append({"role": role, "content": content})

    def get_recent_text(self) -> str:
        return "\n".join(
            f"{m['role'].capitalize()}: {m['content']}"
            for m in self.recent_messages[-RECENT_WINDOW:]
        )

    def should_summarize(self) -> bool:
        return len(self.recent_messages) > RECENT_WINDOW

    def get_history_for_summary(self) -> str:
        older = self.recent_messages[:-RECENT_WINDOW]
        if not older:
            return ""
        return "\n".join(
            f"{m['role'].capitalize()}: {m['content']}" for m in older
        )

    def apply_summary(self, new_summary: str) -> None:
        self.summary = new_summary
        self.recent_messages = self.recent_messages[-RECENT_WINDOW:]

    def to_dict(self) -> dict:
        return {
            "recent_messages": self.recent_messages,
            "summary": self.summary,
        }

    @classmethod
    def from_dict(cls, data: dict) -> ConversationMemory:
        obj = cls()
        obj.recent_messages = data.get("recent_messages", [])
        obj.summary = data.get("summary", "")
        return obj

    def serialize(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False)

    @classmethod
    def deserialize(cls, raw: str) -> ConversationMemory:
        try:
            return cls.from_dict(json.loads(raw))
        except Exception:
            return cls()
