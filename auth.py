import secrets
from functools import wraps
from flask import request, jsonify
from config import config

def require_api_key(f):
    """
    Decorator to protect endpoints by requiring a valid API key.
    Uses secrets.compare_digest for constant-time comparison (prevents timing attacks).
    Checks:
      1. JSON payload: {"api_key": "..."} (Primary)
      2. Query parameter: ?api_key=... (For GET requests)
      3. Header: X-API-Key or Authorization: Bearer <key> (Fallback)
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        expected_key = config.API_AUTH_KEY
        if not expected_key:
            # If API_AUTH_KEY is not configured, allow access
            return f(*args, **kwargs)

        provided_key = None

        # 1. Primary: check JSON payload
        if request.is_json:
            try:
                json_data = request.get_json(silent=True)
                if isinstance(json_data, dict):
                    provided_key = json_data.get("api_key")
            except Exception:
                pass

        # 2. Check query parameter (useful for GET endpoints)
        if not provided_key:
            provided_key = request.args.get("api_key")

        # 3. Check headers (X-API-Key or Authorization Bearer)
        if not provided_key:
            provided_key = request.headers.get("X-API-Key")
            if not provided_key:
                auth_header = request.headers.get("Authorization", "")
                if auth_header.startswith("Bearer "):
                    provided_key = auth_header[7:].strip()

        # Constant-time comparison to prevent timing attacks
        if not provided_key or not isinstance(provided_key, str) or not secrets.compare_digest(provided_key, expected_key):
            return jsonify({
                "status": "error",
                "message": "Unauthorized. A valid 'api_key' is required in the JSON payload, query parameters, or 'X-API-Key' header."
            }), 401

        return f(*args, **kwargs)
    return decorated_function
