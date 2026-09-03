# Research: Web Transfer Prototype

## Decision 1: Keep demo state in module-level fixtures

**Decision**: Use deterministic in-memory fixtures for corridors, UI-scenario signals, pushes, preferences, and simulated transfers; provide a reset helper for tests. Every signal fixture carries a retained public-source snapshot identifier and its availability at date T, while the freshness state remains an explicitly labelled UI scenario rather than a live assessment.

**Rationale**: The PoC explicitly excludes a database and only needs repeatable scenarios. Fixtures make `current`, `changed`, and `unknown` demonstrable without pretending that a live signal pipeline exists, while preserving the traceability required for any historical market reference.

**Alternatives considered**:

- SQLite/ORM — would add persistence that the demo neither needs nor permits.
- External mock service — adds deployment and operational work without user value.

## Decision 2: Serve one static mobile-first page from the service

**Decision**: Serve a single HTML/CSS/vanilla-JavaScript page and mount its static files from the same FastAPI process. The client calls same-origin `/api/*` routes.

**Rationale**: It most directly reproduces the supplied screen forms and keeps the implementation readable for a student-level PoC. It avoids a separate frontend build tool and CORS configuration. FastAPI supports mounting a static directory ([documentation](https://fastapi.tiangolo.com/tutorial/static-files/)).

**Alternatives considered**:

- Server-rendered templates — suitable but no simpler for the small amount of interactive navigation.
- Separate React/Vite SPA — unnecessary dependencies and build tooling for this scope.

## Decision 3: Use generated OpenAPI and Swagger UI as the contract explorer

**Decision**: Define typed request/response models and route metadata so the service exposes OpenAPI, Swagger UI at `/docs`, and the schema at `/openapi.json`.

**Rationale**: Reviewers can inspect and execute the demo contracts before and alongside the UI. Typed models keep the executable contract aligned with the implementation ([metadata](https://fastapi.tiangolo.com/tutorial/metadata/), [request bodies](https://fastapi.tiangolo.com/tutorial/body/)).

**Alternatives considered**:

- Manually maintained Swagger document only — higher risk of drift.
- Postman collection only — less discoverable and not self-documenting in the app.

## Decision 4: Validate at the contract boundary

**Decision**: Use constrained Pydantic schemas and enum-like corridor, status, and method values. Invalid bodies return standard validation responses; missing fixture IDs return clear not-found results.

**Rationale**: This keeps the route handlers small, produces visible contract constraints, and covers the negative scenarios in the specification.

**Alternatives considered**:

- Untyped dictionaries — unclear contract and repetitive validation.
- A custom validation framework — unjustified for this PoC.

## Decision 5: Treat communication safety as a testable product boundary

**Decision**: Fixtures contain only neutral factual text plus source, date, rule version, corridor, and freshness status. `changed` and `unknown` suppress the original favourable claim. The notification link carries only country.

**Rationale**: This implements Constitution Principles II–III and the agreed Q&A position. The public reference is never an execution rate or recommendation.

**Alternatives considered**:

- Benefit/savings copy — could imply an execution result or financial advice.
- Calculating status from live data — depends on the separate reproducible date-T signal pipeline, outside this PoC.

## Decision 6: Use repeatable route tests plus a short visual walkthrough

**Decision**: Add pytest/TestClient checks for root/static availability, every corridor, every status, invalid data, country-only deep links, urgent ordinary route, and explicit simulation labels; run a browser walkthrough for the two form branches.

**Rationale**: Automated checks establish contract and safety behavior without a running server ([FastAPI testing documentation](https://fastapi.tiangolo.com/tutorial/testing/)); the browser walkthrough checks the screen-form experience that unit tests cannot assess.

**Alternatives considered**:

- Manual Swagger testing only — non-repeatable.
- Full browser automation suite — disproportionate to the static PoC; can be added later.
