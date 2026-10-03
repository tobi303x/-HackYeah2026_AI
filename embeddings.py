import os
import hashlib
from typing import List, Optional
import chromadb
from chromadb.api.types import Documents, EmbeddingFunction, Embeddings

try:
    from google import genai
    from google.genai import types
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False


class MockEmbeddingFunction(EmbeddingFunction[Documents]):
    """Fallback embedding function for local testing without an active Gemini API key."""
    def __init__(self, dimension: int = 3072):
        self.dimension = dimension

    def __call__(self, input: Documents) -> Embeddings:
        embeddings: Embeddings = []
        for text in input:
            seed = int(hashlib.md5(text.encode("utf-8")).hexdigest(), 16)
            vec = [((seed + i * 31) % 1000) / 1000.0 for i in range(self.dimension)]
            norm = sum(x * x for x in vec) ** 0.5 or 1.0
            normalized = [x / norm for x in vec]
            embeddings.append(normalized)
        return embeddings


class GeminiEmbeddingFunction(EmbeddingFunction[Documents]):
    """
    Custom Chroma DB EmbeddingFunction using the official Google GenAI SDK.
    Defaults to 'gemini-embedding-2', Google's premier multimodal & text embedding model.
    """
    def __init__(self, api_key: str, model_name: str = "gemini-embedding-2"):
        if not api_key:
            raise ValueError("GEMINI_API_KEY is required to initialize GeminiEmbeddingFunction.")
        if not GENAI_AVAILABLE:
            raise ImportError("The 'google-genai' package is not installed.")

        self.api_key = api_key.strip("'\"")
        self.model_name = model_name
        self.client = genai.Client(api_key=self.api_key)

    def __call__(self, input: Documents) -> Embeddings:
        if not input:
            return []

        # Batch in chunks of 50
        batch_size = 50
        all_embeddings: Embeddings = []

        for i in range(0, len(input), batch_size):
            batch = input[i : i + batch_size]
            # Wrap each text in a Content object to ensure separate embeddings are returned
            contents = [
                types.Content(parts=[types.Part.from_text(text=t)])
                for t in batch
            ]
            response = self.client.models.embed_content(
                model=self.model_name,
                contents=contents,
            )
            for item in response.embeddings:
                all_embeddings.append(item.values)

        return all_embeddings


def get_embedding_function(api_key: Optional[str] = None, model_name: str = "gemini-embedding-2", allow_mock: bool = False):
    """
    Factory to retrieve the appropriate embedding function.
    Falls back to MockEmbeddingFunction if allow_mock is True and api_key is missing.
    """
    cleaned_key = (api_key or "").strip("'\"")
    if cleaned_key:
        return GeminiEmbeddingFunction(api_key=cleaned_key, model_name=model_name)
    elif allow_mock:
        return MockEmbeddingFunction()
    else:
        raise ValueError(
            "GEMINI_API_KEY is not set. Please set the GEMINI_API_KEY environment variable "
            "or enable MOCK_EMBEDDINGS=true for local mock testing."
        )
