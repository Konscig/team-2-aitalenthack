---

description: "Actionable implementation tasks for the Web Transfer Prototype"
---

# Tasks: Web Transfer Prototype

**Input**: Design documents from `/specs/001-web-transfer-prototype/`

**Prerequisites**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md), [data-model.md](data-model.md), [contracts/openapi.yaml](contracts/openapi.yaml), [quickstart.md](quickstart.md)

**Tests**: Included because the constitution requires proportionate automated checks for UI changes, all three freshness states, and the urgent route.

**Organization**: Tasks are grouped by user story so each increment can be demonstrated and tested independently after shared setup.

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Add the minimum runtime and test dependencies for a single-process web PoC.

- [ ] T001 Add FastAPI and Uvicorn runtime dependencies to `requirements.txt`
- [ ] T002 Create the web-PoC test module and a reusable TestClient fixture in `tests/test_web_poc.py`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Establish the one-process service, static asset shell, shared fixture entities, and neutral demo boundaries required by every story.

**⚠️ CRITICAL**: Complete this phase before starting user-story work.

- [ ] T003 Create the FastAPI application, generated OpenAPI metadata, `/docs`, root route, and static-file mounting in `app.py`
- [ ] T004 Define supported corridors, deterministic fixture reset helper, and shared Pydantic schemas in `app.py`
- [ ] T005 [P] Create the mobile-width page shell and bottom navigation in `static/index.html`
- [ ] T006 [P] Create dark, reference-inspired mobile layout primitives and accessible focus states in `static/styles.css`
- [ ] T007 Create shared browser state, safe rendering helpers, and recoverable screen navigation in `static/app.js`
- [ ] T008 Add foundation tests for service health, root page, static assets, and all five supported corridors in `tests/test_web_poc.py`

**Checkpoint**: The empty but runnable service and mobile shell work locally; all stories can now use the common fixture layer.

---

## Phase 3: User Story 1 - Open a signal and start a transfer (Priority: P1) 🎯 MVP

**Goal**: Open a deterministic demo push, show `current`, `changed`, or `unknown` safely, and enter a transfer flow with only the country selected.

**Independent Test**: Request/open a push for each status and a supported corridor; verify required signal metadata, neutral changed/unknown content, urgent ordinary-transfer action, and absence of method/recipient/amount/account prefill.

### Tests for User Story 1

- [ ] T009 [US1] Add contract tests for signal and push fixtures, all three statuses, source snapshot/availability metadata, and unsupported-corridor errors in `tests/test_web_poc.py`
- [ ] T010 [US1] Add safety-flow tests for country-only deep links and an ordinary urgent-transfer route in `tests/test_web_poc.py`

### Implementation for User Story 1

- [ ] T011 [US1] Implement neutral UI-scenario signal fixtures with retained public-source snapshot and date-T availability metadata, plus `GET /api/signals` and `GET /api/signals/{corridor}` in `app.py`
- [ ] T012 [US1] Implement `GET /api/pushes` with a validated country-only deep link in `app.py`
- [ ] T013 [US1] Implement the demo-push entry and signal-status screen for `current`, `changed`, and `unknown`, labelled as a UI scenario rather than a live assessment, in `static/app.js`
- [ ] T014 [US1] Add content-library wording, non-colour status labels, source-snapshot disclaimer, and equal-priority ordinary-transfer action styles in `static/styles.css`

**Checkpoint**: A reviewer can demonstrate every status and immediately reach a neutral transfer path without a real signal calculation or a claim of benefit.

---

## Phase 4: User Story 2 - Complete a simulated familiar transfer path (Priority: P1)

**Goal**: Reproduce the reference journey from Payments through country and method selection to phone/card details and an explicitly simulated result.

**Independent Test**: From the Payments screen, choose any supported corridor and either phone or card, submit valid synthetic details and a positive amount, and receive a simulated result; invalid fields must not create it.

### Tests for User Story 2

- [ ] T015 [US2] Add transfer contract tests for phone/card happy paths, missing fields, non-positive amounts, the 1,000,000 ₽ phone and 500,000 ₽ card limits, and simulation labels in `tests/test_web_poc.py`

### Implementation for User Story 2

- [ ] T016 [US2] Implement `POST /api/transfers` and `GET /api/transfers` with method-specific illustrative limits and in-memory simulated results only in `app.py`
- [ ] T017 [US2] Implement Payments, country, three-method selection with visual-only account option, phone-recipient, card-recipient, validation, and synthetic-result screens in `static/app.js`
- [ ] T018 [US2] Style method cards, form controls, validation messages, and the simulated-result marker in `static/styles.css`
- [ ] T019 [US2] Add a visible simulated-transfer notice and synthetic-input guidance to `static/index.html`

