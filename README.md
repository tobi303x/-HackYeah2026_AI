# HackYeah 2026 - Flask API with Chroma DB & Gemini Embeddings

Production-ready Flask REST API integrated with an embedded, persistent Chroma DB vector database and Google Gemini custom embeddings (`google-genai` SDK). Designed for seamless deployment on **Coolify** and rapid local development.

---

## 🛠 Features

- **API Key Authentication**: Protects endpoints requiring `api_key` directly in JSON payload (or via query/header).
- **Embedded Chroma DB**: Single-container deployment with persistent volume storage (`/app/chroma_data`).
- **Pydantic Validation**: Strict schema validation for all API inputs (`schemas.py`), returning standardized HTTP 422 error structures.
- **Custom Gemini Embeddings**: Implements `chromadb.EmbeddingFunction` via the modern `google-genai` SDK using `gemini-embedding-2` (3072-dim, 8192-token context window with cosine distance).
- **Mock Fallback for Local Testing**: Allows testing the complete vector pipeline locally even without an active Gemini API key (`MOCK_EMBEDDINGS=true`).
- **SQLite Concurrency-Safe Gunicorn**: Configured with 1 worker and 4 threads to prevent SQLite file lock contention while supporting concurrent requests.
- **Full Collection & Vector Management API**:
  - `POST /api/collections`: Create new custom collections with metadata.
  - `GET /api/collections`: List all collections and document counts.
  - `GET /api/collections/<name>`: Get details and count for a specific collection.
  - `DELETE /api/collections/<name>`: Delete a collection and all of its records.
  - `POST /api/documents`: Ingest new documents with metadata and IDs.
  - `PUT /api/documents`: Edit/update existing documents or metadatas.
  - `POST /api/documents/upsert`: Upsert documents (insert if missing, update if existing).
  - `GET /api/documents`: Retrieve documents by ID or list with limit/offset.
  - `DELETE /api/documents`: Remove documents by ID.
  - `POST /api/query`: Vector similarity search.
  - `GET /health`: Health check with Chroma DB status.

---

## 📋 Environment Configuration

Create a `.env` file in the project root:

```ini
# Google Gemini API Key (Required for live embeddings)
GEMINI_API_KEY=your_gemini_api_key_here

# Embedding Model (Default: gemini-embedding-001)
GEMINI_EMBEDDING_MODEL=gemini-embedding-001

# Chroma DB Persistent Storage Directory
# In Docker / Coolify container: /app/chroma_data
CHROMA_PERSIST_DIRECTORY=/app/chroma_data

# Default Collection Name
DEFAULT_COLLECTION_NAME=hackyeah_docs

# Set to true to test locally without an API key
MOCK_EMBEDDINGS=false

# Port configuration
PORT=5000
```

---

## 🚀 Local Testing & Development

### Run with Docker Compose (Recommended)

1. Start the container with persistent storage:
   ```bash
   docker compose up --build
   ```
2. In another terminal, run the automated test suite:
   ```bash
   python3 test_api.py
   ```

---

## ☁️ Coolify Deployment Guide

1. **Deploy as Docker Compose OR Dockerfile**:
   - In Coolify, create a new service from your Git repository (`feature/flask-api` or `main`).
2. **Persistent Storage (Crucial for Chroma DB)**:
   - Go to **Storages / Volumes** in Coolify.
   - Add a persistent volume mount:
     - **Destination Path**: `/app/chroma_data`
3. **Environment Variables**:
   - Add `GEMINI_API_KEY` under the application's **Environment Variables** tab in Coolify.
   - (Optional) `GEMINI_EMBEDDING_MODEL=gemini-embedding-001`.
4. **Port Configuration**:
   - Expose port `5000`.

---

## 📡 API Endpoints Reference

### 1. Collections

#### Create Collection (`POST /api/collections`)
```json
POST /api/collections
Content-Type: application/json

{
  "name": "my_new_collection",
  "metadata": {"topic": "cybersecurity"}
}
```

#### List Collections (`GET /api/collections`)
```
GET /api/collections
```

#### Delete Collection (`DELETE /api/collections/<collection_name>`)
```
DELETE /api/collections/my_new_collection
```

---

### 2. Documents

#### Ingest Documents (`POST /api/documents`)
```json
POST /api/documents
Content-Type: application/json

{
  "documents": ["HackYeah is Europe's largest hackathon in Krakow."],
  "metadatas": [{"source": "event_page"}],
  "ids": ["doc-1"],
  "collection_name": "hackyeah_docs"
}
```

#### Edit / Update Existing Record (`PUT /api/documents`)
```json
PUT /api/documents
Content-Type: application/json

{
  "ids": ["doc-1"],
  "documents": ["HackYeah 2026 is Europe's largest offline hackathon in Tauron Arena Krakow."],
  "metadatas": [{"source": "event_page", "verified": true}],
  "collection_name": "hackyeah_docs"
}
```

#### Upsert Documents (`POST /api/documents/upsert`)
```json
POST /api/documents/upsert
Content-Type: application/json

{
  "ids": ["doc-1", "doc-2"],
  "documents": ["Text 1", "Text 2"],
  "metadatas": [{"cat": "1"}, {"cat": "2"}],
  "collection_name": "hackyeah_docs"
}
```

#### Semantic Similarity Query (`POST /api/query`)
```json
POST /api/query
Content-Type: application/json

{
  "query": "Where is the big hackathon located?",
  "n_results": 3,
  "collection_name": "hackyeah_docs"
}
```

#### Retrieve Documents (`GET /api/documents`)
- `GET /api/documents?limit=10&offset=0`
- `GET /api/documents?ids=doc-1,doc-2`

#### Delete Documents (`DELETE /api/documents`)
```json
DELETE /api/documents
Content-Type: application/json

{
  "ids": ["doc-1"],
  "collection_name": "hackyeah_docs"
}
```