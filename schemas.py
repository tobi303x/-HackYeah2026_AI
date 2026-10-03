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
    max_distance: Optional[float] = Field(None, ge=0.0, le=2.0, description="Maximum cosine distance cutoff (relevance threshold). Only matches with distance <= max_distance are returned.")
    distance_threshold: Optional[float] = Field(None, ge=0.0, le=2.0, description="Alias for max_distance.")

    @model_validator(mode="after")
    def check_query(self):
        if not self.query and not self.query_texts:
            raise ValueError("Either 'query' (string) or 'query_texts' (list) must be provided.")
        if self.distance_threshold is not None and self.max_distance is None:
            self.max_distance = self.distance_threshold
        return self


class ReportQueryInput(BaseAuthInput):
    query: str = Field(..., min_length=2, description="Polish natural language search query for policy reports")
    n_results: int = Field(5, ge=1, le=50, description="Number of results to return")
    collection_name: str = Field("rops_reports", description="Target collection, defaults to rops_reports")
    year_from: Optional[int] = Field(None, ge=2000, le=2035, description="Filter: year >= year_from")
    year_to: Optional[int] = Field(None, ge=2000, le=2035, description="Filter: year <= year_to")
    category: Optional[str] = Field(None, description="Filter: topic category slug")
    only_statistics: Optional[bool] = Field(None, description="Filter: only chunks containing quantitative/survey data")
    max_distance: Optional[float] = Field(0.55, ge=0.0, le=2.0, description="Maximum cosine distance cutoff")
    where: Optional[Dict[str, Any]] = Field(None, description="Optional custom Chroma metadata filtering expression")


class UnifiedRAGQueryInput(BaseAuthInput):
    query: str = Field(..., min_length=2, description="Problem statement or policy question")
    n_reports: int = Field(4, ge=0, le=20, description="Number of top matches from rops_reports")
    n_innovations: int = Field(3, ge=0, le=10, description="Number of top matches from rops_innovations")
    max_distance: Optional[float] = Field(0.55, ge=0.0, le=2.0, description="Cosine distance threshold")
    year_from: Optional[int] = Field(None, ge=2000, le=2035, description="Optional filter for report publication year")
    category: Optional[str] = Field(None, description="Optional topic category slug")


class AgentEvaluateInput(BaseAuthInput):
    query: str = Field(..., min_length=3, description="Project concept, social deficit problem, or target group description")
    powiat: Optional[str] = Field(None, description="Optional territory focus in Małopolska (e.g. olkuski, chrzanowski, tarnowski)")
    applicant_type: Optional[str] = Field(None, description="Optional applicant type (JST, NGO, PES)")
    n_reports: int = Field(4, ge=1, le=15, description="Number of empirical deficit report chunks to retrieve")
    n_innovations: int = Field(3, ge=1, le=10, description="Number of social innovations to retrieve")
    n_grants: int = Field(3, ge=1, le=10, description="Number of grant regulation/implementation chunks to retrieve")
    max_distance: Optional[float] = Field(0.55, ge=0.0, le=2.0, description="Cosine distance threshold cutoff")



