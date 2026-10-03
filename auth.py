import secrets
from functools import wraps
from flask import request, jsonify
from config import config

def _extract_keys():
    """Extracts provided api_key and admin_api_key from json, query, or headers."""
    api_key = None
    admin_key = None

    # 1. JSON payload
    if request.is_json:
        try:
            json_data = request.get_json(silent=True)
            if isinstance(json_data, dict):
                api_key = json_data.get("api_key")
                admin_key = json_data.get("admin_api_key")
        except Exception:
            pass

    # 2. Query parameters
    if not api_key:
        api_key = request.args.get("api_key")
    if not admin_key:
        admin_key = request.args.get("admin_api_key")

    # 3. Headers
    if not api_key:
        api_key = request.headers.get("X-API-Key")
    if not admin_key:
        admin_key = request.headers.get("X-Admin-API-Key")

    if not api_key and not admin_key:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            bearer = auth_header[7:].strip()
            api_key = bearer
            admin_key = bearer

    return api_key, admin_key


def require_api_key(f):
    """
    Decorator to protect standard endpoints (querying, document operations, reading).
    Accepts either standard API_AUTH_KEY or master ADMIN_API_KEY.
    Uses secrets.compare_digest for constant-time comparison (prevents timing attacks).
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        expected_standard = config.API_AUTH_KEY
        expected_admin = config.ADMIN_API_KEY

        # If neither key is configured, allow open access
        if not expected_standard and not expected_admin:
            return f(*args, **kwargs)

        api_key, admin_key = _extract_keys()
        candidates = [k for k in (admin_key, api_key) if k and isinstance(k, str)]

        if not candidates:
            return jsonify({
                "status": "error",
                "message": "Unauthorized. A valid 'api_key' is required in JSON payload, query parameters, or 'X-API-Key' header."
            }), 401

        # Check against standard key or master admin key
        authorized = False
        for key in candidates:
            if expected_standard and secrets.compare_digest(key, expected_standard):
                authorized = True
                break
            if expected_admin and secrets.compare_digest(key, expected_admin):
                authorized = True
                break

        if not authorized:
            return jsonify({
                "status": "error",
                "message": "Unauthorized. Invalid API key."
            }), 401

        return f(*args, **kwargs)
    return decorated_function


def require_admin_key(f):
    """
    Decorator to protect sensitive collection operations (creating or deleting collections).
    Requires a valid ADMIN_API_KEY.
    If ADMIN_API_KEY is not configured, falls back to API_AUTH_KEY.
    If caller provides a valid standard API_AUTH_KEY but not the ADMIN_API_KEY, returns 403 Forbidden.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        expected_admin = config.ADMIN_API_KEY or config.API_AUTH_KEY

        if not expected_admin:
            return f(*args, **kwargs)

        api_key, admin_key = _extract_keys()
        candidates = [k for k in (admin_key, api_key) if k and isinstance(k, str)]

        if not candidates:
            return jsonify({
                "status": "error",
                "message": "Unauthorized. An administrative API key is required ('admin_api_key', 'X-Admin-API-Key', or 'api_key')."
            }), 401

        # Check if caller matches expected admin key
        is_admin = False
        for key in candidates:
            if secrets.compare_digest(key, expected_admin):
                is_admin = True
                break

        if not is_admin:
            # Check if caller passed a valid regular API key to return an explicit 403 Forbidden
            has_standard = False
            if config.API_AUTH_KEY:
                for key in candidates:
                    if secrets.compare_digest(key, config.API_AUTH_KEY):
                        has_standard = True
                        break

            if has_standard:
                return jsonify({
                    "status": "error",
                    "message": "Forbidden. Standard API key does not have permission to create or delete collections. An 'admin_api_key' is required."
                }), 403

            return jsonify({
                "status": "error",
                "message": "Unauthorized. Invalid administrative API key."
            }), 401

        return f(*args, **kwargs)
    return decorated_function

