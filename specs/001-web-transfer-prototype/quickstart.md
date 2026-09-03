# Quickstart: Validate the Web Transfer Prototype

## Prerequisites

- Python 3.11 or newer
- Dependencies from `requirements.txt` plus the web-service dependencies introduced by implementation
- A modern browser

## Run

```bash
python -m pip install -r requirements.txt
python -m uvicorn app:app --reload
```

Open the web prototype at `http://127.0.0.1:8000` and the generated Swagger UI at `http://127.0.0.1:8000/docs`.

## Automated validation

```bash
pytest tests/test_web_poc.py
```

The checks must cover the contracts in [openapi.yaml](contracts/openapi.yaml) and confirm all five corridors, the three fixture statuses, invalid input, explicit simulation, and no-country fallback.

## Manual walkthroughs

1. Start at Payments → international transfers → choose Tajikistan → phone recipient → enter synthetic details and a positive amount → receive an explicitly simulated result.
2. Repeat from the method screen with the card-recipient branch.
3. Open the demo-push route for each status: `current`, `changed`, and `unknown`. Confirm that every screen says it is a demo scenario, shows retained source-snapshot metadata, and that `changed` and `unknown` contain neutral wording with immediate ordinary transfer.
4. Inspect the transfer screen entered from a push: country is selected, while method, recipient, amount, and debit account are blank/unselected.
5. In Swagger UI, call signal, push, preferences, and transfer contracts. Verify an unsupported corridor and non-positive amount produce understandable validation errors.
6. Review all demo copy against [content-library.md](content-library.md): it must not promise a future result, exact saving, execution rate, or financial advice. Disable colour cues during a visual review and confirm that status remains understandable from text and labels alone.

## Expected result

All transfers and results are labelled simulated; restarting the service clears preferences and simulated transfer records. No real payment or push action occurs.

## Validation record

Validated on 2026-09-03: automated suite passed (27 tests). Manual browser walkthrough confirmed the `changed` scenario, its non-colour status label, immediate ordinary-transfer action, three-method selection, and phone-recipient form. No deviations recorded.
