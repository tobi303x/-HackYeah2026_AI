import os
from dotenv import load_dotenv

# Load environment variables from .env file if present
load_dotenv()

class Config:
    GEMINI_API_KEY = (
        os.getenv("GEMINI_API_KEY")
        or os.getenv("GOOGLE_GENAI_KEY")
        or os.getenv("GOOGLE_API_KEY")
        or ""
    ).strip("'\"")
    GEMINI_EMBEDDING_MODEL = os.getenv("GEMINI_EMBEDDING_MODEL", "gemini-embedding-2")
    GEMINI_GENERATION_MODEL = os.getenv("GEMINI_GENERATION_MODEL", "gemini-3.8-flash")
    GEMINI_THINKING_LEVEL = os.getenv("GEMINI_THINKING_LEVEL", "high")
    CHROMA_PERSIST_DIRECTORY = os.getenv("CHROMA_PERSIST_DIRECTORY", os.path.join(os.getcwd(), "chroma_data"))
    DEFAULT_COLLECTION_NAME = os.getenv("DEFAULT_COLLECTION_NAME", "rops_innovations")
    MOCK_EMBEDDINGS = os.getenv("MOCK_EMBEDDINGS", "False").lower() in ("true", "1", "yes")
    
    # API Authentication Secret Key (Read & Document Ops)
    API_AUTH_KEY = (
        os.getenv("API_AUTH_KEY")
        or os.getenv("API_KEY")
        or ""
    ).strip("'\"")

    # Admin API Key (Gates Collection Creation and Deletion)
    ADMIN_API_KEY = (
        os.getenv("ADMIN_API_KEY")
        or os.getenv("API_ADMIN_KEY")
        or ""
    ).strip("'\"")

    # Security Configuration
    CORS_ORIGINS = os.getenv("CORS_ORIGINS", "*").split(",")
    RATE_LIMIT_DEFAULT = os.getenv("RATE_LIMIT_DEFAULT", "120 per minute")
    MAX_CONTENT_LENGTH_MB = int(os.getenv("MAX_CONTENT_LENGTH_MB", 16))

    PORT = int(os.getenv("PORT", 5000))
    DEBUG = os.getenv("DEBUG", "False").lower() in ("true", "1", "yes")

config = Config()
