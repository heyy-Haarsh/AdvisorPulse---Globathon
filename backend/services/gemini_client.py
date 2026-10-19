"""
Gemini API client for Meeting Intelligence.

Secrets: GEMINI_API_KEY (backend only). Never expose to the frontend.
Optional: GEMINI_MODEL (default gemini-2.0-flash)
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")
load_dotenv(ROOT / "backend" / ".env")

DEFAULT_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")


class GeminiNotConfigured(RuntimeError):
    pass


class GeminiError(RuntimeError):
    pass


def api_key() -> str | None:
    key = (os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or "").strip()
    return key or None


def is_configured() -> bool:
    return bool(api_key())


def status() -> dict[str, Any]:
    return {
        "provider": "google_gemini",
        "configured": is_configured(),
        "model": DEFAULT_MODEL,
        "env_vars": ["GEMINI_API_KEY", "GEMINI_MODEL"],
        "note": (
            "Set GEMINI_API_KEY in .env for transcription and minutes generation. "
            "Preparation briefs work without Gemini using deterministic analytics."
        ),
    }


def _client():
    key = api_key()
    if not key:
        raise GeminiNotConfigured(
            "GEMINI_API_KEY is not set. Add it to .env to enable Gemini transcription and minutes."
        )
    try:
        import google.generativeai as genai  # type: ignore
    except ImportError as e:
        raise GeminiError("google-generativeai package is not installed") from e
    genai.configure(api_key=key)
    return genai


def _extract_json(text: str) -> Any:
    text = (text or "").strip()
    if not text:
        raise GeminiError("Empty Gemini response")
    # Strip markdown fences
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if fence:
        text = fence.group(1).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Try first { ... } or [ ... ]
        m = re.search(r"(\{[\s\S]*\}|\[[\s\S]*\])", text)
        if not m:
            raise GeminiError("Gemini response was not valid JSON")
        return json.loads(m.group(1))


def generate_json(prompt: str, *, system: str | None = None, temperature: float = 0.2) -> Any:
    genai = _client()
    model = genai.GenerativeModel(
        DEFAULT_MODEL,
        system_instruction=system
        or (
            "You are an advisor meeting-intelligence assistant for Indian wealth management. "
            "Return ONLY valid JSON matching the requested schema. "
            "Never invent portfolio numbers, meetings, or client facts not present in the input. "
            "If evidence is weak, mark evidence_status as Limited or Insufficient. "
            "Do not treat silence as client agreement."
        ),
    )
    resp = model.generate_content(
        prompt,
        generation_config={
            "temperature": temperature,
            "response_mime_type": "application/json",
        },
    )
    text = getattr(resp, "text", None) or ""
    if not text and getattr(resp, "candidates", None):
        parts = resp.candidates[0].content.parts
        text = "".join(getattr(p, "text", "") or "" for p in parts)
    return _extract_json(text)


def transcribe_audio_file(path: Path, *, mime_type: str | None = None) -> dict[str, Any]:
    """
    Transcribe an audio file with Gemini multimodal.
    Returns { full_text, segments: [{start_time, end_time, speaker_id, text}] }
    """
    genai = _client()
    if not path.exists():
        raise GeminiError(f"Audio file not found: {path}")

    mime = mime_type or _guess_mime(path)
    uploaded = genai.upload_file(path=str(path), mime_type=mime)
    model = genai.GenerativeModel(DEFAULT_MODEL)
    prompt = (
        "Transcribe this advisor–client meeting audio accurately. "
        "Return JSON with keys: full_text (string), segments (array of objects with "
        "start_time (mm:ss or HH:mm:ss string), end_time, speaker_id (Speaker 1/2…), text). "
        "Do not invent content that is not audible. If unintelligible, use [inaudible]. "
        "Do not assume Speaker 1 is the advisor."
    )
    resp = model.generate_content(
        [prompt, uploaded],
        generation_config={"temperature": 0.1, "response_mime_type": "application/json"},
    )
    text = getattr(resp, "text", None) or ""
    data = _extract_json(text)
    if isinstance(data, str):
        data = {"full_text": data, "segments": [{"start_time": "00:00", "end_time": "", "speaker_id": "Speaker 1", "text": data}]}
    if "full_text" not in data and "segments" in data:
        data["full_text"] = " ".join(s.get("text", "") for s in data["segments"])
    data["provider"] = "google_gemini"
    data["model"] = DEFAULT_MODEL
    return data


def _guess_mime(path: Path) -> str:
    ext = path.suffix.lower()
    return {
        ".webm": "audio/webm",
        ".wav": "audio/wav",
        ".mp3": "audio/mpeg",
        ".m4a": "audio/mp4",
        ".ogg": "audio/ogg",
        ".flac": "audio/flac",
    }.get(ext, "audio/webm")