**Checkpoint**: Both detailed reference branches work without real credentials, payment processing, or a claimed execution rate.

---

## Phase 5: User Story 3 - Inspect demo contracts and preferences (Priority: P2)

**Goal**: Let a demo operator inspect and execute Swagger contracts for signals, pushes, transfers, and process-local notification preferences.

**Independent Test**: In Swagger, retrieve a supported signal/push, replace preferences with supported corridors only, create a simulated transfer, and confirm all state resets after service restart.

### Tests for User Story 3

- [ ] T020 [US3] Add tests for generated `/docs` and `/openapi.json`, preference read/update, invalid preference corridor, and restart/reset helper behavior in `tests/test_web_poc.py`

### Implementation for User Story 3

- [ ] T021 [US3] Implement `GET /api/preferences` and `PUT /api/preferences` with process-memory semantics in `app.py`
- [ ] T022 [US3] Add a demo notification-preferences screen that reads and updates only synthetic settings in `static/app.js`
- [ ] T023 [US3] Add preference controls and the no-real-delivery explanation in `static/styles.css`
- [ ] T024 [US3] Align FastAPI route tags, summaries, response models, date-T snapshot metadata, and validation descriptions with `specs/001-web-transfer-prototype/contracts/openapi.yaml` in `app.py`

**Checkpoint**: Swagger is usable as the requested interface explorer and all operator-facing data remains local to the running process.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Check the integrated demo against product safety, visual references, and reproducible instructions.

- [ ] T025 [P] Review all strings in `app.py` and `static/app.js` against `specs/001-web-transfer-prototype/content-library.md` and its forbidden-claims rules
- [ ] T026 [P] Compare the form order, three-method selection, alternate phone/card branches, and synthetic confirmation boundary in `static/app.js` and `static/styles.css` with `docs/screenshots/README.md`
- [ ] T027 Update web-PoC launch and Swagger instructions in `README.md`
- [ ] T028 Run the automated checks and manual walkthroughs from `specs/001-web-transfer-prototype/quickstart.md`, including plain-language and no-colour status checks, and record any deviations in `specs/001-web-transfer-prototype/quickstart.md`

---

## Dependencies & Execution Order

```text
Setup (T001–T002)
        ↓
Foundation (T003–T008)
        ↓
US1: signal/push safe path (T009–T014) ──────┐
US2: simulated transfer forms (T015–T019) ──┼──→ Polish (T025–T028)
US3: Swagger/preferences (T020–T024) ───────┘
```

### Story Dependencies

- **US1 (P1)**: Depends only on the foundation. This is the MVP: deterministic signal state → safe ordinary transfer entry.
- **US2 (P1)**: Depends only on the foundation. It may be implemented alongside US1, although integrating the US1 entry afterward is a small final wiring step in `static/app.js`.
- **US3 (P2)**: Depends only on the foundation and may be implemented in parallel with both P1 stories.

## Parallel Opportunities

- T002, T005, and T006 may proceed in parallel after T001 is understood.
- In Phase 3, T009 and T010 are sequential because they use the same test module; T013 and T014 can proceed in parallel after T011–T012 define the response contract.
- In Phase 4, T017 and T018 can proceed in parallel after T016; T019 may proceed in parallel with them.
- In Phase 5, T022 and T023 can proceed in parallel after T021; T024 follows the route implementation.
- T025 and T026 affect distinct review targets and can proceed in parallel after all stories are complete.

## Parallel Example: User Story 2

```text
Task: "Implement Payments, country, method, phone-recipient, card-recipient, validation, and simulated-result screens in static/app.js"
Task: "Style method cards, form controls, validation messages, and the simulated-result marker in static/styles.css"
Task: "Add a visible simulated-transfer notice and synthetic-input guidance to static/index.html"
```

## Implementation Strategy

### MVP First

1. Complete T001–T008.
2. Complete US1 (T009–T014).
3. Validate all three status flows and country-only navigation before continuing.

### Incremental Delivery

1. Add US2 to make the ordinary-transfer continuation tangible.
2. Add US3 to expose the requested Swagger contracts and mock settings.
3. Complete the cross-cutting checks; do not claim live signals, real push delivery, or payments.

## Notes

- Every task follows the required checkbox, ID, story-label, and file-path format.
- Keep commits small and logical, following the constitution.
