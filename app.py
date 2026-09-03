"""Autonomous web PoC for the cross-border transfer client journey."""

from datetime import date
from enum import Enum
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator, model_validator


class FreshnessStatus(str, Enum):
    current = "current"
    changed = "changed"
    unknown = "unknown"


class ModelScenario(str, Enum):
    favorable_now = "favorable_now"
    withhold = "withhold"
    better_later = "better_later"


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
    status: FreshnessStatus = FreshnessStatus.changed
    model_scenario: ModelScenario = ModelScenario.withhold
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


def model_assessment_fixture(scenario: ModelScenario) -> dict:
    options = {
        ModelScenario.favorable_now: {"scenario": scenario.value, "client_label": "Демо-модель: есть основания рассмотреть перевод сегодня", "push_label": "Есть основания рассмотреть перевод сегодня.", "disclaimer": "Тестовая метка модели, не финансовая рекомендация и не гарантия курса."},
        ModelScenario.withhold: {"scenario": scenario.value, "client_label": None, "push_label": None, "disclaimer": "Модель не даёт клиентской оценки в этом сценарии."},
        ModelScenario.better_later: {"scenario": scenario.value, "client_label": "Демо-прогноз: в следующем окне может быть выгоднее", "push_label": "В следующем окне может быть выгоднее.", "forecast_date": "2026-09-04", "disclaimer": "Тестовый прогноз модели, не финансовая рекомендация и не гарантия курса."},
    }
    return options[scenario]


def signal_fixture(corridor: str, status: FreshnessStatus, model_scenario: ModelScenario = ModelScenario.withhold) -> dict:
    details = corridor_or_404(corridor)
    messages = {
        FreshnessStatus.current: "Публичный ориентир в демо-сценарии не изменился. Если перевод можно не торопить, вы можете открыть обычный путь.",
        FreshnessStatus.changed: "С момента пуша публичный ориентир изменился. Не используйте старое уведомление как основание для решения.",
        FreshnessStatus.unknown: "Свежесть публичного ориентира не подтверждена. Мы не знаем, сохранился ли описанный в пуше контекст.",
    }
    return {
        "id": f"demo-{corridor.lower()}-{status.value}",
        "corridor": corridor.upper(),
        "country": details["country"],
        "currency": details["currency"],
        "freshness_status": status.value,
        "source": "Банк России, публичный аналитический ориентир",
        "source_snapshot_ref": SNAPSHOT_REF,
        "available_at_t": SNAPSHOT_AVAILABLE_AT,
        "observation_date": str(date(2026, 9, 3)),
        "rule_version": "demo-ui-scenario-1",
        "message": messages[status],
        "model_assessment": model_assessment_fixture(model_scenario),
        "disclaimer": "Демо-сценарий, не курс исполнения, не прогноз и не рекомендация переводить сейчас.",
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


@app.get("/api/signals", tags=["Сигналы"], summary="Получить UI-сценарии сигналов")
def list_signals(status: FreshnessStatus = Query(FreshnessStatus.current), model_scenario: ModelScenario = Query(ModelScenario.withhold)) -> list[dict]:
    return [signal_fixture(code, status, model_scenario) for code in CORRIDORS]


@app.get("/api/signals/{corridor}", tags=["Сигналы"], summary="Получить UI-сценарий для направления")
def get_signal(corridor: str, status: FreshnessStatus = Query(FreshnessStatus.current), model_scenario: ModelScenario = Query(ModelScenario.withhold)) -> dict:
    return signal_fixture(corridor, status, model_scenario)


@app.get("/api/quotes/{corridor}", tags=["Переводы"], summary="Рассчитать синтетический ориентир суммы получения")
def get_quote(corridor: str, amount_rub: int = Query(..., gt=0, le=1_000_000)) -> dict:
    return quote_fixture(corridor, amount_rub)


@app.get("/api/pushes", tags=["Пуши"], summary="Получить синтетический push и country-only deep link")
def list_pushes(corridor: str = "TJS", status: FreshnessStatus = FreshnessStatus.current, model_scenario: ModelScenario = ModelScenario.withhold) -> list[dict]:
    signal = signal_fixture(corridor, status, model_scenario)
    return [{
        "id": f"push-{signal['id']}",
        "title": f"Демо: перевод в {signal['country']}",
        "body": "Откройте, чтобы посмотреть статус публичного ориентира.",
        "deep_link": f"/?corridor={signal['corridor']}&status={signal['freshness_status']}&model_scenario={model_scenario.value}",
        "signal": signal,
    }]


@app.post("/api/pushes", tags=["Пуши"], summary="Поставить тестовый push в очередь открытого web-прототипа")
def trigger_push(payload: PushTrigger) -> dict:
    signal = signal_fixture(payload.corridor, payload.status, payload.model_scenario)
    model = signal["model_assessment"]
    push = {
        "id": f"triggered-{uuid4()}",
        "title": f"Перевод в {signal['country']}" + (" · можно сейчас" if payload.model_scenario == ModelScenario.favorable_now else ""),
        "body": payload.body or signal["message"],
        "model_label": model["client_label"],
        "deep_link": f"/?corridor={signal['corridor']}&status={signal['freshness_status']}&model_scenario={payload.model_scenario.value}",
        "signal": signal,
    }
    push_inbox.append(push)
    return {"message": "Тестовый push поставлен в очередь открытого web-прототипа.", "push": push}


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
