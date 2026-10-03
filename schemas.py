from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field, field_validator, model_validator


class BaseAuthInput(BaseModel):
    api_key: Optional[str] = Field(None, description="API authorization key (required if authentication is enabled)")
    admin_api_key: Optional[str] = Field(None, description="Admin authorization key (required for collection creation/deletion)")


class CreateCollectionInput(BaseAuthInput):
    name: str = Field(..., min_length=3, max_length=63, description="Collection name")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Optional collection metadata")

    @field_validator("name")
    def validate_name(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Collection name cannot be empty")
        return v


class AddDocumentsInput(BaseAuthInput):
    documents: List[str] = Field(..., min_length=1, description="List of document texts to embed")
    metadatas: Optional[List[Dict[str, Any]]] = Field(None, description="Optional metadata dicts")
    ids: Optional[List[str]] = Field(None, description="Optional custom document IDs")
    collection_name: Optional[str] = Field(None, description="Target collection name")

    @model_validator(mode="after")
    def check_lengths(self):
        doc_len = len(self.documents)
        if self.metadatas and len(self.metadatas) != doc_len:
            raise ValueError(f"'metadatas' length ({len(self.metadatas)}) must match 'documents' length ({doc_len})")
        if self.ids and len(self.ids) != doc_len:
            raise ValueError(f"'ids' length ({len(self.ids)}) must match 'documents' length ({doc_len})")
        return self


class UpdateDocumentsInput(BaseAuthInput):
    ids: List[str] = Field(..., min_length=1, description="List of document IDs to update")
    documents: Optional[List[str]] = Field(None, description="Updated document texts")
    metadatas: Optional[List[Dict[str, Any]]] = Field(None, description="Updated metadata dicts")
    collection_name: Optional[str] = Field(None, description="Target collection name")
    upsert: bool = Field(False, description="Insert if ID is missing")

    @model_validator(mode="after")
    def validate_update(self):
        id_len = len(self.ids)
        if not self.documents and not self.metadatas:
            raise ValueError("Either 'documents' or 'metadatas' must be provided to update.")
        if self.documents and len(self.documents) != id_len:
            raise ValueError(f"'documents' length ({len(self.documents)}) must match 'ids' length ({id_len})")
        if self.metadatas and len(self.metadatas) != id_len:
            raise ValueError(f"'metadatas' length ({len(self.metadatas)}) must match 'ids' length ({id_len})")
        if self.upsert and not self.documents:
            raise ValueError("'documents' are required when upsert is enabled.")
        return self


class UpsertDocumentsInput(BaseAuthInput):
    ids: List[str] = Field(..., min_length=1, description="List of document IDs to upsert")
    documents: List[str] = Field(..., min_length=1, description="Document texts")
    metadatas: Optional[List[Dict[str, Any]]] = Field(None, description="Metadata dicts")
    collection_name: Optional[str] = Field(None, description="Target collection name")

    @model_validator(mode="after")
    def check_lengths(self):
        id_len = len(self.ids)
        if len(self.documents) != id_len:
            raise ValueError(f"'documents' length ({len(self.documents)}) must match 'ids' length ({id_len})")
        if self.metadatas and len(self.metadatas) != id_len:
            raise ValueError(f"'metadatas' length ({len(self.metadatas)}) must match 'ids' length ({id_len})")
        return self


class DeleteDocumentsInput(BaseAuthInput):
    ids: List[str] = Field(..., min_length=1, description="Document IDs to delete")
    collection_name: Optional[str] = Field(None, description="Target collection name")


class QueryInput(BaseAuthInput):
    query: Optional[str] = Field(None, description="Search query string")
    query_texts: Optional[List[str]] = Field(None, description="Batch query strings")
    n_results: int = Field(5, ge=1, le=100, description="Number of results to return")
    where: Optional[Dict[str, Any]] = Field(None, description="Chroma metadata filtering expression")
    collection_name: Optional[str] = Field(None, description="Target collection name")

    @model_validator(mode="after")
    def check_query(self):
        if not self.query and not self.query_texts:
            raise ValueError("Either 'query' (string) or 'query_texts' (list) must be provided.")
        return self
