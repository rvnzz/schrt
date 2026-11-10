import json
import re
import uuid
from typing import Any, Dict, List, Optional, Tuple

import httpx

from app.config import settings
from app.services.ai_evidence import missing_evidence_hints, review_reason

OK = "ok"
MANUAL_REVIEW = "manual_review"

# Модель может назвать вердикт по-разному или использовать старый формат ответа
_VERDICT_ALIASES = {
    "ok": OK,
    "grade": OK,
    "graded": OK,
    "manual": MANUAL_REVIEW,
    "manual_review": MANUAL_REVIEW,
    "manual-review": MANUAL_REVIEW,
    "review": MANUAL_REVIEW,
    "needs_review": MANUAL_REVIEW,
    "needs_review_manual": MANUAL_REVIEW,
}

_TRUTHY = {"true", "1", "yes", "да", "y"}


class AIGradingError(Exception):
    pass


def _build_content_parts(
    prompt_text: str,
    images: List[Tuple[str, str]],
    max_images: int,
) -> Tuple[List[Dict[str, Any]], int]:
    """Собирает content для запроса. Возвращает части и число переданных изображений."""
    parts: List[Dict[str, Any]] = [{"type": "text", "text": prompt_text}]
    sent = 0
    for _, b64 in images[:max_images]:
        parts.append({"type": "image_url", "image_url": {"url": b64}})
        sent += 1
    return parts, sent


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


def _soft_grade(grade: Any) -> Optional[int]:
    """Оценка «как предложила модель» — без исключения на мусоре."""
    if grade is None or isinstance(grade, bool):
        return None
    try:
        value = int(grade)
    except (TypeError, ValueError):
        return None
    return value if value in (2, 3, 4, 5) else None


def _normalize_missing(value: Any) -> List[str]:
    if isinstance(value, str):
        items = re.split(r"[;,\n]+", value)
    elif isinstance(value, (list, tuple)):
        items = [str(item) for item in value]
    else:
        items = []
    return [item.strip() for item in items if item and item.strip()][:5]


def _manual_verdict(parsed: Dict[str, Any], feedback: str) -> bool:
    """Вердикт из ответа: поле verdict, флаги manual_review или жалоба в тексте."""
    verdict = parsed.get("verdict")
    if isinstance(verdict, str):
        normalized = re.sub(r"[^a-z_-]", "", verdict.strip().lower())
        mapped = _VERDICT_ALIASES.get(normalized)
        if mapped is not None:
            return mapped == MANUAL_REVIEW

    for key in ("manual_review", "needs_review", "requires_manual_review", "need_manual_review"):
        flag = parsed.get(key)
        if isinstance(flag, str):
            if flag.strip().lower() in _TRUTHY:
                return True
        elif isinstance(flag, bool) and flag:
            return True

    # Ответ по старому формату, где вердикта нет: жалоба на отсутствие скриншотов
    return bool(missing_evidence_hints(feedback, limit=1))


def _parse_response(parsed: Dict[str, Any]) -> Dict[str, Any]:
    feedback = str(parsed.get("feedback") or "")
    missing = _normalize_missing(parsed.get("missing") or parsed.get("missing_evidence"))
    proposed = _soft_grade(parsed.get("grade"))

    if _manual_verdict(parsed, feedback):
        reason = review_reason(missing, feedback) or "Модель не смогла увидеть обязательные материалы работы"
        if proposed is not None:
            reason = f"{reason} (предположительная оценка модели: {proposed})"
        return {
            "verdict": MANUAL_REVIEW,
            "grade": None,
            "proposed_grade": proposed,
            "feedback": feedback,
            "missing": missing,
            "reason": reason[:500],
        }

    grade = _validate_grade(parsed.get("grade"))
    return {
        "verdict": OK,
        "grade": grade,
        "proposed_grade": grade,
        "feedback": feedback,
        "missing": [],
        "reason": "",
    }


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
    parts, sent_images = _build_content_parts(
        prompt_text, images, max(1, settings.ai_max_images)
    )
    payload = {
        "model": settings.opencode_go_model,
        "messages": [{"role": "user", "content": parts}],
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

    result = _parse_response(parsed)
    result["images_total"] = len(images)
    result["images_sent"] = sent_images
    return result
