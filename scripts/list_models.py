"""List the Gemini models this API key can actually call.

Model availability changes, and a name that worked last month can return 404
for a newly created key. Rather than hardcoding a guess, run this and put a
name it prints into .env.

Usage:
    python scripts/list_models.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx  # noqa: E402

from app.core.config import settings  # noqa: E402

ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models"


def main() -> None:
    if not settings.google_api_key:
        raise SystemExit("GOOGLE_API_KEY is not set in .env")

    response = httpx.get(
        ENDPOINT,
        params={"key": settings.google_api_key, "pageSize": "200"},
        timeout=30,
    )
    response.raise_for_status()

    models = [
        m["name"].removeprefix("models/")
        for m in response.json().get("models", [])
        if "generateContent" in m.get("supportedGenerationMethods", [])
    ]

    flash = sorted(n for n in models if "flash" in n)
    other = sorted(n for n in models if "flash" not in n)

    print(f"\n{len(models)} models support generateContent with this key.\n")
    print("FLASH models (fast and cheap - pick your primary and fallback here):")
    for name in flash:
        print(f"  {name}")
    print("\nOther models:")
    for name in other[:15]:
        print(f"  {name}")

    print("\nCurrently configured:")
    print(f"  LLM_MODEL          = {settings.llm_model}"
          f"   {'OK' if settings.llm_model in models else '<-- NOT AVAILABLE'}")
    print(f"  LLM_FALLBACK_MODEL = {settings.llm_fallback_model}"
          f"   {'OK' if settings.llm_fallback_model in models else '<-- NOT AVAILABLE'}")


if __name__ == "__main__":
    main()
