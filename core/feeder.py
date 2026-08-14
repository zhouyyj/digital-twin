"""Phase 4 — water the twin with personal artifacts (diary / docs / images)."""

from __future__ import annotations

import base64
import mimetypes
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterator

from openai import OpenAI

from core.config import get_openai_model
from core.memory_manager import MemoryManager

PrintFn = Callable[..., None]

_TEXT_SUFFIXES = {
    ".txt",
    ".md",
    ".markdown",
    ".rst",
    ".csv",
    ".tsv",
    ".json",
    ".jsonl",
    ".yaml",
    ".yml",
    ".html",
    ".htm",
    ".log",
    ".diary",
    ".journal",
}
_IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".gif"}
_PDF_SUFFIXES = {".pdf"}
_DOCX_SUFFIXES = {".docx"}

_CHUNK_CHARS = 1200
_CHUNK_OVERLAP = 150

_IMAGE_PROMPT = (
    "You are watering memory for Digital Twin. In concise English, describe this personal "
    "photo: identity, setting, mood, relationships, or values. No empty aesthetic praise. "
    "Note any visible text. Write 80–180 words as a memory entry."
)


@dataclass(frozen=True)
class WaterResult:
    path: str
    kind: str
    chunks: int
    event_ids: tuple[str, ...]


class PersonalFeeder:
    """Ingest personal files into episodic memory (explicit watering, not surveillance)."""

    def __init__(
        self,
        client: OpenAI,
        memory: MemoryManager,
        *,
        model: str | None = None,
        print: PrintFn = print,
    ) -> None:
        self._client = client
        self._memory = memory
        self._model = model or get_openai_model()
        self._print = print

    def water(self, target: str) -> list[WaterResult]:
        """
        Water with a path, a directory, or an inline note.

        - `/water ~/diary/2024.md`
        - `/water ./photos`
        - `/water note: I finally opened the windows after clearing the studio.`
        """
        raw = target.strip()
        if not raw:
            raise ValueError(
                "Usage: /water <file or directory>  or  /water note: <diary line>"
            )

        if raw.lower().startswith("note:"):
            body = raw.split(":", 1)[1].strip()
            if not body:
                raise ValueError("note: needs a diary line after it.")
            eid = self._memory.add_event(
                body,
                "Diary_Entry",
                source="inline:note",
                media_kind="diary",
            )
            return [
                WaterResult(
                    path="inline:note",
                    kind="diary",
                    chunks=1,
                    event_ids=(eid,),
                )
            ]

        path = Path(raw).expanduser()
        if not path.exists():
            raise FileNotFoundError(f"Path not found: {path}")

        files = sorted(self._iter_files(path))
        if not files:
            raise ValueError(f"Nothing to water at: {path}")

        results: list[WaterResult] = []
        for f in files:
            results.append(self._water_file(f))
        return results

    def _iter_files(self, path: Path) -> Iterator[Path]:
        if path.is_file():
            yield path
            return
        for p in sorted(path.rglob("*")):
            if not p.is_file():
                continue
            if p.name.startswith("."):
                continue
            if p.suffix.lower() in (
                _TEXT_SUFFIXES | _IMAGE_SUFFIXES | _PDF_SUFFIXES | _DOCX_SUFFIXES
            ):
                yield p

    def _water_file(self, path: Path) -> WaterResult:
        suffix = path.suffix.lower()
        if suffix in _IMAGE_SUFFIXES:
            kind = "image"
            texts = [self._describe_image(path)]
            event_type = "Image_Artifact"
        elif suffix in _PDF_SUFFIXES:
            kind = "pdf"
            texts = list(self._chunk_text(self._read_pdf(path)))
            event_type = "Document_Artifact"
        elif suffix in _DOCX_SUFFIXES:
            kind = "docx"
            texts = list(self._chunk_text(self._read_docx(path)))
            event_type = "Document_Artifact"
        elif suffix in _TEXT_SUFFIXES or self._looks_like_text(path):
            kind = "diary" if suffix in {".diary", ".journal", ".md", ".txt"} else "document"
            raw = path.read_text(encoding="utf-8", errors="replace")
            texts = list(self._chunk_text(raw))
            event_type = "Diary_Entry" if kind == "diary" else "Document_Artifact"
        else:
            raise ValueError(f"Unsupported type: {path.suffix or path.name}")

        ids: list[str] = []
        total = len(texts)
        for i, chunk in enumerate(texts, start=1):
            header = f"[watered {kind} · {path.name} · {i}/{total}]\n"
            eid = self._memory.add_event(
                header + chunk,
                event_type,
                source=str(path.resolve()),
                media_kind=kind,
            )
            ids.append(eid)

        self._print(f"Watered {path} → {len(ids)} memories ({kind})")
        return WaterResult(
            path=str(path),
            kind=kind,
            chunks=len(ids),
            event_ids=tuple(ids),
        )

    def _looks_like_text(self, path: Path) -> bool:
        try:
            sample = path.read_bytes()[:2048]
        except OSError:
            return False
        if b"\x00" in sample:
            return False
        try:
            sample.decode("utf-8")
            return True
        except UnicodeDecodeError:
            return False

    def _chunk_text(self, text: str) -> Iterator[str]:
        cleaned = re.sub(r"\r\n?", "\n", text).strip()
        if not cleaned:
            return
        if len(cleaned) <= _CHUNK_CHARS:
            yield cleaned
            return
        start = 0
        n = len(cleaned)
        while start < n:
            end = min(n, start + _CHUNK_CHARS)
            piece = cleaned[start:end].strip()
            if piece:
                yield piece
            if end >= n:
                break
            start = max(end - _CHUNK_OVERLAP, start + 1)

    def _read_pdf(self, path: Path) -> str:
        try:
            from pypdf import PdfReader
        except ImportError as exc:
            raise RuntimeError("pypdf is required for PDFs: pip install pypdf") from exc
        reader = PdfReader(str(path))
        pages: list[str] = []
        for i, page in enumerate(reader.pages, start=1):
            try:
                t = page.extract_text() or ""
            except Exception:
                t = ""
            if t.strip():
                pages.append(f"--- page {i} ---\n{t.strip()}")
        if not pages:
            raise ValueError(f"No text extracted from PDF: {path}")
        return "\n\n".join(pages)

    def _read_docx(self, path: Path) -> str:
        try:
            import docx  # type: ignore
        except ImportError as exc:
            raise RuntimeError(
                "python-docx is required for Word: pip install python-docx"
            ) from exc
        document = docx.Document(str(path))
        paras = [p.text.strip() for p in document.paragraphs if p.text.strip()]
        if not paras:
            raise ValueError(f"Word document is empty: {path}")
        return "\n\n".join(paras)

    def _describe_image(self, path: Path) -> str:
        mime, _ = mimetypes.guess_type(str(path))
        mime = mime or "image/jpeg"
        data = base64.b64encode(path.read_bytes()).decode("ascii")
        data_url = f"data:{mime};base64,{data}"
        resp = self._client.chat.completions.create(
            model=self._model,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": _IMAGE_PROMPT},
                        {
                            "type": "image_url",
                            "image_url": {"url": data_url},
                        },
                    ],
                }
            ],
            max_tokens=500,
            temperature=0.3,
        )
        text = (resp.choices[0].message.content or "").strip()
        if not text:
            raise ValueError(f"Image description was empty: {path}")
        return text
