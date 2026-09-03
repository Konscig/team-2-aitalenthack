<!--
Sync Impact Report
- Version change: template/unversioned -> 1.0.0
- Modified principles: none (initial adoption)
- Added sections: Demo Scope and Data Boundaries; Development Workflow and Quality Gates
- Removed sections: none
- Follow-up TODOs: Production NFRs, SLA, quiet hours, RTO/RPO, and legal requirements require
  agreement before a production pilot.
-->
# «Выгодный момент для трансграничного перевода» Constitution

## Core Principles

### I. Evidence Before Claims
Every market-signal claim MUST use reproducible public data and a pre-declared label. Walk-forward
evaluation MUST use only data available as of date T; future observations, time-leaking random
splits, and retrospective threshold tuning on test windows are prohibited. Each corridor and
horizon MUST report hit rate, lift versus a defined random baseline, benefit-of-timing, frequency,
clustering, and out-of-time stability. A persuasive chart alone is not evidence.

Rationale: the demo can establish statistical informativeness, not proven customer or business
outcomes.

### II. Honest, Compliant Financial Communication
The product MUST state only a current or historical relative market fact, never a forecast,
guarantee, investment recommendation, exact saving, execution rate, spread, margin, or personal
financial advice. Public CBR data MUST be labelled an analytical reference, not a bank execution
rate. If evidence or freshness is insufficient, the product MUST remain neutral.

Rationale: an inaccurate financial message harms trust more than an omitted notification.

### III. User Agency and Safe Transfer Flow
The notification MAY preselect only the country; method, recipient, amount, and other payment data
remain the user's choice. On open, the interface MUST distinguish `актуально`, `изменилось`, and
`неизвестно`; the latter two MUST not repeat the original favourable-moment claim. A transfer with
a critical deadline MUST always have an immediate neutral route to complete the fake transfer, with
no pressure to wait or implication that proceeding is wrong.

Rationale: the feature assists rather than controls an important family-transfer decision.

### IV. Reproducible, Corridor-Specific Signal Engineering
The pipeline MUST retain raw source artefacts, metadata, currency-code mapping, normalisation rules,
and generated outputs needed to reproduce a run. Rates MUST be normalised to RUB per one recipient
currency unit; for a RUB sender, a lower unit rate is more favourable. Signals and evaluation MUST
be separate for RUB→TJS, RUB→UZS, RUB→KGS, RUB→AMD, and RUB→KZT. Features MUST be causal at date T
and MUST NOT fabricate market observations for non-business days.

Rationale: nominal values differ across currencies and future-aware calculations invalidate results.

### V. Demo Simplicity and Explicit Boundaries
The hackathon demo MUST use no personal or internal bank data, database, production push platform,
payment processing, or real money movement. It MUST label transfer actions and results as
simulated. Transparent rules are the baseline; `ML-Min` is allowed only after comparison with it,
and `ML-Max` only after stable out-of-time improvement without weaker interpretability, rarity, or
clustering.

Rationale: the goal is a credible demonstration, not imitation of unavailable banking systems.

## Demo Scope and Data Boundaries

The source is public Bank of Russia currency history, retained with raw responses and metadata.
Initial coverage is at least five years and the five customer-facing corridors named above. USD,
EUR, and CNY may support research but do not expand demo scope without a later specification.

Standard horizons are **1, 3, 5, 10, and 20 calendar days** after a signal. The model targets no
more than **1–2 signals per week per corridor**; this is not a per-client communications policy.
No numeric production NFRs are approved for this demo: SLA, latency, availability, quiet hours,
RTO/RPO, scalability, legal approval, and production observability are pilot prerequisites.

Assumptions affecting results or UI MUST be recorded in `docs/QA_ALIGNMENT.md` or the relevant
feature specification. Public-data results MUST NOT be framed as proof of customer comprehension,
conversion, incremental volume, or benefit received by a family; those require research and a
controlled pilot.

## Development Workflow and Quality Gates

Changes to ingestion, normalisation, features, signals, or client flow MUST have proportionate
automated checks. Data tests MUST cover normalisation, source schemas, missing/non-business days,
and causality. Signal changes MUST include a reproducible date-T run and a report or decision matrix
with Principle I metrics. UI changes MUST exercise all three freshness states and the urgent route.

Specifications and implementation MUST be committed in small, logical, reversible Git commits. A
commit MUST have one coherent purpose and a descriptive message; it MUST NOT absorb unrelated or
another contributor's changes. Before hand-off, tracked inputs must complete the documented run.

## Governance

This constitution governs product, ML, interface, data, and documentation work and supersedes
conflicting informal practices. An amendment requires a written rationale, an impact assessment for
specifications, reports, data contracts, and tests, and a Git commit recording the change. The team
may approve it during the hackathon through the amended constitution and commit history.

Versioning follows semantic intent: MAJOR for incompatible removal or redefinition of a principle,
MINOR for a new principle or material expansion, and PATCH for a non-semantic clarification. Every
specification, plan, task list, review, and hand-off MUST check the five principles. An exception
MUST be explicit, time-bounded, and documented with its risk and owner; it cannot silently weaken
financial-communication or data-causality rules.

**Version**: 1.0.0 | **Ratified**: 2026-09-03 | **Last Amended**: 2026-09-03
