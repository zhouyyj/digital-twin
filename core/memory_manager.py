"""Event-sourced episodic memory backed by ChromaDB + OpenAI embeddings."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

import chromadb
from openai import OpenAI

from core.config import get_openai_embedding_model, get_project_root

EventType = Literal[
    "User_Thought",
    "AI_Intervention",
    "Diary_Entry",
    "Document_Artifact",
    "Image_Artifact",
]
_EVENT_TYPES: frozenset[str] = frozenset(
    {
        "User_Thought",
        "AI_Intervention",
        "Diary_Entry",
        "Document_Artifact",
        "Image_Artifact",
    }
)


class MemoryManager:
    """Append-only event log with semantic retrieval (event sourcing over vectors)."""

    _COLLECTION = "mirror_memory_events"

    def __init__(
        self,
        openai_client: OpenAI,
        *,
        persist_directory: Path | None = None,
    ) -> None:
        self._client = openai_client
        self._embedding_model = get_openai_embedding_model()
        root = persist_directory or get_project_root()
        db_path = root / ".chroma_db"
        db_path.mkdir(parents=True, exist_ok=True)
        self._chroma = chromadb.PersistentClient(path=str(db_path))
        self._collection = self._chroma.get_or_create_collection(
            name=self._COLLECTION,
            metadata={"hnsw:space": "cosine"},
        )

    def _embed(self, text: str) -> list[float]:
        response = self._client.embeddings.create(
            model=self._embedding_model,
            input=text,
        )
        return list(response.data[0].embedding)

    def add_event(
        self,
        text: str,
        event_type: EventType | str,
        *,
        source: str | None = None,
        media_kind: str | None = None,
    ) -> str:
        if event_type not in _EVENT_TYPES:
            raise ValueError(
                f"event_type must be one of {sorted(_EVENT_TYPES)}, got {event_type!r}"
            )
        body = text.strip()
        if not body:
            raise ValueError("text must be non-empty")

        timestamp = datetime.now(timezone.utc).isoformat()
        event_id = str(uuid.uuid4())
        vector = self._embed(body)

        meta: dict[str, str] = {
            "event_type": event_type,
            "timestamp": timestamp,
        }
        if source:
            meta["source"] = source[:500]
        if media_kind:
            meta["media_kind"] = media_kind[:64]

        self._collection.add(
            ids=[event_id],
            embeddings=[vector],
            documents=[body],
            metadatas=[meta],
        )
        return event_id

    def search_relevant_events(
        self, query: str, limit: int = 5
    ) -> list[dict[str, Any]]:
        q = query.strip()
        if not q or limit < 1:
            return []

        count = self._collection.count()
        if count == 0:
            return []

        n_results = min(limit, count)
        vector = self._embed(q)
        raw = self._collection.query(
            query_embeddings=[vector],
            n_results=n_results,
        )

        ids_batch = raw["ids"][0] if raw["ids"] else []
        docs_batch = raw["documents"][0] if raw["documents"] else []
        meta_batch = raw["metadatas"][0] if raw["metadatas"] else []
        dist_batch = raw["distances"][0] if raw.get("distances") else []

        events: list[dict[str, Any]] = []
        for i, eid in enumerate(ids_batch):
            meta = meta_batch[i] if i < len(meta_batch) and meta_batch[i] else {}
            doc = docs_batch[i] if i < len(docs_batch) else ""
            dist = dist_batch[i] if i < len(dist_batch) else None
            events.append(
                {
                    "id": eid,
                    "text": doc,
                    "timestamp": meta.get("timestamp", ""),
                    "event_type": meta.get("event_type", ""),
                    "source": meta.get("source", ""),
                    "media_kind": meta.get("media_kind", ""),
                    "distance": dist,
                }
            )
        return events

    def count_events(self) -> int:
        return int(self._collection.count())
