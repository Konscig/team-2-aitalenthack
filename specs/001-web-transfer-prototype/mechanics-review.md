# Review of Stale-Signal Mechanics

## Decision

Use a status card immediately after opening the demo push. It states whether the UI scenario is `current`, `changed`, or `unknown`, identifies the retained public-source snapshot, and offers two equal, non-pressuring actions: continue the ordinary transfer with only the country selected, or return later. For urgent needs, ordinary transfer is the immediate primary route.

The status is a demonstration of client-flow handling, not a live market assessment or a bank execution quote.

## Alternatives compared

| Mechanic | What the sender sees | Strength | Risk for this PoC | Decision |
|---|---|---|---|---|
| Current-status card + ordinary route | Status, source snapshot, disclaimer, and immediate country-only transfer entry | Handles all three states and preserves urgency/user agency | Needs careful neutral copy | Selected |
| Comparison with moment of push | A comparison of the push-time and opening-time observations | Can explain why a status changed | Requires a live/reproducible opening-time data calculation absent from the PoC | Deferred to signal integration |
| Return later only | A neutral stale message and no transfer action | Lowest risk of stale claim | Blocks or discourages urgent transfer | Rejected |

## Selection criteria

1. Honest freshness: no push-time observation is presented as a live transfer condition.
2. User agency: country may be selected, but method, recipient, amount, and account remain blank.
3. Urgent path: the normal transfer route stays visible without requiring an explanation of urgency.
4. Fit with the existing flow: the status sits before country/method/requisites rather than replacing the transfer journey.
5. Implementability: works with retained fixtures until the reproducible signal service is connected.

## External practice considered

Wise separates rate tracking/alerts from the actual conversion and warns that a tracked rate may not be available when a transfer is made. This supports separating a notification from the later transfer decision and avoiding a promise about execution conditions. [Wise rate alerts](https://wise.com/us/tools/exchange-rate-alerts) and [Wise Rate Tracker terms](https://wise.com/gb/legal/rate-tracker).

Wise also lets users manage notification preferences separately from transfer operations. This supports keeping PoC settings non-transactional. [Wise notification settings](https://wise.com/help/articles/2952327/how-do-i-manage-my-notifications).

## Scope boundary

The selected mechanism intentionally does not compare rates, show an execution quote, fix a rate, schedule a conversion, or claim a saving. Those capabilities require the future signal and transfer-condition integrations.
