"""Automated tests for FastAPI endpoints and Voice Platform Webhooks."""

from fastapi.testclient import TestClient
from app.main import app
from app.config import settings


client = TestClient(app)


def test_health_check_endpoint():
    """Verify health check probe returns expected configuration details."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "Home Credit LAP Voice Agent"
    assert data["max_loan_cap"] == settings.max_loan_amount
    assert str(settings.min_tenure_years) in data["tenure_bounds"]


def test_simulate_turn_endpoint():
    """Verify REST API simulate-turn handles state transitions properly."""
    # First turn: customer confirms identity
    response = client.post(
        "/api/simulate-turn",
        json={"utterance": "Yes, this is Rahul Sharma speaking.", "state": None},
    )
    assert response.status_code == 200
    data = response.json()
    assert "agent_response" in data
    assert data["current_stage"] == "availability_check"
    assert data["is_terminal"] is False


def test_retell_webhook_endpoint():
    """Verify Retell AI webhook event handling."""
    payload = {
        "event": "call_started",
        "call": {
            "call_id": "test_call_9876",
            "agent_id": "agent_hc_01",
        },
    }
    response = client.post("/webhook/retell", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["event"] == "call_started"
    assert data["call_id"] == "test_call_9876"
    assert data["status"] == "processed"


def test_bolna_webhook_endpoint():
    """Verify Bolna webhook event handling."""
    payload = {
        "event": "conversation_end",
        "session_id": "bolna_sess_4321",
        "status": "completed",
    }
    response = client.post("/webhook/bolna", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
