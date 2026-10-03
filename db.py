import os
from typing import Optional, List, Dict, Any
import chromadb
from config import config
from embeddings import get_embedding_function

_client: Optional[chromadb.ClientAPI] = None

def get_chroma_client() -> chromadb.ClientAPI:
    """Returns singleton PersistentClient instance for Chroma DB."""
    global _client
    if _client is None:
        os.makedirs(config.CHROMA_PERSIST_DIRECTORY, exist_ok=True)
        _client = chromadb.PersistentClient(path=config.CHROMA_PERSIST_DIRECTORY)
    return _client

def _get_embedding_fn():
    return get_embedding_function(
        api_key=config.GEMINI_API_KEY,
        model_name=config.GEMINI_EMBEDDING_MODEL,
        allow_mock=config.MOCK_EMBEDDINGS
    )

def get_collection(name: Optional[str] = None):
    """
    Returns or creates a collection configured with the Gemini embedding function.
    Defaults to config.DEFAULT_COLLECTION_NAME.
    """
    client = get_chroma_client()
    col_name = name or config.DEFAULT_COLLECTION_NAME
    embedding_fn = _get_embedding_fn()

    return client.get_or_create_collection(
        name=col_name,
        embedding_function=embedding_fn,
        metadata={"hnsw:space": "cosine"}
    )

def create_new_collection(name: str, metadata: Optional[Dict[str, Any]] = None):
    """
    Explicitly creates a new collection.
    Raises ValueError if collection already exists.
    """
    client = get_chroma_client()
    embedding_fn = _get_embedding_fn()
    
    col_meta = {"hnsw:space": "cosine"}
    if metadata:
        col_meta.update(metadata)

    return client.create_collection(
        name=name,
        embedding_function=embedding_fn,
        metadata=col_meta
    )

def delete_collection_by_name(name: str):
    """Deletes a collection by name."""
    client = get_chroma_client()
    client.delete_collection(name=name)

def list_collections_info() -> List[Dict[str, Any]]:
    """Lists all collections and their item counts."""
    client = get_chroma_client()
    collections = client.list_collections()
    info = []
    for col in collections:
        info.append({
            "name": col.name,
            "count": col.count(),
            "metadata": col.metadata
        })
    return info
