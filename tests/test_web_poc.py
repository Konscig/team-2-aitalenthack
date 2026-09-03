import sys
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import app, reset_demo_state


def client() -> TestClient:
    reset_demo_state()
    return TestClient(app)


def test_service_shell_and_corridors() -> None:
    response = client().get("/")
    assert response.status_code == 200
    assert "Переводы за рубеж" in response.text
    assert client().get("/api/health").json()["mode"] == "demo"
    codes = {item["code"] for item in client().get("/api/corridors").json()}
    assert codes == {"TJS", "UZS", "KGS", "AMD", "KZT"}


def test_signal_and_push_fixtures_are_safe_and_traceable() -> None:
    for status in ("current", "changed", "unknown"):
        item = client().get(f"/api/signals/TJS?status={status}").json()
        assert item["freshness_status"] == status
        assert item["source_snapshot_ref"]
        assert item["available_at_t"]
        assert "демо" in item["disclaimer"].lower()
    changed = client().get("/api/signals/TJS?status=changed").json()
    assert "выгод" not in changed["message"].lower()
    push = client().get("/api/pushes?corridor=TJS&status=current").json()[0]
    assert push["deep_link"] == "/?corridor=TJS&status=current&model_scenario=withhold"
    assert client().get("/api/signals/XXX").status_code == 404


def test_triggered_push_appears_in_process_local_inbox() -> None:
    api = client()
    triggered = api.post("/api/pushes", json={"corridor": "TJS", "status": "changed", "model_scenario": "favorable_now", "body": "Свой тестовый текст"})
    assert triggered.status_code == 200
    push = triggered.json()["push"]
    assert push["deep_link"] == "/?corridor=TJS&status=changed&model_scenario=favorable_now"
    assert push["body"] == "Свой тестовый текст"
    assert push["model_label"]
    assert api.get("/api/pushes/inbox").json() == [push]


def test_preferences_and_openapi_are_process_local() -> None:
    api = client()
    assert api.get("/docs").status_code == 200
    schema = api.get("/openapi.json").json()
    assert "/api/transfers" in schema["paths"]
    updated = api.put("/api/preferences", json={
        "enabled": True, "corridors": ["TJS", "UZS"], "quiet_hours": "22:00–08:00"
    })
    assert updated.status_code == 200
    assert updated.json()["corridors"] == ["TJS", "UZS"]
    invalid = api.put("/api/preferences", json={
        "enabled": True, "corridors": ["XXX"], "quiet_hours": "22:00–08:00"
    })
    assert invalid.status_code == 422
    reset_demo_state()
    assert client().get("/api/preferences").json()["corridors"] == ["TJS", "UZS", "KGS", "AMD", "KZT"]


def test_simulated_transfer_validates_method_limits() -> None:
    api = client()
    base = {"corridor": "TJS", "recipient": "Тестовый получатель", "debit_account": "Демо-счёт"}
    phone = api.post("/api/transfers", json={**base, "method": "phone", "amount_rub": 1_000_000})
    assert phone.status_code == 200
    assert phone.json()["status"] == "simulated"
    assert "не списывались" in phone.json()["message"]
    card_over_limit = api.post("/api/transfers", json={**base, "method": "card", "amount_rub": 500_001})
    assert card_over_limit.status_code == 422
    invalid_amount = api.post("/api/transfers", json={**base, "method": "phone", "amount_rub": 0})
    assert invalid_amount.status_code == 422


def test_demo_quote_and_transfer_result_include_recipient_amount() -> None:
    api = client()
    quote = api.get("/api/quotes/TJS?amount_rub=1200")
    assert quote.status_code == 200
    assert quote.json()["recipient_amount"] == 126.0
    assert quote.json()["rate_label"] == "Демо-ориентир, не курс исполнения"
    transfer = api.post("/api/transfers", json={
        "corridor": "TJS", "method": "phone", "recipient": "+79999999999",
        "amount_rub": 1200, "debit_account": "Демо-счёт •• 1234",
    })
    assert transfer.status_code == 200
    assert transfer.json()["quote"]["recipient_amount"] == 126.0


def test_model_scenarios_keep_a_bad_label_hidden_and_expose_future_window() -> None:
    api = client()
    hidden = api.get("/api/signals/TJS?model_scenario=withhold").json()["model_assessment"]
    assert hidden["client_label"] is None
    later = api.get("/api/signals/TJS?model_scenario=better_later").json()["model_assessment"]
    assert later["forecast_date"] == "2026-09-04"
