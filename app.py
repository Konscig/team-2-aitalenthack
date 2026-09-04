"""Autonomous web PoC for the cross-border transfer client journey."""

from enum import Enum
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator, model_validator


class GateScenario(str, Enum):
    strong = "strong"
    expired = "expired"
    silent = "silent"


class TransferMethod(str, Enum):
    phone = "phone"
    card = "card"


CORRIDORS = {
    "TJS": {"country": "Таджикистан", "currency": "TJS", "flag": "🇹🇯"},
    "UZS": {"country": "Узбекистан", "currency": "UZS", "flag": "🇺🇿"},
    "KGS": {"country": "Кыргызстан", "currency": "KGS", "flag": "🇰🇬"},
    "AMD": {"country": "Армения", "currency": "AMD", "flag": "🇦🇲"},
    "KZT": {"country": "Казахстан", "currency": "KZT", "flag": "🇰🇿"},
}
DEFAULT_CORRIDORS = list(CORRIDORS)
SNAPSHOT_REF = "data/raw/cbr/latest_date.response.xml"
SNAPSHOT_AVAILABLE_AT = "2026-09-03T00:00:00+03:00"
# Synthetic UI rates only. They are deliberately not connected to a market or
# execution system, so the prototype never presents them as a promise.
DEMO_RATES_RUB = {"TJS": 0.105, "UZS": 145.0, "KGS": 0.92, "AMD": 4.55, "KZT": 5.75}
FRAME_DAYS = {"TJS": 2, "UZS": 2, "KGS": 3, "AMD": 2, "KZT": 2}


class PreferencesUpdate(BaseModel):
    enabled: bool = True
    corridors: list[str] = Field(default_factory=lambda: DEFAULT_CORRIDORS.copy())
    quiet_hours: str = "22:00–08:00"

    @field_validator("corridors")
    @classmethod
    def supported_corridors(cls, values: list[str]) -> list[str]:
        unknown = [value for value in values if value not in CORRIDORS]
        if unknown:
            raise ValueError(f"Неподдерживаемые направления: {', '.join(unknown)}")
        return values


class TransferRequest(BaseModel):
    corridor: str
    method: TransferMethod
    recipient: str = Field(min_length=3, max_length=64)
    amount_rub: int = Field(gt=0, le=1_000_000)
    debit_account: str = Field(min_length=3, max_length=64)

    @field_validator("corridor")
    @classmethod
    def supported_corridor(cls, value: str) -> str:
        if value not in CORRIDORS:
            raise ValueError("Выберите поддерживаемое направление")
        return value

    @model_validator(mode="after")
    def check_method_limit(self):
        if self.method == TransferMethod.card and self.amount_rub > 500_000:
            raise ValueError("Для перевода по карте демонстрационный лимит — 500 000 ₽")
        return self


class PushTrigger(BaseModel):
    corridor: str = "TJS"
    scenario: GateScenario = GateScenario.strong
    body: str | None = Field(default=None, min_length=1, max_length=240)

    @field_validator("corridor")
    @classmethod
    def supported_corridor(cls, value: str) -> str:
        if value.upper() not in CORRIDORS:
            raise ValueError("Выберите поддерживаемое направление")
        return value.upper()


app = FastAPI(
    title="Переводы за рубеж — PoC API",
    version="0.1.0",
    description=(
        "Демонстрационный API: все данные синтетические, переводы не исполняются, "
        "а статусы — UI-сценарии, не live-рыночные оценки."
    ),
)
app.mount("/static", StaticFiles(directory="static"), name="static")

preferences: dict = {}
transfers: list[dict] = []
push_inbox: list[dict] = []


def reset_demo_state() -> None:
    """Restore process-local demo data; called by tests and after a service restart."""
    preferences.clear()
    preferences.update({"enabled": True, "corridors": DEFAULT_CORRIDORS.copy(), "quiet_hours": "22:00–08:00"})
    transfers.clear()
    push_inbox.clear()


reset_demo_state()


def corridor_or_404(corridor: str) -> dict:
    result = CORRIDORS.get(corridor.upper())
    if not result:
        raise HTTPException(status_code=404, detail="Неподдерживаемое направление")
    return result


def gate_fixture(corridor: str, scenario: GateScenario) -> dict:
    details = corridor_or_404(corridor)
    scenarios = {
        GateScenario.strong: {
            "emit_push": True,
            "hint": {
                "title": "В такие периоды курс обычно выгоднее",
                "body": f"За ту же сумму в рублях можно отправить больше валюты. Обычно такой период для перевода в {details['country']} длится до {FRAME_DAYS[corridor.upper()]} дней.",
            },
        },
        GateScenario.expired: {
            "emit_push": True,
            "hint": None,
        },
        GateScenario.silent: {"emit_push": False, "hint": None},
    }
    gate = scenarios[scenario]
    return {
        "id": f"gate-{corridor.lower()}-{scenario.value}",
        "corridor": corridor.upper(),
        "country": details["country"],
        "currency": details["currency"],
        "scenario": scenario.value,
        "emit_push": gate["emit_push"],
        "hint": gate["hint"],
        "source_snapshot_ref": SNAPSHOT_REF,
        "available_at_t": SNAPSHOT_AVAILABLE_AT,
        "disclaimer": "Демо-фикстура: это не гарантия курса и не рекомендация переводить сейчас.",
    }


