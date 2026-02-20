from __future__ import annotations

import atexit
import logging
import time
import uuid
from typing import Any, Dict, List, Optional, Sequence

from qdrant_client import QdrantClient
from qdrant_client.http import models as qdrant_models

from ..config import settings

logger = logging.getLogger(__name__)

_client: QdrantClient | None = None
_conversation_collection: "QdrantPayloadCollection" | None = None
_turns_collection: "QdrantPayloadCollection" | None = None
_summaries_collection: "QdrantPayloadCollection" | None = None

_PAYLOAD_DOCUMENT_KEY = "_document"
_PAYLOAD_ID_KEY = "_id"
_PAYLOAD_COLLECTION_VECTOR_SIZE = 1
_ID_NAMESPACE = uuid.UUID("18cf633f-6d0e-4c20-a9ba-c9ecbf139e31")


def get_client() -> QdrantClient:
    global _client
    if _client is None:
        if settings.qdrant_url:
            logger.info("Initializing Qdrant (remote) at %s", settings.qdrant_url)
            kwargs: dict[str, Any] = {"url": settings.qdrant_url}
            if settings.qdrant_api_key:
                kwargs["api_key"] = settings.qdrant_api_key
            _client = QdrantClient(**kwargs)
        else:
            path = str(settings.qdrant_db_path)
            logger.info("Initializing Qdrant (local) at %s", path)
            _client = QdrantClient(path=path)
    return _client


def _close_client() -> None:
    global _client
    if _client is None:
        return
    try:
        _client.close()
    except Exception:
        pass
    _client = None


atexit.register(_close_client)


def _build_filter(where: Optional[Dict[str, Any]]) -> Optional[qdrant_models.Filter]:
    if not where:
        return None

    if "$and" in where:
        conditions: List[qdrant_models.Condition] = []
        for item in where.get("$and", []):
            built = _build_filter(item)
            if built and built.must:
                conditions.extend(built.must)
        if not conditions:
            return None
        return qdrant_models.Filter(must=conditions)

    conditions = []
    for key, value in where.items():
        if isinstance(value, dict):
            if "$eq" in value:
                conditions.append(
                    qdrant_models.FieldCondition(
                        key=key,
                        match=qdrant_models.MatchValue(value=value["$eq"]),
                    )
                )
                continue
            if any(op in value for op in ("$gt", "$gte", "$lt", "$lte")):
                conditions.append(
                    qdrant_models.FieldCondition(
                        key=key,
                        range=qdrant_models.Range(
                            gt=value.get("$gt"),
                            gte=value.get("$gte"),
                            lt=value.get("$lt"),
                            lte=value.get("$lte"),
                        ),
                    )
                )
                continue

        conditions.append(
            qdrant_models.FieldCondition(
                key=key,
                match=qdrant_models.MatchValue(value=value),
            )
        )

    if not conditions:
        return None
    return qdrant_models.Filter(must=conditions)


