import json
import re
import uuid
from typing import Any, Dict, List, Optional, Tuple

import httpx

from app.config import settings


class AIGradingError(Exception):
    pass


def _build_content_parts(prompt_text: str, images: List[Tuple[str, str]]) -> List[Dict[str, Any]]:
    parts: List[Dict[str, Any]] = [{"type": "text", "text": prompt_text}]
    for _, b64 in images[:10]:
        parts.append({"type": "image_url", "image_url": {"url": b64}})
    return parts


def _extract_json(text: str) -> Optional[Dict[str, Any]]:
    text = text.strip()

    # Try fenced code block
    match = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if match:
        candidate = match.group(1).strip()
    else:
        candidate = text

    # Try first {...} object
    match = re.search(r"\{[\s\S]*\}", candidate)
    if match:
        candidate = match.group(0)

    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        return None


def _validate_grade(grade: Any) -> int:
    if isinstance(grade, bool):
        raise AIGradingError(f"Invalid grade type: bool")
    try:
        value = int(grade)
    except (TypeError, ValueError):
        raise AIGradingError(f"Grade is not an integer: {grade}")
    if value not in (2, 3, 4, 5):
        raise AIGradingError(f"Grade out of 2-5 range: {value}")
    return value


async def grade_submission(
    prompt_text: str,
    images: List[Tuple[str, str]],
) -> Dict[str, Any]:
    if not settings.ai_enabled:
        raise AIGradingError("AI grading is disabled: OPENCODE_GO_API_KEY is not set")

    url = f"{settings.opencode_go_base_url.rstrip('/')}/chat/completions"
    headers = {
        "Authorization": f"Bearer {settings.opencode_go_api_key}",
        "Content-Type": "application/json",
        "x-opencode-session": str(uuid.uuid4()),
    }
    payload = {
        "model": settings.opencode_go_model,
        "messages": [
            {
                "role": "user",
                "content": _build_content_parts(prompt_text, images),
            }
        ],
        "temperature": 0.2,
        "max_tokens": 4096,
    }

    async with httpx.AsyncClient(timeout=300) as client:
        response = await client.post(url, headers=headers, json=payload)
        response.raise_for_status()
        data = response.json()

    choices = data.get("choices") or []
    if not choices:
        raise AIGradingError("Empty choices in model response")

    message = choices[0].get("message", {})
    content = message.get("content") or ""

    parsed = _extract_json(content)
    if parsed is None:
        raise AIGradingError(f"Could not parse JSON from model response: {content[:500]}")

    grade = _validate_grade(parsed.get("grade"))
    feedback = str(parsed.get("feedback") or "")

    return {"grade": grade, "feedback": feedback}
