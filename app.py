import os
import uuid
import logging
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from werkzeug.exceptions import HTTPException
from pydantic import ValidationError

from config import config
from auth import require_api_key, require_admin_key
from db import (
    get_collection,
    create_new_collection,
    delete_collection_by_name,
    list_collections_info,
    get_chroma_client
)
from schemas import (
    CreateCollectionInput,
    AddDocumentsInput,
    UpdateDocumentsInput,
    UpsertDocumentsInput,
    DeleteDocumentsInput,
    QueryInput
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("hackyeah_api")

app = Flask(__name__)

# ----------------- Security Enhancements -----------------

# 1. Payload size limit (DoS protection)
app.config['MAX_CONTENT_LENGTH'] = config.MAX_CONTENT_LENGTH_MB * 1024 * 1024

# 2. CORS (Cross-Origin Resource Sharing)
CORS(app, resources={r"/*": {"origins": config.CORS_ORIGINS}})

# 3. Rate Limiting (Abuse & Quota Protection)
limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=[config.RATE_LIMIT_DEFAULT],
    storage_uri="memory://"
)

# 4. HTTP Security Headers (OWASP)
@app.after_request
def add_security_headers(response):
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    return response

# 5. Sanitized Error Handlers (Information Disclosure Protection)
@app.errorhandler(413)
def request_entity_too_large(e):
    return jsonify({
        "status": "error",
        "message": f"Payload too large. Maximum allowed size is {config.MAX_CONTENT_LENGTH_MB} MB."
    }), 413

@app.errorhandler(429)
def ratelimit_exceeded(e):
    return jsonify({
        "status": "error",
        "message": f"Rate limit exceeded: {e.description}"
    }), 429

@app.errorhandler(Exception)
def handle_unhandled_exception(e):
    if isinstance(e, HTTPException):
        return jsonify({
            "status": "error",
            "message": e.description
        }), e.code

    logger.error(f"Internal server error: {e}", exc_info=True)
    return jsonify({
        "status": "error",
        "message": "Internal server error. The request could not be processed."
    }), 500

def format_pydantic_errors(err: ValidationError):
    return [
        {
            "field": " -> ".join(str(loc) for loc in e.get("loc", [])),
            "message": e.get("msg", ""),
            "type": e.get("type", "")
        }
        for e in err.errors()
    ]

# ----------------- Documentation & System -----------------

@app.route('/', methods=['GET'])
def index():
    return jsonify({
        "name": "HackYeah 2026 - Flask ChromaDB API",
        "status": "online",
        "embedding_model": config.GEMINI_EMBEDDING_MODEL,
        "auth_enabled": bool(config.API_AUTH_KEY),
        "security": {
            "rate_limit": config.RATE_LIMIT_DEFAULT,
            "max_payload_mb": config.MAX_CONTENT_LENGTH_MB,
            "timing_attack_protection": True,
            "security_headers": True,
            "cors_enabled": True
        },
        "docs": {
            "swagger_ui": "GET /docs",
            "openapi_spec": "GET /openapi.json",
            "health": "GET /health",
            "list_collections": "GET /api/collections",
            "create_collection": "POST /api/collections",
            "get_collection": "GET /api/collections/<collection_name>",
            "delete_collection": "DELETE /api/collections/<collection_name>",
            "add_documents": "POST /api/documents",
            "update_documents": "PUT /api/documents",
            "upsert_documents": "POST /api/documents/upsert",
            "get_documents": "GET /api/documents",
            "delete_documents": "DELETE /api/documents",
            "query": "POST /api/query"
        }
    })

@app.route('/openapi.json', methods=['GET'])
def get_openapi_spec():
    """Serves the OpenAPI specification file."""
    base_dir = os.path.dirname(os.path.abspath(__file__))
    return send_from_directory(base_dir, 'openapi.json', mimetype='application/json')

@app.route('/docs', methods=['GET'])
def swagger_ui():
    """Interactive Swagger UI for frontend and API exploration."""
    return """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>HackYeah 2026 - API Documentation</title>
  <link rel="stylesheet" href="https://unpkg.com/swagger-ui-dist@5/swagger-ui.css" />
  <link rel="icon" type="image/png" href="https://unpkg.com/swagger-ui-dist@5/favicon-32x32.png" />
  <style>
    body { margin: 0; background: #fafafa; }
    .topbar { display: none; }
  </style>
</head>
<body>
  <div id="swagger-ui"></div>
  <script src="https://unpkg.com/swagger-ui-dist@5/swagger-ui-bundle.js"></script>
  <script>
    window.onload = () => {
      SwaggerUIBundle({
        url: '/openapi.json',
        dom_id: '#swagger-ui',
        deepLinking: true,
        presets: [
          SwaggerUIBundle.presets.apis
        ]
      });
    };
  </script>
</body>
</html>"""