class QdrantPayloadCollection:
    def __init__(self, collection_name: str):
        self.collection_name = collection_name
        self.client = get_client()
        self._ensure_collection()

    @staticmethod
    def _to_point_id(raw_id: str) -> str:
        return str(uuid.uuid5(_ID_NAMESPACE, raw_id))

    def _ensure_collection(self) -> None:
        if self.client.collection_exists(self.collection_name):
            return
        self.client.create_collection(
            collection_name=self.collection_name,
            vectors_config=qdrant_models.VectorParams(
                size=_PAYLOAD_COLLECTION_VECTOR_SIZE,
                distance=qdrant_models.Distance.COSINE,
            ),
        )

    def _scroll(
        self, scroll_filter: Optional[qdrant_models.Filter]
    ) -> List[qdrant_models.Record]:
        results: List[qdrant_models.Record] = []
        offset: Optional[qdrant_models.PointId] = None
        while True:
            page, offset = self.client.scroll(
                collection_name=self.collection_name,
                scroll_filter=scroll_filter,
                with_payload=True,
                with_vectors=False,
                limit=256,
                offset=offset,
            )
            results.extend(page)
            if offset is None:
                break
        return results

    @staticmethod
    def _point_to_result_item(point: qdrant_models.Record) -> tuple[str, Dict[str, Any], str]:
        payload = dict(point.payload or {})
        source_id = str(payload.pop(_PAYLOAD_ID_KEY, str(point.id)))
        document = str(payload.pop(_PAYLOAD_DOCUMENT_KEY, ""))
        return source_id, payload, document

    def add(
        self,
        *,
        documents: Sequence[str],
        metadatas: Sequence[Dict[str, Any]],
        ids: Sequence[str],
    ) -> None:
        self.upsert(documents=documents, metadatas=metadatas, ids=ids)

    def upsert(
        self,
        *,
        documents: Sequence[str],
        metadatas: Sequence[Dict[str, Any]],
        ids: Sequence[str],
    ) -> None:
        points: List[qdrant_models.PointStruct] = []
        for pid, metadata, document in zip(ids, metadatas, documents):
            raw_id = str(pid)
            payload = dict(metadata or {})
            payload[_PAYLOAD_ID_KEY] = raw_id
            payload[_PAYLOAD_DOCUMENT_KEY] = document
            points.append(
                qdrant_models.PointStruct(
                    id=self._to_point_id(raw_id),
                    vector=[0.0],
                    payload=payload,
                )
            )
        if points:
            self.client.upsert(collection_name=self.collection_name, points=points)

    def update(self, *, ids: Sequence[str], metadatas: Sequence[Dict[str, Any]]) -> None:
        if not ids:
            return
        existing = self.client.retrieve(
            collection_name=self.collection_name,
            ids=[self._to_point_id(str(pid)) for pid in ids],
            with_payload=True,
            with_vectors=False,
        )
        existing_map = {str(item.id): item for item in existing}

        points: List[qdrant_models.PointStruct] = []
        for pid, metadata in zip(ids, metadatas):
            raw_id = str(pid)
            point_id = self._to_point_id(raw_id)
            point = existing_map.get(point_id)
            if point is None:
                continue
            payload = dict(point.payload or {})
            payload[_PAYLOAD_ID_KEY] = raw_id
            payload.update(metadata or {})
            points.append(
                qdrant_models.PointStruct(
                    id=point_id,
                    vector=[0.0],
                    payload=payload,
                )
            )
        if points:
            self.client.upsert(collection_name=self.collection_name, points=points)

    def get(
        self,
        *,
        ids: Optional[Sequence[str]] = None,
        where: Optional[Dict[str, Any]] = None,
        include: Optional[Sequence[str]] = None,
    ) -> Dict[str, Any]:
        include_set = set(include or [])
        include_metadatas = not include_set or "metadatas" in include_set
        include_documents = not include_set or "documents" in include_set

        points: List[qdrant_models.Record]
        if ids is not None:
            fetched = self.client.retrieve(
                collection_name=self.collection_name,
                ids=[self._to_point_id(str(pid)) for pid in ids],
                with_payload=True,
                with_vectors=False,
            )
            fetched_map = {str(item.id): item for item in fetched}
            ordered_point_ids = [self._to_point_id(str(pid)) for pid in ids]
            points = [fetched_map[item] for item in ordered_point_ids if item in fetched_map]
        else:
            points = self._scroll(_build_filter(where))

        out_ids: List[str] = []
        out_metadatas: List[Dict[str, Any]] = []
        out_documents: List[str] = []

        for point in points:
            pid, metadata, document = self._point_to_result_item(point)
            out_ids.append(pid)
            if include_metadatas:
                out_metadatas.append(metadata)
            if include_documents:
                out_documents.append(document)

        result: Dict[str, Any] = {"ids": out_ids}
        if include_metadatas:
            result["metadatas"] = out_metadatas
        if include_documents:
            result["documents"] = out_documents
        return result

    def delete(
        self,
        *,
        ids: Optional[Sequence[str]] = None,
        where: Optional[Dict[str, Any]] = None,
    ) -> None:
        if ids is not None:
            selector = qdrant_models.PointIdsList(
                points=[self._to_point_id(str(pid)) for pid in ids]
            )
            self.client.delete(collection_name=self.collection_name, points_selector=selector)
            return
        built_filter = _build_filter(where)
        if built_filter is None:
            return
        self.client.delete(collection_name=self.collection_name, points_selector=built_filter)


def get_conversations_collection() -> QdrantPayloadCollection:
    global _conversation_collection
    if _conversation_collection is None:
        _conversation_collection = QdrantPayloadCollection("conversations")
    return _conversation_collection


def get_turns_collection() -> QdrantPayloadCollection:
    global _turns_collection
    if _turns_collection is None:
        _turns_collection = QdrantPayloadCollection("turns")
    return _turns_collection


def get_summaries_collection() -> QdrantPayloadCollection:
    global _summaries_collection
    if _summaries_collection is None:
        _summaries_collection = QdrantPayloadCollection("summaries")
    return _summaries_collection


def get_vector_store(collection_name: str = "documents"):
    from llama_index.vector_stores.qdrant import QdrantVectorStore

    return QdrantVectorStore(
        client=get_client(),
        collection_name=collection_name,
    )


def _clear_collection_points(client: QdrantClient, collection_name: str) -> None:
    # Qdrant local mode can retain stale vectors across delete/recreate cycles.
    # Explicitly delete all points to guarantee a clean state.
    client.delete(
        collection_name=collection_name,
        points_selector=qdrant_models.Filter(must=[]),
    )


def reset_collection(collection_name: str) -> None:
    client = get_client()
    try:
        if client.collection_exists(collection_name):
            _clear_collection_points(client, collection_name)
            client.delete_collection(collection_name=collection_name)
            deadline = time.time() + 5.0
            while time.time() < deadline:
                if not client.collection_exists(collection_name):
                    break
                time.sleep(0.1)
            else:
                raise RuntimeError(
                    f"Collection '{collection_name}' still exists after delete"
                )
    except Exception as exc:
        logger.warning(
            "Failed to reset Qdrant collection '%s': %s",
            collection_name,
            exc,
        )
        raise


def recreate_collection(
    collection_name: str,
    vector_size: int,
    *,
    distance: qdrant_models.Distance = qdrant_models.Distance.COSINE,
) -> None:
    if int(vector_size) <= 0:
        raise ValueError(f"vector_size must be > 0, got {vector_size!r}")

    client = get_client()
    reset_collection(collection_name)
    try:
        client.create_collection(
            collection_name=collection_name,
            vectors_config=qdrant_models.VectorParams(
                size=int(vector_size),
                distance=distance,
            ),
        )
        if client.collection_exists(collection_name):
            _clear_collection_points(client, collection_name)
    except Exception as exc:
        logger.warning(
            "Failed to recreate Qdrant collection '%s' (size=%s): %s",
            collection_name,
            vector_size,
            exc,
        )
        raise
