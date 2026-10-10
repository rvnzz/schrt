from typing import List, Optional, Tuple

from app.services.file_text import ExtractedContent


def build_grading_prompt(
    assignment_title: str,
    brief_md: str,
    author_name: str,
    is_group_work: bool,
    group_members: Optional[List[dict]],
    extracted: ExtractedContent,
) -> str:
    members_text = ""
    if is_group_work and group_members:
        members_text = "\n".join(
            f"- {m.get('first_name', '')} {m.get('last_name', '')}" for m in group_members
        )

    notes_text = "\n".join(f"- {n}" for n in extracted.notes) if extracted.notes else "нет"

    prompt = f"""Ты — строгий преподаватель, проверяющий учебное задание.

## Задание
Название: {assignment_title}

{brief_md}

## Сданная работа
Автор (основной): {author_name}
{"Работа групповая. Участники:\n" + members_text if is_group_work else "Работа индивидуальная."}

### Текстовая часть работы
{extracted.text or "(текстовое содержимое отсутствует)"}

### Примечания к файлу
{notes_text}

## Инструкция
Оцени работу по шкале от 2 до 5:
- 5 — отлично, задание выполнено полностью и качественно
- 4 — хорошо, небольшие недочёты
- 3 — удовлетворительно, есть заметные проблемы
- 2 — неудовлетворительно, задание не выполнено

Если в работе есть изображения (скриншоты, блок-схемы, диаграммы), учитывай их содержимое при оценке.

Ответь СТРОГО в формате JSON без Markdown-разметки:
{{"grade": <2-5>, "feedback": "<развёрнутое пояснение к оценке на русском языке>"}}
"""
    return prompt
