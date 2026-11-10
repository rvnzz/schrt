"""Признаки того, что в работе не нашлось обязательных материалов.

Логика нужна в двух местах:

* воркер подстрахует модель, которая ответила по-старому (без флага `verdict`)
  и просто пожаловалась на отсутствующие скриншоты в комментарии;
* дашборд находит старые работы со статусом `done`, где модель уже написала
  «скриншоты не найдены», но оценку всё равно опубликовал — их перепроверяют
  одной кнопкой.

Совпадение ищем внутри одного предложения: нужно существо материала
(скриншот, изображение, схема) и указание на его отсутствие. Иначе «ошибок не
найдено» или «скриншоты качественные» дали бы ложную ручную проверку.
"""

import re
from typing import List

# О каких доказательствах идёт речь в задании — берём основы слов, чтобы
# ловить падежи («снимков», «изображений», «на скриншоте»)
EVIDENCE_TERMS = (
    r"скриншот\w*",
    r"скрин\w*",
    r"изображ\w*",
    r"картин\w*",
    r"снимк\w*",
    r"фот\w*",
    r"иллюстрац\w*",
    r"рисун\w*",
    r"диаграмм\w*",
    r"блок-?схем\w*",
    r"схем\w*",
    r"график\w*",
)

# Как модель сообщает, что материала нет или его не видно
ABSENCE_TERMS = (
    r"не\s+найд\w*",
    r"не\s+обнаруж\w*",
    r"не\s+приложен\w*",
    r"не\s+прикреп\w*",
    r"не\s+предоставлен\w*",
    r"не\s+видн\w*",
    r"не\s+видно",
    r"не\s+различим\w*",
    r"не\s+чита\w*",
    r"не\s+загру\w*",
    r"не\s+откр\w*",
    r"не\s+переда\w*",
    r"не\s+показан\w*",
    r"отсутству\w*",
    r"пуст\w*",
    r"нет\s+в\s+работ\w*",
)

# Режем только по концам предложений: «Скриншоты этапов 2-5: не найдено» и
# «Скриншоты, требуемые заданием, отсутствуют» — одна фраза. Ложные срабатывания
# на перечисления («скриншоты отличные, замечаний нет») отсекает соседство слов ниже.
_SENTENCE_SPLIT = re.compile(r"[.!?\n]+")
_EVIDENCE_RE = re.compile("|".join(EVIDENCE_TERMS), re.IGNORECASE)
_ABSENCE_RE = re.compile("|".join(ABSENCE_TERMS), re.IGNORECASE)

# Основы тех же слов — для оборотов «нет скриншотов» и «скриншотов нет»,
# где отрицание стоит до или сразу после названия материала. Между словами
# только пробелы: «скриншоты отличные, замечаний нет» совпадением не считается.
_EVIDENCE_STEMS = tuple(term.replace(r"\w*", "") for term in EVIDENCE_TERMS)
_STEM_ALT = "|".join(_EVIDENCE_STEMS)
# «нет обязательных скриншотов», «не хватает изображений»
_NO_BEFORE_EVIDENCE = re.compile(
    rf"(?:нет|не\s+хватает|не\s+хватило|не\s+ста\w+)(?:\s+[\w-]+){{0,2}}\s+(?:{_STEM_ALT})",
    re.IGNORECASE,
)
# «скриншотов в работе нет», «изображений нет»
_NO_AFTER_EVIDENCE = re.compile(
    rf"(?:{_STEM_ALT})\w*(?:\s+[\w-]+){{0,3}}\s+нет\b",
    re.IGNORECASE,
)

MAX_HINTS = 3
HINT_LENGTH = 220


def _sentence_complains(sentence: str) -> bool:
    if _NO_BEFORE_EVIDENCE.search(sentence) or _NO_AFTER_EVIDENCE.search(sentence):
        return True
    return bool(_EVIDENCE_RE.search(sentence) and _ABSENCE_RE.search(sentence))


def missing_evidence_hints(text: str, limit: int = MAX_HINTS) -> List[str]:
    """Фразы из текста, где говорится об отсутствующих скриншотах/изображениях."""
    if not text:
        return []

    hints: List[str] = []
    seen: set[str] = set()
    for chunk in _SENTENCE_SPLIT.split(text):
        sentence = " ".join(chunk.split())
        if not sentence:
            continue
        if _sentence_complains(sentence):
            key = sentence.lower()
            if key in seen:
                continue
            seen.add(key)
            hints.append(sentence[:HINT_LENGTH])
            if len(hints) >= limit:
                break
    return hints


def looks_like_missing_evidence(text: str) -> bool:
    """True, если текст похож на жалобу «не нашёл скриншоты/изображения»."""
    return bool(missing_evidence_hints(text, limit=1))


def review_reason(missing: List[str], feedback: str = "") -> str:
    """Короткая причина ручной проверки: список от модели или фраза из комментария."""
    cleaned = [item.strip() for item in missing if item and item.strip()]
    if cleaned:
        return "Не найдено в работе: " + "; ".join(cleaned[:MAX_HINTS])[:500]
    hints = missing_evidence_hints(feedback, limit=1)
    if hints:
        return f"Модель не нашла материалы: {hints[0]}"[:500]
    return ""
