"""Qdrant Cloud knowledge-base adapter for LegacyLens.

The adapter intentionally keeps the small interface used by the existing
LegacyLens knowledge-base code (insert_many/search) while moving vectors and
embedding inference out of the Render container.

Render/hosted profile:
- Qdrant Cloud stores persistent vectors + metadata.
- Qdrant Cloud Inference creates dense MiniLM + sparse BM25 vectors.
- Qdrant performs hybrid RRF retrieval server-side.

No local embedding model is loaded by this module.
"""

from __future__ import annotations

import hashlib
import logging
import os
import uuid
from typing import Any, Iterable

from qdrant_client import QdrantClient, models
from agno.knowledge.document import Document

from app.infrastructure.utils.migration_context import migration_name_ctx
from app.infrastructure.utils.user_context import current_user

logger = logging.getLogger(__name__)

QDRANT_URL = os.getenv("QDRANT_URL", "").strip()
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY", "").strip() or None
QDRANT_COLLECTION_PREFIX = os.getenv("QDRANT_COLLECTION_PREFIX", "legacylens").strip()
QDRANT_DENSE_MODEL = os.getenv(
    "QDRANT_DENSE_MODEL", "sentence-transformers/all-MiniLM-L6-v2"
).strip()
# Qdrant Cloud currently exposes this model under the canonical
# `sentence-transformers/...` identifier. Accept older/mistyped aliases in
# Render environment variables, but always send the supported model ID.
if QDRANT_DENSE_MODEL.lower() in {
    "transformers/all-minilm-l6-v2",
    "all-minilm-l6-v2",
    "sentence-transformers/all-minilm-l6-v2",
}:
    QDRANT_DENSE_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
QDRANT_SPARSE_MODEL = os.getenv("QDRANT_SPARSE_MODEL", "qdrant/bm25").strip()
QDRANT_DENSE_DIMENSIONS = int(os.getenv("QDRANT_DENSE_DIMENSIONS", "384"))
QDRANT_TOP_K = int(os.getenv("QDRANT_TOP_K", "8"))
QDRANT_CLOUD_INFERENCE = os.getenv("QDRANT_CLOUD_INFERENCE", "true").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}


def _context_value(ctx, default: str) -> str:
    try:
        value = ctx.get()
    except LookupError:
        value = None
    if hasattr(value, "id"):
        value = getattr(value, "id", None)
    value = str(value or "").strip()
    return value or default


def _tenant_key() -> tuple[str, str]:
    user_id = _context_value(current_user, "anonymous")
    migration_name = _context_value(migration_name_ctx, "default")
    return user_id, migration_name


def _collection_name(scope: str) -> str:
    safe_scope = "source" if scope.lower() == "source" else "target"
    # Qdrant collection names are easier to operate when kept short/stable.
    digest = hashlib.sha1(QDRANT_COLLECTION_PREFIX.encode("utf-8")).hexdigest()[:10]
    return f"{QDRANT_COLLECTION_PREFIX}-{digest}-{safe_scope}"


