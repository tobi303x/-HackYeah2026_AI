import os
import json
import time
import requests

BASE_URL = "http://localhost:5000"
AUTH_KEY = os.getenv("API_AUTH_KEY", "hackyeah2026_secret_key")

def test_api():
    print(f"=== 1. Testing Health Endpoint ({BASE_URL}/health) [Public] ===")
    res = requests.get(f"{BASE_URL}/health")
    print(f"Status: {res.status_code}, Response: {res.json()}")
    assert res.status_code == 200

    print(f"\n=== 2. Testing Authentication Rejection without API Key ===")
    res = requests.post(f"{BASE_URL}/api/collections", json={"name": "unauthorized_col"})
    print(f"Expected 401: Status={res.status_code}, Body={res.json()}")
    assert res.status_code == 401
    assert "Unauthorized" in res.json().get("message", "")

    print(f"\n=== 3. Testing Authentication Rejection with Invalid Key ===")
    res = requests.post(f"{BASE_URL}/api/collections", json={"name": "unauthorized_col", "api_key": "wrong_key"})
    print(f"Expected 401: Status={res.status_code}, Body={res.json()}")
    assert res.status_code == 401

    test_col = "hackyeah_test_collection"

    print(f"\n=== 4. Testing Create New Collection with Valid api_key in Payload ===")
    # Clean up if existing
    requests.delete(f"{BASE_URL}/api/collections/{test_col}", json={"api_key": AUTH_KEY})
    res = requests.post(f"{BASE_URL}/api/collections", json={
        "name": test_col,
        "metadata": {"topic": "ai_hackathon_2026"},
        "api_key": AUTH_KEY
    })
    print(f"Status: {res.status_code}, Response: {res.json()}")
    assert res.status_code == 201

    print(f"\n=== 5. Testing List Collections (GET with api_key param) ===")
    res = requests.get(f"{BASE_URL}/api/collections?api_key={AUTH_KEY}")
    print(f"Status: {res.status_code}, Collections: {res.json()}")
    assert res.status_code == 200
    col_names = [c["name"] for c in res.json().get("collections", [])]
    assert test_col in col_names

    print(f"\n=== 6. Testing Document Ingestion with api_key in Payload ===")
    sample_docs = {
        "api_key": AUTH_KEY,
        "documents": [
            "HackYeah 2026 is Europe's largest offline hackathon in Krakow.",
            "ChromaDB stores high-dimensional embeddings for fast retrieval.",
            "Flask is a micro web framework written in Python."
        ],
        "metadatas": [
            {"category": "event", "city": "Krakow"},
            {"category": "database", "type": "vector"},
            {"category": "framework", "language": "python"}
        ],
        "ids": ["doc-1", "doc-2", "doc-3"],
        "collection_name": test_col
    }
    res = requests.post(f"{BASE_URL}/api/documents", json=sample_docs)
    print(f"Status: {res.status_code}, Response: {res.json()}")
    assert res.status_code == 201

    print(f"\n=== 7. Testing Edit / Update Existing Record with api_key in Payload ===")
    update_payload = {
        "api_key": AUTH_KEY,
        "ids": ["doc-1"],
        "documents": ["HackYeah 2026 is Europe's largest offline hackathon at Tauron Arena in Krakow."],
        "metadatas": [{"category": "event", "city": "Krakow", "updated": True}],
        "collection_name": test_col
    }
    res = requests.put(f"{BASE_URL}/api/documents", json=update_payload)
    print(f"Status: {res.status_code}, Response: {res.json()}")
    assert res.status_code == 200

    print(f"\n=== 8. Testing Vector Similarity Query with api_key in Payload ===")
    query_payload = {
        "api_key": AUTH_KEY,
        "query": "Where is the big offline coding event happening?",
        "n_results": 2,
        "collection_name": test_col
    }
    res = requests.post(f"{BASE_URL}/api/query", json=query_payload)
    print(f"Status: {res.status_code}")
    print(json.dumps(res.json(), indent=2))
    assert res.status_code == 200

    print(f"\n=== 9. Testing Delete Collection with api_key in Payload ===")
    res = requests.delete(f"{BASE_URL}/api/collections/{test_col}", json={"api_key": AUTH_KEY})
    print(f"Status: {res.status_code}, Response: {res.json()}")
    assert res.status_code == 200

    print("\n[SUCCESS] ALL AUTHENTICATION CHECKS & API OPERATIONS VERIFIED!")

if __name__ == "__main__":
    test_api()
