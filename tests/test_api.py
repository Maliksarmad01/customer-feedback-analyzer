
import csv
import io
import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import main
from app.db.database import Base, get_db


@pytest.fixture
def client():
    test_engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    TestSessionLocal = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=test_engine,
    )

    Base.metadata.create_all(bind=test_engine)

    def override_get_db():
        db = TestSessionLocal()
        try:
            yield db
        finally:
            db.close()

    main.app.dependency_overrides[get_db] = override_get_db
    main.app.dependency_overrides[main.get_current_user] = lambda: None

    try:
        with TestClient(main.app) as test_client:
            yield test_client
    finally:
        main.app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=test_engine)
        test_engine.dispose()


def test_home_endpoint(client):
    response = client.get("/")

    assert response.status_code == 200
    assert response.json() == {
        "message": "Customer Feedback Analyzer is running!",
        "status": "success",
    }


def test_health_endpoint(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


def test_analyze_and_save_ticket(client):
    response = client.post(
        "/tickets/analyze",
        json={
            "message": (
                "The checkout page crashes every time. "
                "Please fix this urgently."
            )
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["accepted"] is True
    assert data["status"] == "analyzed"
    assert data["category"] == "Bug Report"
    assert data["priority"] == "Urgent"
    assert data["ticket_id"] is not None

    saved_response = client.get(
        f"/tickets/{data['ticket_id']}"
    )

    assert saved_response.status_code == 200
    assert saved_response.json()["message"] == (
        "The checkout page crashes every time. "
        "Please fix this urgently."
    )


def test_greeting_is_rejected(client):
    response = client.post(
        "/tickets/analyze",
        json={"message": "Hello!"},
    )

    assert response.status_code == 200

    data = response.json()

    assert data["accepted"] is False
    assert data["status"] == "rejected"
    assert data["reason"] == "Standalone greeting"
    assert data["ticket_id"] is None

    assert client.get("/tickets").json()["total"] == 0


def test_batch_processing(client):
    response = client.post(
        "/tickets/batch",
        json={
            "messages": [
                "The checkout page crashes when I pay.",
                "Hello!",
                "Buy now and get a huge discount!",
            ]
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["total_submitted"] == 3
    assert data["accepted_count"] == 1
    assert data["rejected_count"] == 2
    assert len(data["results"]) == 3

    assert client.get("/tickets").json()["total"] == 1


def test_list_tickets(client):
    client.post(
        "/tickets/analyze",
        json={"message": "I need a refund for my order."},
    )

    response = client.get("/tickets")

    assert response.status_code == 200

    data = response.json()

    assert data["total"] == 1
    assert len(data["tickets"]) == 1
    assert data["tickets"][0]["message"] == (
        "I need a refund for my order."
    )


def test_missing_ticket_returns_404(client):
    response = client.get("/tickets/9999")

    assert response.status_code == 404
    assert response.json()["detail"] == "Ticket 9999 not found"


def test_analytics(client):
    client.post(
        "/tickets/analyze",
        json={"message": "I need a refund for my order."},
    )

    response = client.get("/analytics")

    assert response.status_code == 200

    data = response.json()

    assert data["total_tickets"] == 1
    assert sum(data["by_category"].values()) == 1
    assert sum(data["by_priority"].values()) == 1
    assert sum(data["by_sentiment"].values()) == 1


def test_csv_export(client):
    client.post(
        "/tickets/analyze",
        json={
            "message": (
                "The checkout page crashes. "
                "Please fix it urgently."
            )
        },
    )

    response = client.get("/tickets/export/csv")

    assert response.status_code == 200
    assert "text/csv" in response.headers["content-type"]

    rows = list(csv.DictReader(io.StringIO(response.text)))

    assert len(rows) == 1
    assert rows[0]["message"] == (
        "The checkout page crashes. Please fix it urgently."
    )
    assert rows[0]["category"] == "Bug Report"


def test_json_export(client):
    client.post(
        "/tickets/analyze",
        json={"message": "I need a refund for my order."},
    )

    response = client.get("/tickets/export/json")

    assert response.status_code == 200
    assert "application/json" in response.headers["content-type"]

    data = json.loads(response.text)

    assert len(data) == 1
    assert data[0]["message"] == "I need a refund for my order."
    assert data[0]["category"] == "Billing Issue"


def test_empty_message_is_rejected_by_validation(client):
    response = client.post(
        "/tickets/analyze",
        json={"message": ""},
    )

    assert response.status_code == 422


def test_message_over_5000_characters_is_rejected(client):
    response = client.post(
        "/tickets/analyze",
        json={"message": "a" * 5001},
    )

    assert response.status_code == 422


def test_batch_with_more_than_100_messages_is_rejected(client):
    response = client.post(
        "/tickets/batch",
        json={
            "messages": ["Please help with my issue."] * 101
        },
    )

    assert response.status_code == 422


def test_empty_batch_is_rejected(client):
    response = client.post(
        "/tickets/batch",
        json={"messages": []},
    )

    assert response.status_code == 422


def test_signup_login_and_me(client):
    # Remove the test-only authentication override for the auth flow itself.
    main.app.dependency_overrides.pop(main.get_current_user, None)
    signup = client.post('/auth/signup', json={
        'name': 'Test User', 'email': 'test@example.com', 'password': 'StrongPass123'
    })
    assert signup.status_code == 201
    session = signup.json()
    assert session['access_token']
    assert session['user']['email'] == 'test@example.com'
    assert 'password' not in session['user']

    me = client.get('/auth/me', headers={'Authorization': f"Bearer {session['access_token']}"})
    assert me.status_code == 200
    assert me.json()['name'] == 'Test User'

    login = client.post('/auth/login', json={'email': 'TEST@example.com', 'password': 'StrongPass123'})
    assert login.status_code == 200
    assert login.json()['user']['id'] == session['user']['id']

    wrong_password = client.post('/auth/login', json={'email': 'test@example.com', 'password': 'wrong-password'})
    assert wrong_password.status_code == 401


def test_ticket_api_requires_authentication(client):
    main.app.dependency_overrides.pop(main.get_current_user, None)
    response = client.get('/tickets')
    assert response.status_code == 401


def test_csv_import_endpoint(client):
    response = client.post(
        "/tickets/import/csv",
        files={"file": ("feedback.csv", "message\nHello, hope you are having a nice day!\nThe checkout page crashes ASAP!\n", "text/csv")},
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["total_submitted"] == 2
    assert data["accepted_count"] == 1
    assert data["rejected_count"] == 1
    accepted = next(row for row in data["results"] if row["accepted"])
    assert accepted["category"] == "Bug Report"


def test_csv_import_rejects_non_csv(client):
    response = client.post(
        "/tickets/import/csv",
        files={"file": ("feedback.txt", "message\nHello\n", "text/plain")},
    )
    assert response.status_code == 400


def test_json_file_import_accepts_message_objects(client):
    response = client.post(
        "/tickets/import/json",
        files={
            "file": (
                "feedback.json",
                json.dumps({"messages": [
                    {"message": "The payment page crashes on checkout. Please fix ASAP!"},
                    {"message": "Hello!"},
                ]}),
                "application/json",
            )
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["total_submitted"] == 2
    assert data["accepted_count"] == 1
    assert data["rejected_count"] == 1
    assert client.get("/tickets").json()["total"] == 1


def test_json_file_import_rejects_invalid_json(client):
    response = client.post(
        "/tickets/import/json",
        files={"file": ("feedback.json", "{not valid json", "application/json")},
    )
    assert response.status_code == 400
    assert "valid UTF-8 JSON" in response.json()["detail"]