class QdrantKnowledgeBase:
    """Small sync knowledge-base facade used by the existing agent code."""

    def __init__(self, collection_name: str):
        if not QDRANT_URL:
            raise RuntimeError("QDRANT_URL is required for the Qdrant knowledge base")

        self.collection_name = collection_name
        self.client = QdrantClient(
            url=QDRANT_URL,
            api_key=QDRANT_API_KEY,
            cloud_inference=QDRANT_CLOUD_INFERENCE,
            timeout=float(os.getenv("QDRANT_TIMEOUT_SECONDS", "30")),
        )
        self._ensure_collection()

    def _ensure_collection(self) -> None:
        if not self.client.collection_exists(self.collection_name):
            logger.info("Creating Qdrant collection %s", self.collection_name)
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config={
                    "dense_vector": models.VectorParams(
                        size=QDRANT_DENSE_DIMENSIONS,
                        distance=models.Distance.COSINE,
                    )
                },
                sparse_vectors_config={
                    "bm25_sparse_vector": models.SparseVectorParams(
                        modifier=models.Modifier.IDF,
                    )
                },
            )

        # Keep the payload schema synchronized with every exact-match filter
        # used by the existing LegacyLens code. This runs on every startup so
        # collections created by older deployments are repaired in-place.
        payload_indexes = (
            ("_user_id", models.PayloadSchemaType.KEYWORD),
            ("_migration_name", models.PayloadSchemaType.KEYWORD),
            ("_scope", models.PayloadSchemaType.KEYWORD),
            ("meta_source", models.PayloadSchemaType.KEYWORD),
            ("meta_source_file_path", models.PayloadSchemaType.KEYWORD),
            ("meta_file_name", models.PayloadSchemaType.KEYWORD),
            ("meta_doc_type", models.PayloadSchemaType.KEYWORD),
            ("meta_migration_status", models.PayloadSchemaType.KEYWORD),
            ("meta_plan_id", models.PayloadSchemaType.KEYWORD),
            ("meta_symbol_id", models.PayloadSchemaType.KEYWORD),
            ("meta_symbol_hash", models.PayloadSchemaType.KEYWORD),
            ("meta_source_symbol_id", models.PayloadSchemaType.KEYWORD),
            ("meta_source_symbol_hash", models.PayloadSchemaType.KEYWORD),
            ("meta_is_target", models.PayloadSchemaType.BOOL),
        )

        for field_name, schema in payload_indexes:
            try:
                self.client.create_payload_index(
                    collection_name=self.collection_name,
                    field_name=field_name,
                    field_schema=schema,
                )
                logger.debug("Ensured Qdrant payload index: %s", field_name)
            except Exception as exc:  # pragma: no cover - best-effort index setup
                logger.debug("Payload index %s not created: %s", field_name, exc)

    @staticmethod
    def _point_id(scope: str, name: str, text: str, user_id: str, migration_name: str) -> str:
        stable = "|".join((scope, user_id, migration_name, name, hashlib.sha256(text.encode("utf-8")).hexdigest()))
        return str(uuid.uuid5(uuid.NAMESPACE_URL, stable))

    @staticmethod
    def _payload_filter(filters: dict[str, Any] | None) -> models.Filter | None:
        conditions: list[models.FieldCondition] = []
        for key, value in (filters or {}).items():
            q_key = key if key.startswith("_") else f"meta_{key}"
            if isinstance(value, (list, tuple, set)):
                conditions.append(
                    models.FieldCondition(
                        key=q_key,
                        match=models.MatchAny(any=list(value)),
                    )
                )
            else:
                conditions.append(
                    models.FieldCondition(
                        key=q_key,
                        match=models.MatchValue(value=value),
                    )
                )
        return models.Filter(must=conditions) if conditions else None

    def _scoped_filter(self, filters: dict[str, Any] | None = None) -> models.Filter:
        user_id, migration_name = _tenant_key()
        must: list[Any] = [
            models.FieldCondition(key="_user_id", match=models.MatchValue(value=user_id)),
            models.FieldCondition(
                key="_migration_name", match=models.MatchValue(value=migration_name)
            ),
        ]
        extra = self._payload_filter(filters)
        if extra:
            must.extend(extra.must or [])
        return models.Filter(must=must)

    @staticmethod
    def _normalize_metadata(metadata: Any) -> dict[str, Any]:
        return dict(metadata) if isinstance(metadata, dict) else {}

    def insert(self, *, name: str, text_content: str, metadata: dict[str, Any] | None = None, **_: Any) -> int:
        """Agno-compatible single-document insert used by older tool paths."""
        return self.insert_many([
            {
                "name": name,
                "text_content": text_content,
                "metadata": metadata or {},
            }
        ])

    def insert_many(self, contents: Iterable[dict[str, Any]]) -> int:
        items = list(contents)
        if not items:
            return 0

        user_id, migration_name = _tenant_key()
        points: list[models.PointStruct] = []
        for item in items:
            text = str(item.get("text_content") or item.get("content") or "").strip()
            if not text:
                continue
            name = str(item.get("name") or hashlib.sha1(text.encode("utf-8")).hexdigest())
            metadata = self._normalize_metadata(item.get("metadata") or item.get("meta_data"))
            scope = "target" if metadata.get("is_target") else "source"
            payload = {
                "text_content": text,
                "content": text,
                "name": name,
                "metadata": metadata,
                "_user_id": user_id,
                "_migration_name": migration_name,
                "_scope": scope,
            }
            # Flat metadata fields make filtering fast and predictable.
            for key, value in metadata.items():
                if isinstance(value, (str, int, float, bool)) or value is None:
                    payload[f"meta_{key}"] = value

            points.append(
                models.PointStruct(
                    id=self._point_id(scope, name, text, user_id, migration_name),
                    payload=payload,
                    vector={
                        "dense_vector": models.Document(text=text, model=QDRANT_DENSE_MODEL),
                        "bm25_sparse_vector": models.Document(text=text, model=QDRANT_SPARSE_MODEL),
                    },
                )
            )

        if not points:
            return 0

        self.client.upload_points(
            collection_name=self.collection_name,
            points=points,
            batch_size=32,
        )
        return len(points)

    @staticmethod
    def _as_document(payload: dict[str, Any], *, score: float | None = None) -> Document:
        """Convert a Qdrant payload into the Agno Document contract expected by LegacyLens.

        The original LanceDB/Agno path returned Document instances. Keeping that
        contract here avoids leaking Qdrant payload dictionaries into existing
        planning/conversion code that accesses ``doc.content`` and
        ``doc.meta_data`` attributes.
        """
        metadata = payload.get("metadata")
        if not isinstance(metadata, dict):
            metadata = {}
        doc = Document(
            id=str(payload.get("id") or ""),
            name=str(payload.get("name") or ""),
            content=str(payload.get("text_content") or payload.get("content") or ""),
            meta_data=metadata,
        )
        if score is not None:
            # Agno versions used by LegacyLens expose score on search results;
            # set it defensively so this adapter remains compatible across versions.
            try:
                doc.score = score
            except Exception:
                pass
        return doc

    def search(
        self,
        query: str | None = None,
        *,
        filters: dict[str, Any] | None = None,
        limit: int | None = None,
        max_results: int | None = None,
        **_: Any,
    ) -> list[dict[str, Any]]:
        top_k = int(max_results or limit or QDRANT_TOP_K)
        if not query:
            return []
        if query.strip() == "*":
            payloads = self.scroll(filters=filters, limit=top_k)
            return [self._as_document(p, score=0.0) for p in payloads]
        scoped_filter = self._scoped_filter(filters)

        response = self.client.query_points(
            collection_name=self.collection_name,
            prefetch=[
                models.Prefetch(
                    query=models.Document(text=query, model=QDRANT_DENSE_MODEL),
                    using="dense_vector",
                    filter=scoped_filter,
                    limit=max(top_k * 2, top_k),
                ),
                models.Prefetch(
                    query=models.Document(text=query, model=QDRANT_SPARSE_MODEL),
                    using="bm25_sparse_vector",
                    filter=scoped_filter,
                    limit=max(top_k * 2, top_k),
                ),
            ],
            query=models.FusionQuery(fusion=models.Fusion.RRF),
            query_filter=scoped_filter,
            limit=top_k,
            with_payload=True,
        )

        results: list[Document] = []
        for point in response.points:
            payload = point.payload or {}
            doc = self._as_document(payload, score=float(point.score or 0.0))
            results.append(doc)
        return results

    def scroll(self, *, filters: dict[str, Any] | None = None, limit: int = 1000) -> list[dict[str, Any]]:
        records, _ = self.client.scroll(
            collection_name=self.collection_name,
            scroll_filter=self._scoped_filter(filters),
            limit=limit,
            with_payload=True,
            with_vectors=False,
        )
        return [record.payload or {} for record in records]

    def delete(self, *, filters: dict[str, Any] | None = None) -> None:
        self.client.delete(
            collection_name=self.collection_name,
            points_selector=models.FilterSelector(filter=self._scoped_filter(filters)),
            wait=True,
        )