def quote_fixture(corridor: str, amount_rub: int) -> dict:
    details = corridor_or_404(corridor)
    rate = DEMO_RATES_RUB[corridor.upper()]
    return {
        "corridor": corridor.upper(), "currency": details["currency"], "amount_rub": amount_rub,
        "rate": rate, "fee_rub": 0, "recipient_amount": round(amount_rub * rate, 2),
        "rate_label": "Демо-ориентир, не курс исполнения",
    }


@app.get("/", include_in_schema=False)
def home() -> FileResponse:
    return FileResponse(Path("static/index.html"))


@app.get("/api/health", tags=["Сервис"], summary="Проверить состояние демонстрационного сервиса")
def health() -> dict:
    return {"status": "ok", "mode": "demo", "storage": "in-memory"}


@app.get("/api/corridors", tags=["Переводы"], summary="Получить поддерживаемые demo-направления")
def list_corridors() -> list[dict]:
    return [{"code": code, **details} for code, details in CORRIDORS.items()]


@app.get("/api/gates", tags=["Контекст перевода"], summary="Получить demo-фикстуры gate")
def list_gates(scenario: GateScenario = Query(GateScenario.strong)) -> list[dict]:
    return [gate_fixture(code, scenario) for code in CORRIDORS]


@app.get("/api/gates/{corridor}", tags=["Контекст перевода"], summary="Получить demo-gate для направления")
def get_gate(corridor: str, scenario: GateScenario = Query(GateScenario.strong)) -> dict:
    return gate_fixture(corridor, scenario)


@app.get("/api/quotes/{corridor}", tags=["Переводы"], summary="Рассчитать синтетический ориентир суммы получения")
def get_quote(corridor: str, amount_rub: int = Query(..., gt=0, le=1_000_000)) -> dict:
    return quote_fixture(corridor, amount_rub)


@app.get("/api/pushes", tags=["Пуши"], summary="Получить push только для пройденного demo-gate")
def list_pushes(corridor: str = "TJS", scenario: GateScenario = GateScenario.strong) -> list[dict]:
    gate = gate_fixture(corridor, scenario)
    if not gate["emit_push"]:
        return []
    return [build_push(gate)]


@app.post("/api/pushes", tags=["Пуши"], summary="Поставить тестовый push в очередь открытого web-прототипа")
def trigger_push(payload: PushTrigger) -> dict:
    gate = gate_fixture(payload.corridor, payload.scenario)
    if not gate["emit_push"]:
        return {"message": "В этом сценарии пуш не отправляется: пользователь видит обычный путь без контекста.", "emitted": False}
    push = build_push(gate, payload.body)
    push_inbox.append(push)
    return {"message": "Тестовый push поставлен в очередь открытого web-прототипа.", "emitted": True, "push": push}


def build_push(gate: dict, body: str | None = None) -> dict:
    return {
        "id": f"triggered-{uuid4()}",
        "title": "✦ Лови момент",
        "body": body or f"Сейчас выгодный курс для перевода в {gate['country']}!",
        "deep_link": f"/?corridor={gate['corridor']}&scenario={gate['scenario']}",
        "gate": gate,
    }


@app.get("/api/pushes/inbox", tags=["Пуши"], summary="Получить очередь тестовых push-уведомлений")
def get_push_inbox() -> list[dict]:
    return push_inbox


@app.get("/api/preferences", tags=["Настройки пушей"], summary="Получить process-local настройки demo-пушей")
def get_preferences() -> dict:
    return preferences


@app.put("/api/preferences", tags=["Настройки пушей"], summary="Заменить process-local настройки demo-пушей")
def update_preferences(update: PreferencesUpdate) -> dict:
    preferences.update(update.model_dump())
    return {"message": "Настройки сохранены только в памяти текущего запуска.", **preferences}


@app.post("/api/transfers", tags=["Переводы"], summary="Создать симулированный перевод")
def create_transfer(payload: TransferRequest) -> dict:
    transfer = {
        "id": str(uuid4()),
        **payload.model_dump(mode="json"),
        "country": corridor_or_404(payload.corridor)["country"],
        "quote": quote_fixture(payload.corridor, payload.amount_rub),
        "status": "simulated",
        "message": "Перевод создан в режиме симуляции. Деньги не списывались и не отправлялись.",
    }
    transfers.append(transfer)
    return transfer


@app.get("/api/transfers", tags=["Переводы"], summary="Получить переводы текущего demo-сеанса")
def list_transfers() -> list[dict]:
    return transfers