@app.route('/health', methods=['GET'])
def health():
    try:
        client = get_chroma_client()
        collections = client.list_collections()
        has_api_key = bool(config.GEMINI_API_KEY)
        
        return jsonify({
            "status": "healthy",
            "chroma_storage": config.CHROMA_PERSIST_DIRECTORY,
            "embedding_model": config.GEMINI_EMBEDDING_MODEL,
            "gemini_api_key_configured": has_api_key,
            "auth_enabled": bool(config.API_AUTH_KEY),
            "admin_auth_enabled": bool(config.ADMIN_API_KEY),
            "mock_embeddings_enabled": config.MOCK_EMBEDDINGS,
            "collections_count": len(collections)
        }), 200
    except Exception as e:
        logger.error(f"Health check failure: {e}")
        return jsonify({
            "status": "unhealthy",
            "error": "Storage or database service unreachable."
        }), 500

# ----------------- Collection Management (Protected) -----------------

@app.route('/api/collections', methods=['GET'])
@require_api_key
def get_collections():
    """Lists all collections and their metadata and item counts."""
    try:
        collections = list_collections_info()
        return jsonify({
            "status": "success",
            "collections": collections
        }), 200
    except Exception as e:
        logger.error(f"Error fetching collections: {e}")
        return jsonify({"status": "error", "message": "Failed to list collections."}), 500

