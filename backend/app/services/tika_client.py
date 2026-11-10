"""Клиент Apache Tika — промышленный экстрактор содержимого документов.

Нужен для двух классов проблем, которые python-ридеры не решают:

* старые форматы (`.doc` = OLE2 compound) и редкие (rtf, pages, wordperfect) —
  python-docx их не открывает вообще, воркер получал пустоту;
* нестандартная раскладка пакета: имена и расположение частей Tika берёт из
  связной модели документа, а не из угадывания путей в zip.

Один запрос `PUT /unpack` возвращает zip (Frictionless-пакет):

* `rmeta.json` — метаданные и `tk:content` главного документа (markdown, где
  скриншоты стоят на своих местах: `1. ![](embedded:image3.png)`);
* `datapackage.json` — ресурсы с `path`, `mediatype` и `tk:resource-name`;
* `unpacked/1.png` … — байты самих изображений.

`tk:resource-name` совпадает со ссылкой в markdown, поэтому картинки можно
вернуть в порядке документа, а не в порядке обхода архива.

Tika — не граница безопасности: серверу можно доверять только вызывающего, поэтому
в compose он закрыт во внутренней сети и снаружи не публикуется.
"""

import base64
import io
import json
import logging
import re
import zipfile
from urllib.parse import quote
from typing import Any, Dict, List, Optional, Tuple

import httpx

from app.config import settings
from app.services.file_text import IMAGE_EXTENSIONS, ExtractedContent, resize_image

logger = logging.getLogger(__name__)

# ![](embedded:image9.png) — ссылка Tika на вложенный ресурс
_EMBEDDED_REF = re.compile(r"!\[\]\(embedded:([^)]+)\)")
# поля, в которых Tika пишет о проблемах разбора
_EXCEPTION_KEYS = ("tk:exception:container-exception", "tk:exception:embedded-exception")
MAX_NOTES = 6


def enabled() -> bool:
    return bool(settings.tika_url.strip())


def _endpoint(path: str) -> str:
    return f"{settings.tika_url.rstrip('/')}/{path.lstrip('/')}"


def _unpack_zip(payload: bytes, filename: str) -> Optional[Dict[str, bytes]]:
    """PUT /unpack → словарь {имя файла в zip: байты}. None, если Tika не ответила."""
    # Имя файла — только подсказка, и оно бывает кириллическим: кодируем по RFC 5987,
    # иначе httpx не сможет отправить заголовок в ascii
    headers = {"Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename, safe='')}"}
    try:
        with httpx.Client(timeout=settings.tika_timeout_seconds) as client:
            response = client.put(_endpoint("unpack"), content=payload, headers=headers)
    except Exception as exc:
        logger.warning("Tika недоступна (%s): %s", _endpoint("unpack"), exc)
        return None

    if response.status_code != 200:
        # 204 бывает у пакета без вложенных файлов — это не авария, но и не содержимое
        logger.warning("Tika ответила %s на %s", response.status_code, filename)
        return None

    try:
        with zipfile.ZipFile(io.BytesIO(response.content)) as zf:
            return {name: zf.read(name) for name in zf.namelist()}
    except Exception as exc:
        logger.warning("Tika вернула не zip для %s: %s", filename, exc)
        return None


def _json_entry(raw: Optional[bytes]) -> Optional[Any]:
    if not raw:
        return None
    try:
        return json.loads(raw.decode("utf-8", errors="replace"))
    except Exception:
        return None


