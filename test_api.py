import os
import json
import time
import requests

BASE_URL = "http://localhost:5000"
AUTH_KEY = os.getenv("API_AUTH_KEY", "hackyeah2026_secret_key")
ADMIN_KEY = os.getenv("ADMIN_API_KEY", "hackyeah2026_admin_secret_key")

def test_api():
    print(f"=== 1. Testing Health Endpoint ({BASE_URL}/health) [Public] ===")
    res = requests.get(f"{BASE_URL}/health")
    print(f"Status: {res.status_code}, Response: {res.json()}")
    assert res.status_code == 200
    health_info = res.json()
    admin_auth_enabled = health_info.get("admin_auth_enabled", False)

    test_col = "hackyeah_test_collection"

    if admin_auth_enabled:
        print(f"\n=== 4. Testing Create Collection Gating: Standard Key Rejected (403 Forbidden) ===")
        res = requests.post(f"{BASE_URL}/api/collections", json={
            "name": test_col,
            "metadata": {"topic": "ai_hackathon_2026"},
            "api_key": AUTH_KEY
        })
        print(f"Expected 403: Status={res.status_code}, Body={res.json()}")
        assert res.status_code == 403
        assert "Forbidden" in res.json().get("message", "")
    else:
        print(f"\n=== 4. (Single-key mode) ADMIN_API_KEY not set; fallback allows standard key ===")

    print(f"\n=== 5. Testing Create Collection with ADMIN_KEY (201 Created) ===")
    active_admin_key = ADMIN_KEY if admin_auth_enabled else AUTH_KEY
    requests.delete(f"{BASE_URL}/api/collections/{test_col}", json={"admin_api_key": active_admin_key})
    res = requests.post(f"{BASE_URL}/api/collections", json={
        "name": test_col,
        "metadata": {"topic": "ai_hackathon_2026"},
        "admin_api_key": active_admin_key
    })
    print(f"Status: {res.status_code}, Response: {res.json()}")
    assert res.status_code == 201

    print(f"\n=== 6. Testing List Collections (GET with standard api_key) ===")
    res = requests.get(f"{BASE_URL}/api/collections?api_key={AUTH_KEY}")
    print(f"Status: {res.status_code}, Collections: {res.json()}")
    assert res.status_code == 200
    col_names = [c["name"] for c in res.json().get("collections", [])]
    assert test_col in col_names

    print(f"\n=== 7. Testing Document Ingestion with standard api_key ===")
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

    print(f"\n=== 8. Testing Edit / Update Existing Record with standard api_key ===")
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

    print(f"\n=== 9. Testing Vector Similarity Query with standard api_key ===")
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

    print(f"\n=== 9b. Testing Vector Similarity Query with max_distance Cutoff ===")
    query_cutoff_payload = {
        "api_key": AUTH_KEY,
        "query": "Where is the big offline coding event happening?",
        "n_results": 5,
        "collection_name": test_col,
        "max_distance": 0.5
    }
    res = requests.post(f"{BASE_URL}/api/query", json=query_cutoff_payload)
    assert res.status_code == 200
    for match in res.json()["results"][0]["matches"]:
        assert match["distance"] <= 0.5
    print("max_distance cutoff filter: PASSED")

    if admin_auth_enabled:
        print(f"\n=== 10. Testing Delete Collection Gating: Standard Key Rejected (403 Forbidden) ===")
        res = requests.delete(f"{BASE_URL}/api/collections/{test_col}", json={"api_key": AUTH_KEY})
        print(f"Expected 403: Status={res.status_code}, Body={res.json()}")
        assert res.status_code == 403

    print(f"\n=== 11. Testing Delete Collection with ADMIN_KEY (200 OK) ===")
    res = requests.delete(f"{BASE_URL}/api/collections/{test_col}", json={"admin_api_key": active_admin_key})
    print(f"Status: {res.status_code}, Response: {res.json()}")
    assert res.status_code == 200

    print(f"\n=== 12. Testing Policy Reports Query Endpoint (/api/reports/query) ===")
    rep_payload = {
        "api_key": AUTH_KEY,
        "query": "wyzwania i potrzeby opieki senioralnej",
        "n_results": 3,
        "collection_name": "rops_innovations"  # test with available collection
    }
    res = requests.post(f"{BASE_URL}/api/reports/query", json=rep_payload)
    print(f"Status: {res.status_code}, Response keys: {list(res.json().keys())}")
    assert res.status_code == 200
    assert "matches" in res.json()

    print(f"\n=== 13. Testing Unified RAG Dual-Retrieval Endpoint (/api/rag/search) ===")
    rag_payload = {
        "api_key": AUTH_KEY,
        "query": "pomoc dla osób starszych w miejscu zamieszkania",
        "n_reports": 2,
        "n_innovations": 2
    }
    res = requests.post(f"{BASE_URL}/api/rag/search", json=rag_payload)
    print(f"Status: {res.status_code}, Counts: {res.json().get('counts')}")
    assert res.status_code == 200
    assert "policy_evidence" in res.json()
    assert "social_innovations" in res.json()
    assert "evaluation_framework" in res.json()
    print("[OK] Unified RAG Search: PASSED")

    print(f"\n=== 14. Testing Synchronous ROPS Grant Advisor Endpoint (/api/agent/evaluate) ===")
    agent_payload = {
        "api_key": AUTH_KEY,
        "query": "Mobilne modułowe zaplecze higieniczne dla osób bezdomnych poza schroniskami",
        "powiat": "olkuski",
        "applicant_type": "NGO",
        "n_reports": 2,
        "n_innovations": 2,
        "n_grants": 2
    }
    res = requests.post(f"{BASE_URL}/api/agent/evaluate", json=agent_payload, timeout=60)
    print(f"Status: {res.status_code}")
    assert res.status_code == 200
    res_data = res.json().get("data", {})
    assert "active_grant" in res_data
    assert "final_report_markdown" in res_data
    assert len(res_data["final_report_markdown"]) > 100
    print(f"Active Grant identified: {res_data['active_grant'].get('title')}")
    print(f"Markdown dossier length: {len(res_data['final_report_markdown'])} chars")
    print("[OK] Synchronous Agent Evaluation: PASSED")

    print(f"\n=== 15. Testing Real-time SSE Agent Streaming Endpoint (/api/agent/stream) ===")
    stream_payload = {
        "api_key": AUTH_KEY,
        "query": "Wsparcie wytchnieniowe dla opiekunów osób starszych w Małopolsce",
        "n_reports": 2,
        "n_innovations": 2,
        "n_grants": 2
    }
    res_stream = requests.post(f"{BASE_URL}/api/agent/stream", json=stream_payload, stream=True, timeout=60)
    print(f"Status: {res_stream.status_code}, Content-Type: {res_stream.headers.get('Content-Type')}")
    assert res_stream.status_code == 200
    assert "text/event-stream" in res_stream.headers.get("Content-Type", "")

    events_received = []
    for line in res_stream.iter_lines(decode_unicode=True):
        if line and line.startswith("event:"):
            event_name = line.split(":", 1)[1].strip()
            events_received.append(event_name)

    print(f"Events captured: {events_received}")
    assert "agent_start" in events_received
    assert "step_start" in events_received
    assert "agent_complete" in events_received
    print("[OK] Real-time SSE Agent Streaming: PASSED")

    print("\n[SUCCESS] ALL STANDARD, ADMIN, RAG DUAL-RETRIEVAL, AND AGENT SSE CHECKS VERIFIED!")

if __name__ == "__main__":
    test_api()

