# Implementation Plan: Web Transfer Prototype

**Branch**: `001-web-transfer-prototype` | **Date**: 2026-09-03 | **Spec**: [spec.md](spec.md)

## Summary

Build a small browser-based, mobile-width transfer-flow PoC based on the supplied reference screens. A FastAPI service will serve the static interface and documented demo contracts for deterministic signal fixtures, mock push notifications, in-memory preferences, and explicitly simulated transfers. Fixtures are UI scenarios anchored to retained public-source snapshot metadata, not live market assessments. The UI supports the five approved corridors, displays all three reference methods, and provides phone/card recipient branches; it makes a country-only transition from the notification and safely demonstrates all three signal freshness states.

## Technical Context

**Language/Version**: Python 3.11+; HTML, CSS, and browser JavaScript

**Primary Dependencies**: FastAPI, Uvicorn, Pydantic, pytest

**Storage**: Process-memory fixtures and collections only; reset on service restart

**Testing**: pytest with FastAPI TestClient for contracts; browser/manual walkthrough for visual form flow

**Target Platform**: Local developer machine; modern desktop browser at mobile-width viewport

**Project Type**: Single web service with static browser client

**Performance Goals**: A reviewer completes either transfer branch in under 2 minutes and can reach a neutral ordinary-transfer route from each freshness state in under 30 seconds. No production latency or availability target is claimed.

**Constraints**: No database, authentication, real payment processing, production push provider, personal data, execution rate, or real bank credentials. Only RUB→TJS/UZS/KGS/AMD/KZT may be shown. Links from notifications carry only the corridor. A fixture includes its retained-public-snapshot reference and availability at date T but never asserts a live market condition. Text is Russian for the initial PoC and remains neutral and factual. The account method is visual-only; the final result is a synthetic continuation, not a bank confirmation.

**Scale/Scope**: One service, one static mobile-first UI, five corridors, two detailed transfer branches, three deterministic signal states, and a small set of documented JSON contracts.

## Constitution Check

| Principle | Design response | Status |
|---|---|---|
| I. Evidence Before Claims | Each fixture identifies a retained public-source snapshot available at date T, source, observation date, rule version, corridor, and deterministic UI state. The UI labels it as a demo scenario and does not claim live signal quality or customer outcomes. | PASS |
| II. Honest, Compliant Financial Communication | Copy is limited to a neutral current/historical public-reference observation; it excludes forecasts, guarantees, execution rates, savings, spread, margin, and advice. | PASS |
| III. User Agency and Safe Transfer Flow | The deep link validates and selects only country. `changed`/`unknown` never repeat a favourable claim; every state has an immediate neutral transfer route. | PASS |
| IV. Reproducible, Corridor-Specific Signals | The PoC uses explicit per-corridor fixture metadata and does not calculate or fabricate market observations. Integration to the separate data pipeline is deferred. | PASS |
| V. Demo Simplicity and Explicit Boundaries | All transfers and pushes are simulated; only in-memory synthetic data is used, with no payment or database integration. | PASS |

**Post-design re-check**: PASS. The contracts, data model, and quickstart retain all five boundaries. No constitution exception or complexity justification is needed.

## Project Structure

### Documentation (this feature)

```text
specs/001-web-transfer-prototype/
├── plan.md
├── research.md
├── mechanics-review.md
├── content-library.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── openapi.yaml
└── tasks.md                 # created by speckit-tasks
```

### Source Code (repository root)

```text
app.py                       # FastAPI application, fixtures, request models, routes
static/
├── index.html               # mobile-width prototype shell
├── styles.css               # reference-inspired visual styles
└── app.js                   # screen navigation and same-origin contract calls
tests/
└── test_web_poc.py          # contract and core safety-flow tests
```

**Structure Decision**: Use a deliberately flat single-service structure. The PoC has no persistence or external integrations, so separate repositories, services, or a frontend build system would obscure the student-level implementation without improving the demo. `mechanics-review.md` records the selected stale-signal interaction, and `content-library.md` constrains the copy used in the UI.

## Complexity Tracking

No constitution violations or additional complexity require justification.
