import os
import uuid
import logging
from flask import Flask, request, jsonify, send_from_directory, Response, stream_with_context
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
    QueryInput,
    ReportQueryInput,
    UnifiedRAGQueryInput,
    AgentEvaluateInput
)
from agent_service import generate_agent_stream, evaluate_idea_synchronous

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
            "query": "POST /api/query",
            "query_reports": "POST /api/reports/query",
            "rag_search": "POST /api/rag/search",
            "agent_stream": "POST /api/agent/stream",
            "agent_evaluate": "POST /api/agent/evaluate",
            "agent_ui": "GET /agent-ui"
        }
    })

@app.route('/agent-ui', methods=['GET'])
@app.route('/demo', methods=['GET'])
def agent_ui():
    """Interactive ROPS Grant & Innovation Advisor Web UI Demonstrator."""
    base_dir = os.path.dirname(os.path.abspath(__file__))
    return send_from_directory(os.path.join(base_dir, 'static'), 'index.html', mimetype='text/html')

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
        total_count = collection.count() or 1

        # When max_distance is specified, fetch up to 3x candidates (capped at total_count)
        # so filtering by distance threshold doesn't starve the requested n_results.
        fetch_k = min(validated.n_results * 3, total_count) if validated.max_distance is not None else min(validated.n_results, total_count)

        results = collection.query(
            query_texts=query_texts,
            n_results=fetch_k,
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
                    # Filter out matches exceeding the maximum distance cutoff
                    if validated.max_distance is not None and dist is not None:
                        if dist > validated.max_distance:
                            continue

                    query_res.append({
                        "id": doc_id,
                        "document": doc,
                        "metadata": meta,
                        "distance": dist
                    })

                    # Stop once we have reached requested n_results
                    if len(query_res) >= validated.n_results:
                        break

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

@app.route('/api/reports/query', methods=['POST'])
@require_api_key
def query_reports():
    """
    Semantic search across ROPS policy & diagnostic reports.
    Supports filtering by year range, category, and statistics flag.
    """
    raw_data = request.get_json() or {}
    try:
        validated = ReportQueryInput.model_validate(raw_data)
    except ValidationError as err:
        return jsonify({"status": "error", "message": "Validation failed", "errors": format_pydantic_errors(err)}), 422

    try:
        collection = get_collection(name=validated.collection_name)
        total_count = collection.count() or 1

        # Build Chroma 'where' filter from structured fields
        where_conditions = []
        if validated.where:
            where_conditions.append(validated.where)
        if validated.year_from is not None:
            where_conditions.append({"year": {"$gte": validated.year_from}})
        if validated.year_to is not None:
            where_conditions.append({"year": {"$lte": validated.year_to}})
        if validated.category is not None:
            where_conditions.append({"category": {"$eq": validated.category}})
        if validated.only_statistics is True:
            where_conditions.append({"has_statistics": {"$eq": True}})

        if len(where_conditions) == 1:
            where_filter = where_conditions[0]
        elif len(where_conditions) > 1:
            where_filter = {"$and": where_conditions}
        else:
            where_filter = None

        fetch_k = min(validated.n_results * 3, total_count) if validated.max_distance is not None else min(validated.n_results, total_count)

        results = collection.query(
            query_texts=[validated.query],
            n_results=fetch_k,
            where=where_filter
        )

        matches = []
        if results["ids"] and len(results["ids"]) > 0:
            for doc_id, doc, meta, dist in zip(
                results["ids"][0],
                results["documents"][0] if results.get("documents") else [None] * len(results["ids"][0]),
                results["metadatas"][0] if results.get("metadatas") else [None] * len(results["ids"][0]),
                results["distances"][0] if results.get("distances") else [None] * len(results["ids"][0]),
            ):
                if validated.max_distance is not None and dist is not None:
                    if dist > validated.max_distance:
                        continue

                matches.append({
                    "id": doc_id,
                    "document": doc,
                    "metadata": meta,
                    "distance": dist
                })
                if len(matches) >= validated.n_results:
                    break

        return jsonify({
            "status": "success",
            "collection": collection.name,
            "query": validated.query,
            "total_matches": len(matches),
            "matches": matches
        }), 200
    except Exception as e:
        logger.error(f"Reports query error: {e}")
        return jsonify({"status": "error", "message": "Failed to query reports collection."}), 500

@app.route('/api/rag/search', methods=['POST'])
@require_api_key
def unified_rag_search():
    """
    Unified Dual-Retrieval RAG endpoint.
    Retrieves diagnostic evidence from 'rops_reports' and actionable solutions from 'rops_innovations',
    and synthesizes a suggested evaluation framework structured along the ROPS canonical evaluation triad.
    """
    raw_data = request.get_json() or {}
    try:
        validated = UnifiedRAGQueryInput.model_validate(raw_data)
    except ValidationError as err:
        return jsonify({"status": "error", "message": "Validation failed", "errors": format_pydantic_errors(err)}), 422

    try:
        # 1. Query policy reports (rops_reports)
        policy_evidence = []
        if validated.n_reports > 0:
            try:
                rep_col = get_collection(name="rops_reports")
                rep_total = rep_col.count()
                if rep_total > 0:
                    rep_fetch_k = min(validated.n_reports * 3, rep_total)

                    rep_where = []
                    if validated.year_from:
                        rep_where.append({"year": {"$gte": validated.year_from}})
                    if validated.category:
                        rep_where.append({"category": {"$eq": validated.category}})

                    where_filter = None
                    if len(rep_where) == 1:
                        where_filter = rep_where[0]
                    elif len(rep_where) > 1:
                        where_filter = {"$and": rep_where}

                    rep_res = rep_col.query(
                        query_texts=[validated.query],
                        n_results=rep_fetch_k,
                        where=where_filter
                    )
                    if rep_res["ids"] and len(rep_res["ids"]) > 0:
                        for doc_id, doc, meta, dist in zip(
                            rep_res["ids"][0],
                            rep_res["documents"][0] if rep_res.get("documents") else [None] * len(rep_res["ids"][0]),
                            rep_res["metadatas"][0] if rep_res.get("metadatas") else [None] * len(rep_res["ids"][0]),
                            rep_res["distances"][0] if rep_res.get("distances") else [None] * len(rep_res["ids"][0]),
                        ):
                            if validated.max_distance is not None and dist is not None and dist > validated.max_distance:
                                continue
                            policy_evidence.append({
                                "id": doc_id,
                                "document": doc,
                                "metadata": meta,
                                "distance": dist
                            })
                            if len(policy_evidence) >= validated.n_reports:
                                break
            except Exception as e_rep:
                logger.warning(f"Note: rops_reports query error or collection uninitialized: {e_rep}")

        # 2. Query social innovations (rops_innovations)
        social_innovations = []
        if validated.n_innovations > 0:
            try:
                inn_col = get_collection(name="rops_innovations")
                inn_total = inn_col.count()
                if inn_total > 0:
                    inn_fetch_k = min(validated.n_innovations * 3, inn_total)

                    inn_where = None
                    if validated.category:
                        inn_where = {"category_slug": {"$eq": validated.category}}

                    inn_res = inn_col.query(
                        query_texts=[validated.query],
                        n_results=inn_fetch_k,
                        where=inn_where
                    )
                    if inn_res["ids"] and len(inn_res["ids"]) > 0:
                        for doc_id, doc, meta, dist in zip(
                            inn_res["ids"][0],
                            inn_res["documents"][0] if inn_res.get("documents") else [None] * len(inn_res["ids"][0]),
                            inn_res["metadatas"][0] if inn_res.get("metadatas") else [None] * len(inn_res["ids"][0]),
                            inn_res["distances"][0] if inn_res.get("distances") else [None] * len(inn_res["ids"][0]),
                        ):
                            if validated.max_distance is not None and dist is not None and dist > validated.max_distance:
                                continue
                            social_innovations.append({
                                "id": doc_id,
                                "document": doc,
                                "metadata": meta,
                                "distance": dist
                            })
                            if len(social_innovations) >= validated.n_innovations:
                                break
            except Exception as e_inn:
                logger.warning(f"rops_innovations query error: {e_inn}")

        # 3. Canonical ROPS Evaluation Triad Guidance
        suggested_evaluation = {
            "substantive_actions": (
                "Działania merytoryczne: Zdefiniuj bezpośrednie wsparcie dla beneficjentów końcowych opierając się na "
                "wybranych innowacjach społecznych. Uwzględnij kryteria trafności (rozwiązywanie zdiagnozowanych w raportach deficytów) "
                "oraz mierzalności rezultatów miękkich (poczucie bezpieczeństwa, sprawczość, integracja społeczna)."
            ),
            "promotion_and_outreach": (
                "Promocja projektu: Zaplanuj rekrutację z poszanowaniem godności uczestników, unikając stygmatyzacji. "
                "Wdróż standardy dostępności WCAG 2.1 i ETR (tekst łatwy do czytania). Przeprowadź działania uświadamiające otoczenie i pracodawców."
            ),
            "project_governance": (
                "Zarządzanie projektem: Zbuduj partnerstwo międzysektorowe (JST/OPS/CUS + PUP + NGO/PES). "
                "Wdróż ewaluację bieżącą (on-going) i zabezpiecz trwałość instytucjonalną poprzez wpisanie wypracowanego modelu do lokalnej Strategii (SRPS)."
            )
        }

        return jsonify({
            "status": "success",
            "query": validated.query,
            "counts": {
                "policy_evidence": len(policy_evidence),
                "social_innovations": len(social_innovations)
            },
            "policy_evidence": policy_evidence,
            "social_innovations": social_innovations,
            "evaluation_framework": suggested_evaluation
        }), 200
    except Exception as e:
        logger.error(f"Unified RAG search error: {e}")
        return jsonify({"status": "error", "message": "Failed to execute unified RAG search."}), 500

@app.route('/api/agent/stream', methods=['GET', 'POST'])
@require_api_key
def agent_stream_evaluation():
    """
    Real-time Server-Sent Events (SSE) streaming endpoint for autonomous ROPS Grant Advisory.
    Streams structured thinking steps, evidence retrieval from rops_reports & rops_innovations & grants,
    scoring benchmarking, and streaming Markdown grant proposal dossier.
    """
    if request.method == 'GET':
        raw_data = request.args.to_dict()
    else:
        raw_data = request.get_json() or {}

    try:
        validated = AgentEvaluateInput.model_validate(raw_data)
    except ValidationError as err:
        return jsonify({"status": "error", "message": "Validation failed", "errors": format_pydantic_errors(err)}), 422

    response = Response(
        stream_with_context(generate_agent_stream(validated)),
        mimetype='text/event-stream'
    )
    response.headers['Cache-Control'] = 'no-cache, no-transform'
    response.headers['X-Accel-Buffering'] = 'no'
    response.headers['Connection'] = 'keep-alive'
    return response

@app.route('/api/agent/evaluate', methods=['POST'])
@require_api_key
def agent_evaluate_synchronous():
    """
    Synchronous REST endpoint for ROPS Social Innovation & Grant Advisory.
    Executes full multi-step reasoning and returns structured evaluation report,
    retrieved citations, scorecard compliance, and complete Markdown dossier as JSON.
    """
    raw_data = request.get_json() or {}
    try:
        validated = AgentEvaluateInput.model_validate(raw_data)
    except ValidationError as err:
        return jsonify({"status": "error", "message": "Validation failed", "errors": format_pydantic_errors(err)}), 422

    try:
        result = evaluate_idea_synchronous(validated)
        return jsonify({
            "status": "success",
            "data": result
        }), 200
    except Exception as e:
        logger.error(f"Agent evaluation error: {e}", exc_info=True)
        return jsonify({"status": "error", "message": f"Agent evaluation failed: {str(e)}"}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=config.PORT, debug=config.DEBUG)


