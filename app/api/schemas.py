"""API request and response models.

Every field the API accepts is declared and bounded here. Validation happens at
the edge, before a value reaches the agent, so a malformed or oversized request
is rejected by FastAPI with a 422 rather than becoming an odd failure deeper in
the graph.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

MAX_QUESTION_CHARS = 4_000


class ChatRequest(BaseModel):
    """One turn of conversation."""

    message: str = Field(min_length=1, max_length=MAX_QUESTION_CHARS)
    user_id: str = Field(min_length=1, max_length=64)
    session_id: str = Field(default="default", max_length=128)

    @field_validator("message")
    @classmethod
    def reject_control_characters(cls, value: str) -> str:
        """Strip control characters used to smuggle instructions past filters."""
        cleaned = "".join(ch for ch in value if ch == "\n" or ch == "\t" or ch >= " ")
        if not cleaned.strip():
            raise ValueError("message is empty after removing control characters")
        return cleaned.strip()

    @field_validator("user_id")
    @classmethod
    def normalise_user(cls, value: str) -> str:
        return value.strip().lower()


class Citation(BaseModel):
    """A verified source document."""

    doc_id: str
    title: str
    section: str
    department: str
    document_type: str
    created_date: str
    found_by: str
    score: float


class StreamEvent(BaseModel):
    """One newline-delimited JSON event on the chat stream."""

    type: Literal["trace", "token", "citations", "validation", "error", "done"]
    payload: dict[str, Any] = Field(default_factory=dict)


class UserInfo(BaseModel):
    """A selectable user, for the UI's role switcher."""

    user_id: str
    display_name: str
    role: str
    department: str
    permissions: list[str]
    access_levels: list[str]
