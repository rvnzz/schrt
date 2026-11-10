import io
import re
import xml.etree.ElementTree as ET
import zipfile
from dataclasses import dataclass
from typing import List, Optional, Tuple

from pypdf import PdfReader
from docx import Document
from PIL import Image

from app import s3


IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "webp", "gif", "bmp", "tiff", "tif"}
TEXT_EXTENSIONS = {
    "txt", "md", "markdown", "csv", "json", "xml", "yaml", "yml",
    "py", "js", "ts", "tsx", "jsx", "java", "cpp", "c", "h", "hpp",
    "cs", "go", "rs", "rb", "php", "html", "css", "sql", "sh",
}


@dataclass
class ExtractedContent:
    text: str
    images_base64: List[Tuple[str, str]]  # (mime_type, base64)
    notes: List[str]


def _read_text_bytes(data: bytes) -> str:
    for encoding in ("utf-8", "utf-16", "cp1251", "latin-1"):
        try:
            return data.decode(encoding)
        except (UnicodeDecodeError, LookupError):
            continue
    return data.decode("utf-8", errors="replace")


def _resize_image(data: bytes, max_width: int = 1280) -> bytes:
    try:
        img = Image.open(io.BytesIO(data))
        img = img.convert("RGB") if img.mode in ("RGBA", "P") else img
        if img.width > max_width:
            ratio = max_width / img.width
            new_height = int(img.height * ratio)
            img = img.resize((max_width, new_height), Image.Resampling.LANCZOS)
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        return buffer.getvalue()
    except Exception:
        return data


def _image_to_base64(data: bytes, mime: str = "image/png") -> str:
    import base64
    return f"data:{mime};base64,{base64.b64encode(data).decode()}"


def _natural_key(name: str) -> Tuple[int, str]:
    """Натуральный порядок частей: image2 раньше image10."""
    stem = name.rsplit("/", 1)[-1].rsplit(".", 1)[0]
    match = re.search(r"(\d+)$", stem)
    return (int(match.group(1)) if match else 0, name)


def _collect_images(
    zf: zipfile.ZipFile,
    parts: List[str],
    label: str,
) -> Tuple[List[Tuple[str, str]], List[str]]:
    """Читает и ужимает найденные части пакета; непонятные форматы — в заметки."""
    images: List[Tuple[str, str]] = []
    notes: List[str] = []
    for name in parts:
        ext = name.split(".")[-1].lower()
        if ext not in IMAGE_EXTENSIONS:
            notes.append(f"Пропущено изображение {label} неподдерживаемого формата: {name}")
            continue
        try:
            resized = _resize_image(zf.read(name))
            images.append(("image/png", _image_to_base64(resized)))
        except Exception as exc:
            notes.append(f"Не удалось обработать изображение {name}: {exc}")
    return images, notes


def _resolve_part(rels_name: str, target: str) -> Optional[str]:
    """Путь к части пакета из Target связи: «/media/image.png», «media/x.png», «../media/x.png»."""
    if not target:
        return None
    if target.startswith("/"):
        return target[1:]
    # Слово «_rels» в имени — сигнал, от какой папки считать относительный путь
    base = f"{rels_name.rsplit('/_rels/', 1)[0]}/" if "/_rels/" in rels_name else ""
    resolved: List[str] = []
    for part in f"{base}{target}".split("/"):
        if part in ("", "."):
            continue
        if part == "..":
            if resolved:
                resolved.pop()
            continue
        resolved.append(part)
    return "/".join(resolved) or None


def _docx_image_parts(zf: zipfile.ZipFile) -> Tuple[List[str], List[str]]:
    """Список путей к изображениям docx + заметки о проблемных местах.

    По спецификации части обычно лежат в word/media/, но редакторы кладут их и в
    корень пакета (media/image.png) — такие файлы раньше оставались без единой
    картинки, и агент проверял работу вслепую. Поэтому смотрим и на папки с
    изображениями, и на цели связей .rels, которые точнее всего.
    """
    names = set(zf.namelist())
    found: List[str] = []
    notes: List[str] = []

    for name in zf.namelist():
        lowered = name.lower()
        if lowered.startswith("word/media/") or lowered.startswith("media/"):
            if name not in found:
                found.append(name)

    for rels_name in sorted(n for n in names if n.lower().endswith(".rels")):
        try:
            root = ET.fromstring(zf.read(rels_name))
        except Exception:
            # битый .rels не повод терять картинки, найденные по путям
            continue
        for rel in root:
            if not rel.tag.endswith("Relationship"):
                continue
            if "/image" not in rel.attrib.get("Type", "").lower():
                continue
            if rel.attrib.get("TargetMode", "").lower() == "external":
                notes.append(
                    f"Скриншот вставлен ссылкой на внешний файл: {rel.attrib.get('Target', '')}"
                )
                continue
            resolved = _resolve_part(rels_name, rel.attrib.get("Target", ""))
            if resolved is None:
                continue
            if resolved in names:
                if resolved not in found:
                    found.append(resolved)
            else:
                notes.append(f"Связь ссылается на отсутствующую часть пакета: {resolved}")

    return sorted(found, key=_natural_key), notes


def _is_odt(content: bytes) -> bool:
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as zf:
            if "mimetype" in zf.namelist():
                mimetype = zf.read("mimetype").decode("utf-8", errors="ignore").strip()
                return "opendocument" in mimetype
    except Exception:
        pass
    return False