def _main_entry(rmeta: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Запись главного документа: та, что не является вложенным ресурсом."""
    for entry in rmeta:
        if not entry.get("tk:embedded-resource-path") and not entry.get("tk:resource-name"):
            return entry
    return rmeta[0] if rmeta else {}


def _ordered_images(
    resources: List[Dict[str, Any]],
    blob_for: Dict[str, bytes],
    text: str,
) -> Tuple[List[Tuple[str, bytes]], List[str]]:
    """Изображения пакета в порядке ссылки на них в тексте документа.

    Возвращает [(mime, байты), заметки]. Ресурс, на который в тексте нет ссылки,
    всё равно отдаём — просто в конец, чтобы модель не потеряла скриншот.
    """
    by_name: Dict[str, Dict[str, Any]] = {}
    for resource in resources:
        name = str(resource.get("tk:resource-name") or resource.get("name") or "")
        path = str(resource.get("path") or "")
        if name and path in blob_for:
            by_name[name] = {**resource, "_path": path}

    notes: List[str] = []
    ordered: List[Tuple[str, bytes]] = []
    seen: set[str] = set()

    # порядок появления в тексте: image3 раньше image10, если так встал в документе
    for name in _EMBEDDED_REF.findall(text):
        clean = name.strip()
        if clean in seen or clean not in by_name:
            continue
        seen.add(clean)
        resource = by_name[clean]
        media_type = str(resource.get("mediatype") or resource.get("Content-Type") or "")
        ordered.append((media_type, blob_for[resource["_path"]]))

    for name, resource in by_name.items():
        if name in seen:
            continue
        seen.add(name)
        media_type = str(resource.get("mediatype") or resource.get("Content-Type") or "")
        ordered.append((media_type, blob_for[resource["_path"]]))

    images: List[Tuple[str, bytes]] = []
    for media_type, blob in ordered:
        subtype = media_type.split("/")[-1].lower().split(";")[0]
        if subtype not in IMAGE_EXTENSIONS:
            if len(notes) < MAX_NOTES:
                notes.append(
                    f"Tika не отдаёт изображение формата {media_type or 'неизвестно'} — "
                    "его не видно модели"
                )
            continue
        images.append((media_type, blob))
    return images, notes


def _extract_from_archive(archive: Dict[str, bytes]) -> Optional[ExtractedContent]:
    """Разбирает Frictionless-пакет из /unpack. None — если Tika ничего не дала."""
    rmeta = _json_entry(archive.get("rmeta.json")) or []
    datapackage = _json_entry(archive.get("datapackage.json")) or {}
    if isinstance(rmeta, dict):
        rmeta = [rmeta]
    resources = datapackage.get("resources") if isinstance(datapackage, dict) else None
    if not isinstance(resources, list):
        resources = []

    main = _main_entry(list(rmeta))
    text = str(main.get("tk:content") or main.get("X-TIKA:content") or "").strip()
    # markdown-escape служебных пробелов модели ни о чём не говорит
    text = text.replace("&#32;", " ")

    blob_for = {
        name: blob
        for name, blob in archive.items()
        if not name.endswith("/") and name != "datapackage.json" and name != "rmeta.json"
    }
    images, notes = _ordered_images(resources, blob_for, text)

    for entry in rmeta:
        for key in _EXCEPTION_KEYS:
            problem = entry.get(key)
            if problem and len(notes) < MAX_NOTES:
                notes.append(f"Tika не смогла разобрать часть документа: {str(problem)[:160]}")

    # ни текста, ни картинок — пакет пуст или разбор не удался: пусть работают
    # штатные ридеры, а модель получит честную картину от них
    if not text and not images:
        return None

    resized: List[Tuple[str, str]] = []
    for media_type, blob in images:
        try:
            data = resize_image(blob)
        except Exception as exc:
            notes.append(f"Не удалось обработать изображение: {exc}")
            continue
        resized.append((media_type, f"data:image/png;base64,{base64.b64encode(data).decode()}"))

    return ExtractedContent(
        text=text,
        images_base64=resized,
        notes=[note for note in notes if note][:MAX_NOTES],
    )


def extract(content: bytes, filename: str) -> Optional[ExtractedContent]:
    """Извлекает текст и изображения через Tika. None — если полагаемся на свои ридеры."""
    if not enabled() or not content:
        return None

    archive = _unpack_zip(content, filename)
    if archive is None:
        return None

    extracted = _extract_from_archive(archive)
    if extracted is None:
        logger.info("Tika не вернула содержимого для %s, переключаемся на свои ридеры", filename)
    return extracted
