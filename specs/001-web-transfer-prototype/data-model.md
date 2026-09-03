# Data Model: Web Transfer Prototype

All entities are synthetic and process-local. They are reset when the demo service restarts.

## Corridor

| Field | Type | Rules |
|---|---|---|
| code | string | One of `TJS`, `UZS`, `KGS`, `AMD`, `KZT`; unique key |
| country | string | Display name of the destination country |
| currency | string | Recipient ISO currency code; equals `code` in this PoC |

## Signal

| Field | Type | Rules |
|---|---|---|
| id | string | Unique deterministic fixture ID |
| corridor | Corridor code | Must reference a supported corridor |
| freshness_status | string | `current`, `changed`, or `unknown`; chosen by fixture/scenario parameter |
| observation_date | date string | Date of the public analytical observation |
| source | string | Must identify the public analytical reference |
| source_snapshot_ref | string | Identifier/path of a retained public-source snapshot available at date T |
| available_at_t | date-time string | When the referenced public snapshot was available to the scenario |
| rule_version | string | Identifies the fixture rule/version |
| message | string | Neutral current/historical wording only |
| disclaimer | string | States that it is not an execution rate, forecast, or recommendation |

**State handling**: The state is a deterministic UI scenario, not a live market assessment. `current` may describe the retained observed reference; `changed` and `unknown` must not restate it as a current favourable condition; `unknown` has no claim of freshness.

## Push Notification

| Field | Type | Rules |
|---|---|---|
| id | string | Unique fixture ID |
| title | string | Names the destination, not a promised benefit |
| body | string | Neutral invitation to inspect status |
| signal_id | Signal ID | References one signal fixture |
| deep_link | string | Carries only the valid corridor and optional fixture status |

## Notification Preferences

| Field | Type | Rules |
|---|---|---|
| enabled | boolean | Demo opt-in switch |
| corridors | list[Corridor code] | Every value must be supported; may be empty |
| quiet_hours | string | Display-only demo setting; no actual scheduling or delivery |

## Transfer Draft and Simulated Transfer

| Field | Type | Rules |
|---|---|---|
| id | string | Generated only for a successfully simulated transfer |
| corridor | Corridor code | Required and supported |
| method | string | `phone` or `card` in the detailed form branches |
| recipient | string | Required synthetic form input; no real credential validation |
| amount_rub | number | Required and greater than zero; illustrative limit is 1,000,000 ₽ for phone and 500,000 ₽ for card |
| debit_account | string | Required synthetic account label; never a real account number |
| status | string | Always `simulated` |
| message | string | Explicitly says that no money was moved |

**Lifecycle**: draft form input → validation error, or → simulated transfer result. There is no pending, sent, executed, or failed payment lifecycle.

## Relationships

- A Corridor has zero or more Signal fixtures and Push Notification fixtures.
- A Push Notification references one Signal and navigates to that Signal's Corridor only.
- A Notification Preferences record selects zero or more Corridors.
- A simulated Transfer references one Corridor but is not linked to an identity, account, or real payment.
