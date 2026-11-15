# APAA S08-C02-P01 — Controlled Task Execution

Isolated implementation package for the Personal AI Automation Agent. This directory does not alter the existing GitHub write-test files.

## Safety boundary
- No browser, device, network, payment, purchase, deployment, or firewall actions are implemented.
- Only explicitly registered in-process handlers can run.
- Every task requires an explicit permission grant and user consent.
- One task executes at a time per engine instance.
- State transitions are validated and persisted in SQLite.
- Handler exceptions produce a failed task record; the worker continues safely.

## Run
`python -m unittest discover -s apaa-s08-c02-p01/tests -v`

Python 3.11+, standard library only.