@app.route('/api/collections', methods=['POST'])
@require_admin_key
def create_collection_route():
    """
    Create a new collection in Chroma DB with Pydantic validation & auth.
    Requires ADMIN_API_KEY.
    """
    raw_data = request.get_json() or {}
    try:
        validated = CreateCollectionInput.model_validate(raw_data)
    except ValidationError as err:
        return jsonify({"status": "error", "message": "Validation failed", "errors": format_pydantic_errors(err)}), 422

    try:
        col = create_new_collection(name=validated.name, metadata=validated.metadata)
        return jsonify({
            "status": "success",
            "message": f"Collection '{col.name}' created successfully.",
            "collection": {
                "name": col.name,
                "count": col.count(),
                "metadata": col.metadata
            }
        }), 201
    except Exception as e:
        logger.warning(f"Collection creation error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 400

@app.route('/api/collections/<collection_name>', methods=['GET'])
@require_api_key
def get_single_collection(collection_name):
    """Retrieve info about a specific collection."""
    try:
        col = get_collection(name=collection_name)
        return jsonify({
            "status": "success",
            "collection": {
                "name": col.name,
                "count": col.count(),
                "metadata": col.metadata
            }
        }), 200
    except Exception as e:
        return jsonify({"status": "error", "message": f"Collection '{collection_name}' not found."}), 404

@app.route('/api/collections/<collection_name>', methods=['DELETE'])
@require_admin_key
def delete_collection_route(collection_name):
    """
    Delete a collection and all of its records.
    Requires ADMIN_API_KEY.
    """
    try:
        delete_collection_by_name(collection_name)
        return jsonify({
            "status": "success",
            "message": f"Collection '{collection_name}' deleted successfully."
        }), 200
    except Exception as e:
        logger.error(f"Error deleting collection {collection_name}: {e}")
        return jsonify({"status": "error", "message": "Failed to delete collection."}), 500

# ----------------- Document Operations (Protected) -----------------

@app.route('/api/documents', methods=['POST'])
@require_api_key
def add_documents():
    """
    Ingest new documents into Chroma DB with Pydantic validation & auth.
    """
    raw_data = request.get_json() or {}
    try:
        validated = AddDocumentsInput.model_validate(raw_data)
    except ValidationError as err:
        return jsonify({"status": "error", "message": "Validation failed", "errors": format_pydantic_errors(err)}), 422

    doc_ids = validated.ids if validated.ids else [str(uuid.uuid4()) for _ in validated.documents]

    try:
        collection = get_collection(name=validated.collection_name)
        collection.add(
            documents=validated.documents,
            metadatas=validated.metadatas,
            ids=doc_ids
        )
        return jsonify({
            "status": "success",
            "collection": collection.name,
            "added_count": len(validated.documents),
            "ids": doc_ids
        }), 201
    except Exception as e:
        logger.error(f"Failed to add documents: {e}")
        return jsonify({"status": "error", "message": "Failed to add documents to collection."}), 500

@app.route('/api/documents', methods=['PUT'])
@require_api_key
def update_documents():
    """
    Edit/update existing records in a collection with Pydantic validation & auth.
    """
    raw_data = request.get_json() or {}
    try:
        validated = UpdateDocumentsInput.model_validate(raw_data)
    except ValidationError as err:
        return jsonify({"status": "error", "message": "Validation failed", "errors": format_pydantic_errors(err)}), 422

    try:
        collection = get_collection(name=validated.collection_name)
        if validated.upsert:
            collection.upsert(
                ids=validated.ids,
                documents=validated.documents,
                metadatas=validated.metadatas
            )
            action = "upserted"
        else:
            collection.update(
                ids=validated.ids,
                documents=validated.documents,
                metadatas=validated.metadatas
            )
            action = "updated"

        return jsonify({
            "status": "success",
            "action": action,
            "collection": collection.name,
            "ids": validated.ids
        }), 200
    except Exception as e:
        logger.error(f"Failed to update documents: {e}")
        return jsonify({"status": "error", "message": "Failed to update documents in collection."}), 500

@app.route('/api/documents/upsert', methods=['POST'])
@require_api_key
def upsert_documents():
    """
    Upsert documents with Pydantic validation & auth.
    """
    raw_data = request.get_json() or {}
    try:
        validated = UpsertDocumentsInput.model_validate(raw_data)
    except ValidationError as err:
        return jsonify({"status": "error", "message": "Validation failed", "errors": format_pydantic_errors(err)}), 422

    try:
        collection = get_collection(name=validated.collection_name)
        collection.upsert(
            ids=validated.ids,
            documents=validated.documents,
            metadatas=validated.metadatas
        )
        return jsonify({
            "status": "success",
            "action": "upserted",
            "collection": collection.name,
            "ids": validated.ids
        }), 200
    except Exception as e:
        logger.error(f"Failed to upsert documents: {e}")
        return jsonify({"status": "error", "message": "Failed to upsert documents."}), 500

@app.route('/api/documents', methods=['GET'])
@require_api_key
def get_documents():
    """
    Retrieve documents by ID or list with pagination (Protected).
    """
    try:
        ids_param = request.args.get("ids")
        collection_name = request.args.get("collection_name")
        limit = int(request.args.get("limit", 10))
        offset = int(request.args.get("offset", 0))

        collection = get_collection(name=collection_name)

        if ids_param:
            ids = [i.strip() for i in ids_param.split(",") if i.strip()]
            results = collection.get(ids=ids)
        else:
            results = collection.get(limit=limit, offset=offset)

        return jsonify({
            "status": "success",
            "collection": collection.name,
            "data": results
        }), 200
    except Exception as e:
        logger.error(f"Failed to get documents: {e}")
        return jsonify({"status": "error", "message": "Failed to retrieve documents."}), 500

@app.route('/api/documents', methods=['DELETE'])
@require_api_key
def delete_documents():
    """
    Delete documents by IDs with Pydantic validation & auth.
    """
    raw_data = request.get_json() or {}
    try:
        validated = DeleteDocumentsInput.model_validate(raw_data)
    except ValidationError as err:
        return jsonify({"status": "error", "message": "Validation failed", "errors": format_pydantic_errors(err)}), 422

    try:
        collection = get_collection(name=validated.collection_name)
        collection.delete(ids=validated.ids)
        return jsonify({
            "status": "success",
            "collection": collection.name,
            "deleted_ids": validated.ids
        }), 200
    except Exception as e:
        logger.error(f"Failed to delete documents: {e}")
        return jsonify({"status": "error", "message": "Failed to delete documents."}), 500

@app.route('/api/query', methods=['POST'])
@require_api_key
def query_documents():
    """
    Query documents using vector semantic similarity with Pydantic validation & auth.
    """
    raw_data = request.get_json() or {}
    try:
        validated = QueryInput.model_validate(raw_data)
    except ValidationError as err:
        return jsonify({"status": "error", "message": "Validation failed", "errors": format_pydantic_errors(err)}), 422

    query_texts = validated.query_texts or ([validated.query] if validated.query else [])

    try:
        collection = get_collection(name=validated.collection_name)
        results = collection.query(
            query_texts=query_texts,
            n_results=min(validated.n_results, collection.count() or 1),
            where=validated.where
        )

        formatted_results = []
        for i, q in enumerate(query_texts):
            query_res = []
            if results["ids"] and len(results["ids"]) > i:
                for doc_id, doc, meta, dist in zip(
                    results["ids"][i],
                    results["documents"][i] if results.get("documents") else [None] * len(results["ids"][i]),
                    results["metadatas"][i] if results.get("metadatas") else [None] * len(results["ids"][i]),
                    results["distances"][i] if results.get("distances") else [None] * len(results["ids"][i]),
                ):
                    query_res.append({
                        "id": doc_id,
                        "document": doc,
                        "metadata": meta,
                        "distance": dist
                    })
            formatted_results.append({
                "query": q,
                "matches": query_res
            })

        return jsonify({
            "status": "success",
            "collection": collection.name,
            "results": formatted_results
        }), 200
    except Exception as e:
        logger.error(f"Semantic query error: {e}")
        return jsonify({"status": "error", "message": "Failed to execute semantic query."}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=config.PORT, debug=config.DEBUG)
