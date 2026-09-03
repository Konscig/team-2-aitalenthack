# Feature Specification: Web Transfer Prototype

**Feature Branch**: `001-web-transfer-prototype`  
**Created**: 2026-09-03  
**Status**: Draft  
**Input**: User description: "Create a web-only mobile-app-like PoC based on supplied transfer screens, with mock signal, push, transfer and settings flows."

## Clarifications

### Session 2026-09-03

- Q: How should the PoC determine the signal status at push opening — `current`, `changed`, or `unknown`? → A: The status is set by a demo fixture or scenario parameter. It is a UI scenario, not a live market assessment.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Open a signal and start a transfer (Priority: P1)

A sender opens a demo notification about a cross-border transfer and sees whether the observed market moment is still current before entering the familiar transfer journey with the country selected.

**Why this priority**: This proves the core transition from a signal to a safe client action.

**Independent Test**: Open a sample notification for any supported corridor and verify that the chosen country, but not method, recipient, or amount, is carried into the transfer journey.

**Acceptance Scenarios**:

1. **Given** a current sample signal for RUB to Tajikistan, **When** the sender opens its notification, **Then** the sender sees a clear current-status explanation and can continue to the Tajikistan country selection context.
2. **Given** a changed or unknown sample signal, **When** the sender opens its notification, **Then** the original favourable-moment claim is not repeated as current and a neutral transfer route remains available.
3. **Given** a sender with an urgent need, **When** they open any signal state, **Then** they can immediately continue the ordinary transfer flow without pressure to wait.

---

### User Story 2 - Complete a simulated familiar transfer path (Priority: P1)

A sender can move through web forms that reflect the supplied payment, country, method, phone-recipient, and card-recipient screens, entering synthetic details and receiving a simulated result.

**Why this priority**: The PoC must make the signal transition tangible without claiming to execute a payment.

**Independent Test**: From Payments, select an eligible country, choose phone or card, enter mock details and an amount, and receive an explicitly simulated completion result.

**Acceptance Scenarios**:

1. **Given** the payments home screen, **When** the sender chooses international transfers and a supported country, **Then** they can choose a transfer method and see its illustrative speed, limit, and fee.
2. **Given** a selected phone or card method, **When** the sender completes required mock fields, **Then** they can continue to a simulated confirmation.
3. **Given** invalid or incomplete mock details, **When** the sender attempts to continue, **Then** the form explains which information needs correction and does not create a simulated transfer.

---

### User Story 3 - Inspect demo contracts and preferences (Priority: P2)

A demo operator can use documented demo contracts to retrieve sample signals and notifications, create a simulated transfer, and view or change non-personal notification preferences.

**Why this priority**: The team needs a simple integration seam for later signal and push work while retaining a demonstrable PoC today.

**Independent Test**: Use the documented demo contracts with a supported corridor and verify predictable mock results.

**Acceptance Scenarios**:

1. **Given** the demo documentation, **When** an operator requests signals for a supported corridor, **Then** the result includes source, date, rule version, and a freshness state.
2. **Given** the demo documentation, **When** an operator updates a notification preference, **Then** the result preserves the selected corridors and enabled state for the running demo session.
3. **Given** the demo documentation, **When** an operator submits a simulated transfer, **Then** the result identifies it as simulated and contains no execution rate or payment confirmation.

### Edge Cases

- A deep link contains an unsupported corridor: the sender receives a clear message and can return to country selection.
- Freshness data is unavailable: the status is `unknown`; no favourable-moment claim is displayed and the neutral path remains available.
- The amount is non-positive, missing, or exceeds an illustrative method limit: the form rejects it with a field-level explanation.
- A visitor refreshes a screen or opens it directly: the prototype shows a recoverable route to the appropriate preceding step.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The product MUST provide a browser-based, mobile-width prototype that mirrors the supplied order: Payments, international transfer, country, method, recipient details, amount, and simulated continuation.
- **FR-002**: The product MUST present Tajikistan, Uzbekistan, Kyrgyzstan, Kazakhstan, and Armenia as supported demo destinations.
- **FR-003**: The product MUST show phone, card, and account methods with illustrative details before data entry; only phone-recipient and card-recipient branches are interactive in this PoC, while the account method is visibly informational.
- **FR-004**: The product MUST clearly label every transfer action and result as simulated; it MUST not initiate a real payment.
- **FR-005**: The product MUST provide a sample notification and signal-opening journey for `current`, `changed`, and `unknown` freshness states; each state MUST be selected deterministically by a demo fixture or scenario parameter until the signal layer is connected, and MUST be labelled as a demo scenario rather than a live market assessment.
- **FR-006**: The product MUST ensure that a notification deep link selects only the destination country; it MUST NOT prefill a method, recipient, amount, account, or other payment detail.
- **FR-007**: The product MUST use only neutral, present or historical market-language examples; it MUST NOT contain forecasts, guarantees, execution rates, exact savings, or personal financial advice.
- **FR-008**: The product MUST provide a clearly visible ordinary-transfer route in every signal freshness state, including an urgent-transfer route.
- **FR-009**: The product MUST expose documented demo contracts for sample signals, sample push notifications, simulated transfers, and notification preferences.
- **FR-010**: The product MUST return source, public-source snapshot identifier available at date T, observation date, rule version, corridor, and freshness state with each sample signal or notification where applicable.
- **FR-011**: The product MUST validate required transfer fields and keep all submitted data in memory only for the running demo session.
- **FR-012**: The product MUST avoid collecting real payment credentials, user identifiers, client history, or secrets; all defaults and examples MUST be synthetic.

### Key Entities

- **Corridor**: A supported RUB-to-recipient-currency destination, including country and currency code.
- **Signal**: A synthetic UI scenario anchored to an identified public-source snapshot available at date T; it includes source, observation date, rule version, status at opening, and neutral explanatory text, but is not a live market assessment.
- **Push notification**: A sample message referencing one signal and its country-only navigation context.
- **Transfer draft**: A synthetic sender input for a selected country and method, validated only for prototype demonstration.
- **Notification preferences**: In-memory opt-in state and selected corridors for the demo session.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A reviewer can complete either supported transfer branch from the payments screen to a simulated result in under 2 minutes.
- **SC-002**: A reviewer can demonstrate all three freshness states and reach a neutral ordinary-transfer route from each in under 30 seconds.
- **SC-003**: All documented demo endpoints return a valid response for the five supported corridors and reject unsupported corridors with an understandable error.
- **SC-004**: In a content review, 100% of displayed signal and notification examples avoid forecast, guarantee, exact saving, execution-rate, and financial-advice claims.
- **SC-005**: In a deep-link check, 100% of entries reach the selected country without prefilled method, recipient, or amount.

## Assumptions

- The supplied screenshots are visual and flow references, not a source of production text, pricing, authentication, or real payment behavior.
- Russian is the initial PoC interface language; translation and localization are future extension points rather than a claim of production language coverage.
- Sample statuses and notification content are manually defined fixtures or scenario parameters until the separate reproducible signal layer is connected.
- The service is a hackathon demo with in-memory data only; persistence, real push delivery, authentication, client communication policy, and execution pricing are out of scope.
- Illustrative method conditions are demonstrative only and must not be treated as actual bank terms.
- The account method is displayed to match the supplied selection screen but has no detailed form branch in the PoC.
- The result screen is a synthetic continuation because the supplied screens do not show the real bank confirmation, execution rate, or final transfer result.
- Quiet hours are a display-only demo preference, not a configured contact policy or delivery schedule; channel, time zone, and production quiet hours require a pilot decision.
