"""Pinecone integration helpers for research chunk storage and retrieval.

This module owns all Pinecone and embedding lifecycle concerns:
- Singleton initialization for Pinecone and OpenAI clients
- Automatic index creation and readiness checks
- Chunking, embedding, upsert, query, and cleanup helpers
- Defensive error handling so agent flows can continue gracefully
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import os
import re
import time
from functools import lru_cache
from typing import Any, Dict, List, Optional

from openai import OpenAI
from pinecone import Pinecone, ServerlessSpec

logger = logging.getLogger(__name__)

DEFAULT_INDEX_NAME = "research-chunks"
DEFAULT_DIMENSION = 1536
DEFAULT_METRIC = "cosine"
DEFAULT_CLOUD = "aws"
DEFAULT_REGION = "us-east-1"
MAX_EMBED_TEXT_CHARS = 8000
EMBEDDING_MODEL = "text-embedding-3-small"

_PINECONE_CLIENT: Optional[Pinecone] = None
_OPENAI_CLIENT: Optional[OpenAI] = None
_INDEX = None


def _clean_text(text: str) -> str:
    """Normalize whitespace and remove control characters before embedding."""
    if not text:
        return ""
    cleaned = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]+", " ", text)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned[:MAX_EMBED_TEXT_CHARS]


def _env_or_raise(name: str, message: str) -> str:
    """Return a required environment variable or raise a clear runtime error."""
    value = os.getenv(name)
    if not value:
        raise RuntimeError(message)
    return value


def _metadata_value(value: Any) -> Any:
    """Convert metadata values into Pinecone-friendly primitives."""
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, list):
        return ", ".join(str(item) for item in value)
    if isinstance(value, dict):
        return str(value)
    return str(value)


def _get_index_name() -> str:
    """Return the configured index name with a safe default."""
    return os.getenv("PINECONE_INDEX", DEFAULT_INDEX_NAME)


def _get_index_host() -> Optional[str]:
    """Return the dashboard-provided Pinecone host when available."""
    host = os.getenv("PINECONE_INDEX_HOST")
    if not host:
        return None
    cleaned = host.strip()
    if not cleaned:
        return None
    if cleaned.lower().startswith("replace_with_") or cleaned.lower().startswith("your_"):
        return None
    return cleaned


def _get_index_cloud_region() -> tuple[str, str]:
    """Return the serverless cloud and region used when auto-creating an index."""
    cloud = os.getenv("PINECONE_CLOUD", DEFAULT_CLOUD)
    region = os.getenv("PINECONE_REGION", DEFAULT_REGION)
    return cloud, region


def _get_index_dimension() -> int:
    """Return the configured embedding dimension with validation."""
    raw_value = os.getenv("PINECONE_DIM", str(DEFAULT_DIMENSION))
    try:
        dimension = int(raw_value)
    except ValueError as exc:
        raise RuntimeError(f"Invalid PINECONE_DIM value: {raw_value}") from exc
    if dimension <= 0:
        raise RuntimeError("PINECONE_DIM must be a positive integer")
    return dimension


def _describe_index_status(index_name: str) -> Dict[str, Any]:
    """Return the current Pinecone index description with broad compatibility."""
    client = get_pinecone_client()
    try:
        description = client.describe_index(index_name)
    except Exception as exc:
        logger.exception("Unable to describe Pinecone index %s", index_name)
        raise RuntimeError(f"Unable to describe Pinecone index '{index_name}': {exc}") from exc

    model_dump = getattr(description, "model_dump", None)
    if callable(model_dump):
        return model_dump()
    to_dict = getattr(description, "to_dict", None)
    if callable(to_dict):
        return to_dict()
    if isinstance(description, dict):
        return description
    return {"raw": description}


def _is_ready(description: Dict[str, Any]) -> bool:
    """Inspect a Pinecone description payload and determine readiness."""
    status = description.get("status")
    if isinstance(status, dict):
        if status.get("ready") is True:
            return True
        state = str(status.get("state", "")).lower()
        if state == "ready":
            return True
    state = str(description.get("state", "")).lower()
    return state == "ready"


@lru_cache(maxsize=1)
def get_pinecone_client() -> Pinecone:
    """Return a singleton Pinecone client after validating the API key."""
    global _PINECONE_CLIENT
    if _PINECONE_CLIENT is not None:
        return _PINECONE_CLIENT

    api_key = _env_or_raise(
        "PINECONE_API_KEY",
        "PINECONE_API_KEY is missing. Add your Pinecone API key to the backend environment.",
    )
    try:
        _PINECONE_CLIENT = Pinecone(api_key=api_key)
        logger.info("Pinecone client initialized")
        return _PINECONE_CLIENT
    except Exception as exc:
        logger.exception("Failed to initialize Pinecone client")
        raise RuntimeError(f"Failed to initialize Pinecone client: {exc}") from exc


@lru_cache(maxsize=1)
def get_openai_client() -> OpenAI:
    """Return a singleton OpenAI client after validating the API key."""
    global _OPENAI_CLIENT
    if _OPENAI_CLIENT is not None:
        return _OPENAI_CLIENT

    api_key = _env_or_raise(
        "OPENAI_API_KEY",
        "OPENAI_API_KEY is missing. Add your OpenAI API key to the backend environment.",
    )
    try:
        _OPENAI_CLIENT = OpenAI(api_key=api_key)
        logger.info("OpenAI client initialized")
        return _OPENAI_CLIENT
    except Exception as exc:
        logger.exception("Failed to initialize OpenAI client")
        raise RuntimeError(f"Failed to initialize OpenAI client: {exc}") from exc


@lru_cache(maxsize=1)
def get_pinecone_index():
    """Return a singleton Pinecone index, creating it when necessary.

    The function validates all required environment variables, creates the index
    if it does not yet exist, and waits until Pinecone reports the index as ready.
    """
    global _INDEX
    if _INDEX is not None:
        return _INDEX

    client = get_pinecone_client()
    index_name = _get_index_name()
    dimension = _get_index_dimension()
    host = _get_index_host()

    try:
        index_names: List[str] = []
        try:
            index_list = client.list_indexes()
            if hasattr(index_list, "names"):
                index_names = list(index_list.names())
            else:
                index_names = [item.name for item in index_list]
        except Exception:
            logger.debug("Falling back to direct index description during existence check", exc_info=True)

        if index_name not in index_names:
            cloud, region = _get_index_cloud_region()
            logger.info("Creating Pinecone index %s in %s/%s", index_name, cloud, region)
            client.create_index(
                name=index_name,
                dimension=dimension,
                metric=DEFAULT_METRIC,
                spec=ServerlessSpec(cloud=cloud, region=region),
            )

        for attempt in range(30):
            description = _describe_index_status(index_name)
            if _is_ready(description):
                break
            logger.info("Waiting for Pinecone index %s to become ready (attempt %s)", index_name, attempt + 1)
            time.sleep(2)
        else:
            raise RuntimeError(f"Pinecone index '{index_name}' did not become ready in time")

        if host:
            _INDEX = client.Index(host=host)
        else:
            _INDEX = client.Index(index_name)

        logger.info("Pinecone index ready: %s", index_name)
        return _INDEX
    except Exception as exc:
        logger.exception("Failed to initialize Pinecone index")
        raise RuntimeError(f"Failed to initialize Pinecone index '{index_name}': {exc}") from exc


async def create_embedding(text: str) -> List[float]:
    """Create a single embedding with retry logic and text sanitization."""
    cleaned_text = _clean_text(text)
    if not cleaned_text:
        raise ValueError("Cannot embed empty text")

    from utils.retry import (
        async_retry,
        OPENAI_RETRY_EXCEPTIONS
    )

    @async_retry(
        max_attempts=3,
        base_delay=2,
        exceptions=OPENAI_RETRY_EXCEPTIONS
    )
    async def _create_embedding_with_retry(text_val):
        client = get_openai_client()
        response = client.embeddings.create(
            input=text_val,
            model=EMBEDDING_MODEL
        )
        return response.data[0].embedding

    embedding = await _create_embedding_with_retry(cleaned_text)
    if len(embedding) != DEFAULT_DIMENSION:
        raise RuntimeError(f"Unexpected embedding dimension: {len(embedding)}")
    return [float(value) for value in embedding]


async def create_embeddings_batch(texts: List[str]) -> List[List[float]]:
    """Creates embeddings for multiple texts in a single OpenAI API call."""
    if not texts:
        return []

    cleaned_texts = [
        (t.replace("\n", " ").strip()[:8000] or " ")
        for t in texts
    ]

    from utils.retry import (
        async_retry,
        OPENAI_RETRY_EXCEPTIONS
    )

    @async_retry(
        max_attempts=3,
        base_delay=2,
        exceptions=OPENAI_RETRY_EXCEPTIONS
    )
    async def _create_embeddings_batch_with_retry(texts_val):
        client = get_openai_client()
        response = client.embeddings.create(
            input=texts_val,
            model=EMBEDDING_MODEL
        )
        return response.data

    data = await _create_embeddings_batch_with_retry(cleaned_texts)
    sorted_data = sorted(data, key=lambda x: x.index)
    return [[float(val) for val in item.embedding] for item in sorted_data]



def chunk_text(text: str, chunk_size: int = 500, overlap: int = 50) -> List[str]:
    """Split clean text into semantic character chunks with overlap."""
    if not text:
        return []
    cleaned = _clean_text(text)
    if not cleaned:
        return []

    words = cleaned.split(" ")
    chunks: List[str] = []
    i = 0
    while i < len(words):
        chunk_words = words[i: i + chunk_size]
        chunk = " ".join(chunk_words)
        if len(chunk.strip()) > 30:
            chunks.append(chunk)
        i += chunk_size - overlap

    return chunks


def _build_vector_id(report_id: str, source_index: int, chunk_index: int, chunk_text_value: str) -> str:
    """Build a unique deterministically hashed vector ID."""
    raw = f"{report_id}_{source_index}_{chunk_index}_{chunk_text_value[:50]}"
    return hashlib.md5(raw.encode("utf-8")).hexdigest()


async def upsert_source_chunks(
    content: str,
    source_url: str,
    source_title: str,
    report_id: str,
    sub_question: str,
    source_index: int,
    credibility: Dict[str, Any],
) -> int:
    """Chunk source content, embed each chunk, and upsert them into Pinecone.

    Embedding failures are skipped per chunk so one bad segment does not block
    the rest of the source from being stored.
    """
    index = get_pinecone_index()
    chunks = chunk_text(content)
    if not chunks:
        logger.warning("No eligible chunks found for source %s", source_url)
        return 0

    credibility_payload = credibility or {}
    vectors: List[tuple[str, List[float], Dict[str, Any]]] = []

    # Batch chunk embeddings to minimize API call overhead (10 chunks per call)
    EMBED_BATCH_SIZE = 10
    all_embeddings = []
    
    for i in range(0, len(chunks), EMBED_BATCH_SIZE):
        batch = chunks[i:i + EMBED_BATCH_SIZE]
        try:
            embeddings = await create_embeddings_batch(batch)
            all_embeddings.extend(embeddings)
        except Exception as exc:
            logger.warning(
                f"Skipping embedding batch starting at index {i} from source {source_url}: {exc}"
            )
            all_embeddings.extend([None] * len(batch))

    for chunk_index, chunk in enumerate(chunks):
        if chunk_index >= len(all_embeddings) or all_embeddings[chunk_index] is None:
            logger.warning(
                "Skipping chunk %s from source %s because embedding failed",
                chunk_index,
                source_url,
            )
            continue

        embedding = all_embeddings[chunk_index]
        metadata = {
            "report_id": report_id,
            "source_url": source_url,
            "source_title": source_title,
            "sub_question": sub_question,
            "source_index": source_index,
            "chunk_index": chunk_index,
            "chunk_count": len(chunks),
            "content": chunk,
            "content_length": len(chunk),
            "credibility_rating": _metadata_value(credibility_payload.get("rating") or credibility_payload.get("label")),
            "credibility_score": _metadata_value(credibility_payload.get("score")),
            "credibility_label": _metadata_value(credibility_payload.get("label")),
            "credibility_color": _metadata_value(credibility_payload.get("color")),
            "credibility_emoji": _metadata_value(credibility_payload.get("emoji")),
        }
        vector_id = _build_vector_id(report_id, source_index, chunk_index, chunk)
        cleaned_metadata = {k: _metadata_value(v) for k, v in metadata.items()}
        cleaned_metadata = {k: v for k, v in cleaned_metadata.items() if v is not None}
        vectors.append((vector_id, embedding, cleaned_metadata))


    if not vectors:
        return 0

    from utils.retry import with_timeout

    stored = 0
    for batch_start in range(0, len(vectors), 100):
        batch = vectors[batch_start: batch_start + 100]
        batch_idx = batch_start // 100
        
        upsert_res = await with_timeout(
            asyncio.get_event_loop().run_in_executor(
                None,
                lambda: index.upsert(vectors=batch)
            ),
            timeout_seconds=30.0,
            fallback=None,
            operation_name=f"Pinecone upsert batch {batch_idx}"
        )
        
        if upsert_res is not None:
            stored += len(batch)
        else:
            logger.warning(f"Pinecone upsert batch {batch_idx} timed out or failed. Skipping batch.")

    return stored


async def query_relevant_chunks(question: str, report_id: str, top_k: int = 5) -> List[Dict[str, Any]]:
    """Return the most relevant chunks for a question within one report."""
    index = get_pinecone_index()
    embedding = await create_embedding(question)
    
    from utils.retry import with_timeout
    
    results = await with_timeout(
        asyncio.get_event_loop().run_in_executor(
            None,
            lambda: index.query(
                vector=embedding,
                top_k=top_k,
                include_metadata=True,
                filter={"report_id": {"$eq": report_id}},
            )
        ),
        timeout_seconds=10.0,
        fallback=None,
        operation_name="Pinecone query"
    )

    if results is None:
        logger.warning("Pinecone query timed out, returning empty chunks")
        return []

    matches = results.get("matches", []) if isinstance(results, dict) else getattr(results, "matches", [])
    formatted: List[Dict[str, Any]] = []
    for match in matches:
        score = getattr(match, "score", None) if not isinstance(match, dict) else match.get("score")
        if score is None or float(score) < 0.3:
            continue

        metadata = getattr(match, "metadata", None) if not isinstance(match, dict) else match.get("metadata", {})
        metadata = metadata or {}
        formatted.append(
            {
                "id": getattr(match, "id", None) if not isinstance(match, dict) else match.get("id"),
                "score": float(score),
                "content": metadata.get("content"),
                "source_url": metadata.get("source_url"),
                "source_title": metadata.get("source_title"),
                "sub_question": metadata.get("sub_question"),
                "source_index": metadata.get("source_index"),
                "chunk_index": metadata.get("chunk_index"),
                "chunk_count": metadata.get("chunk_count"),
                "report_id": metadata.get("report_id"),
                "credibility": {
                    "rating": metadata.get("credibility_rating"),
                    "score": metadata.get("credibility_score"),
                    "label": metadata.get("credibility_label"),
                    "color": metadata.get("credibility_color"),
                    "emoji": metadata.get("credibility_emoji"),
                },
            }
        )
    return formatted


async def query_claim_evidence(claim: str, report_id: str, top_k: int = 3) -> List[Dict[str, Any]]:
    """Return the strongest evidence chunks for a fact-checking claim."""
    return await query_relevant_chunks(claim, report_id=report_id, top_k=top_k)


def delete_report_chunks(report_id: str) -> bool:
    """Delete every vector associated with a report id from Pinecone."""
    index = get_pinecone_index()
    try:
        index.delete(filter={"report_id": {"$eq": report_id}})
        logger.info("Deleted Pinecone vectors for report %s", report_id)
        return True
    except Exception as exc:
        logger.exception("Failed to delete Pinecone vectors for report %s", report_id)
        raise RuntimeError(f"Failed to delete Pinecone vectors for report '{report_id}': {exc}") from exc


def get_index_stats() -> Dict[str, Any]:
    """Return a compact health summary for the Pinecone index."""
    index_name = _get_index_name()
    try:
        index = get_pinecone_index()
        stats = index.describe_index_stats()
        model_dump = getattr(stats, "model_dump", None)
        if callable(model_dump):
            stats_dict = model_dump()
        else:
            to_dict = getattr(stats, "to_dict", None)
            if callable(to_dict):
                stats_dict = to_dict()
            elif isinstance(stats, dict):
                stats_dict = stats
            else:
                stats_dict = {"raw": stats}

        total_vectors = stats_dict.get("total_vector_count") or stats_dict.get("totalVectors") or 0
        dimension = _get_index_dimension()
        description = _describe_index_status(index_name)
        status = description.get("status", {})
        if isinstance(status, dict):
            readiness = status.get("state") or ("Ready" if status.get("ready") else "NotReady")
        else:
            readiness = description.get("state", "unknown")

        return {
            "status": readiness,
            "index_name": index_name,
            "host": _get_index_host(),
            "dimension": dimension,
            "metric": DEFAULT_METRIC,
            "total_vectors": total_vectors,
            "namespaces": stats_dict.get("namespaces", {}),
            "raw": stats_dict,
        }
    except Exception as exc:
        logger.exception("Failed to fetch Pinecone index stats")
        return {
            "status": "error",
            "index_name": index_name,
            "error": str(exc),
        }