def _odt_image_parts(zf: zipfile.ZipFile) -> List[str]:
    """Изображения ODT: стандартная папка Pictures/ и всё, что объявлено как image/* в манифесте."""
    names = set(zf.namelist())
    found: List[str] = []

    def is_thumb(path: str) -> bool:
        return "thumbnails/" in path.lower()

    for name in zf.namelist():
        lowered = name.lower()
        if is_thumb(lowered):
            continue
        if lowered.startswith("pictures/") or lowered.startswith("media/"):
            if name not in found:
                found.append(name)

    if "META-INF/manifest.xml" in names:
        try:
            root = ET.fromstring(zf.read("META-INF/manifest.xml"))
        except Exception:
            root = None
        for entry in root.iter() if root is not None else []:
            media_type = ""
            path = ""
            for key, value in entry.attrib.items():
                if key.endswith("media-type"):
                    media_type = value
                elif key.endswith("full-path"):
                    path = value
            if media_type.lower().startswith("image/") and path in names and not is_thumb(path):
                if path not in found:
                    found.append(path)

    return sorted(found, key=_natural_key)


def _extract_odt(content: bytes) -> ExtractedContent:
    text_parts: List[str] = []
    notes: List[str] = []

    try:
        with zipfile.ZipFile(io.BytesIO(content)) as zf:
            if "content.xml" in zf.namelist():
                content_xml = zf.read("content.xml")
                root = ET.fromstring(content_xml)
                for elem in root.iter():
                    if elem.text and elem.text.strip():
                        text_parts.append(elem.text.strip())
                    if elem.tail and elem.tail.strip():
                        text_parts.append(elem.tail.strip())
            else:
                notes.append("В ODT-файле не найден content.xml")

            images, image_notes = _collect_images(zf, _odt_image_parts(zf), "odt")
            notes.extend(image_notes)
    except Exception as exc:
        notes.append(f"Не удалось открыть ODT как zip: {exc}")
        images = []

    return ExtractedContent(text="\n".join(text_parts), images_base64=images, notes=notes)


def _extract_docx(content: bytes) -> ExtractedContent:
    if _is_odt(content):
        return _extract_odt(content)

    text_parts: List[str] = []
    images: List[Tuple[str, str]] = []
    notes: List[str] = []

    try:
        document = Document(io.BytesIO(content))
        for para in document.paragraphs:
            if para.text:
                text_parts.append(para.text)
        for table in document.tables:
            for row in table.rows:
                for cell in row.cells:
                    if cell.text:
                        text_parts.append(cell.text)
    except Exception as exc:
        notes.append(f"Не удалось извлечь текст docx: {exc}")

    try:
        with zipfile.ZipFile(io.BytesIO(content)) as zf:
            parts, link_notes = _docx_image_parts(zf)
            notes.extend(link_notes)
            collected, image_notes = _collect_images(zf, parts, "docx")
            images.extend(collected)
            notes.extend(image_notes)
    except Exception as exc:
        notes.append(f"Не удалось открыть docx как zip: {exc}")

    return ExtractedContent(text="\n".join(text_parts), images_base64=images, notes=notes)


def _extract_pdf(content: bytes) -> ExtractedContent:
    text_parts: List[str] = []
    images: List[Tuple[str, str]] = []
    notes: List[str] = []

    try:
        reader = PdfReader(io.BytesIO(content))
        for page in reader.pages:
            try:
                page_text = page.extract_text()
                if page_text:
                    text_parts.append(page_text)
            except Exception as exc:
                notes.append(f"Не удалось извлечь текст страницы: {exc}")

            try:
                for image in page.images:
                    try:
                        resized = _resize_image(image.data)
                        images.append(("image/png", _image_to_base64(resized)))
                    except Exception as exc:
                        notes.append(f"Не удалось обработать изображение pdf: {exc}")
            except Exception:
                pass
    except Exception as exc:
        notes.append(f"Не удалось прочитать PDF: {exc}")

    return ExtractedContent(text="\n".join(text_parts), images_base64=images, notes=notes)


def _extract_xlsx(content: bytes) -> ExtractedContent:
    text_parts: List[str] = []
    notes: List[str] = []
    try:
        from openpyxl import load_workbook
        wb = load_workbook(io.BytesIO(content), data_only=True)
        for sheet in wb.worksheets:
            for row in sheet.iter_rows(values_only=True):
                row_text = " ".join(str(cell) for cell in row if cell is not None)
                if row_text.strip():
                    text_parts.append(row_text)
    except Exception as exc:
        notes.append(f"Не удалось прочитать xlsx: {exc}")
    return ExtractedContent(text="\n".join(text_parts), images_base64=[], notes=notes)


def extract_file(key: str, original_filename: str) -> ExtractedContent:
    data = s3.get_object_bytes(key)
    ext = original_filename.split(".")[-1].lower() if "." in original_filename else ""

    if ext in ("docx", "doc", "odt"):
        return _extract_docx(data)
    if ext == "pdf":
        return _extract_pdf(data)
    if ext in ("xlsx", "xls"):
        return _extract_xlsx(data)
    if ext in IMAGE_EXTENSIONS:
        try:
            resized = _resize_image(data)
            return ExtractedContent(
                text="",
                images_base64=[("image/png", _image_to_base64(resized))],
                notes=[],
            )
        except Exception as exc:
            return ExtractedContent(text="", images_base64=[], notes=[f"Не удалось обработать изображение: {exc}"])
    if ext in TEXT_EXTENSIONS or not ext:
        return ExtractedContent(text=_read_text_bytes(data), images_base64=[], notes=[])

    return ExtractedContent(
        text="",
        images_base64=[],
        notes=[f"Формат файла .{ext} не поддерживается для извлечения содержимого."],
    )
