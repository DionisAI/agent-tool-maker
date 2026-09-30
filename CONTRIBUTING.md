# Contributing to ATM

Use Python 3.11+, `python -m pip install -e '.[test,browser-test]'`, then `pytest -q`. Install real local tools for their integration tests. Never put genuine API keys, cookies, private documents or customer records in fixtures.

## Add a finite action

Edit `scripts/build_v02_catalog.py`, retain a primary documentation/maintainer source, and regenerate it. Define one operation, bounded schema, concrete argv or fixed API destination, response acceptance level and explicit side-effect permissions. Use a vault reference rather than a literal token. Model pagination and asynchronous completion explicitly; an HTTP 200 or CLI exit is not business acceptance.

CLI actions run an approved installed program, not arbitrary shell text. Add a contract fixture plus real-program tests where possible. Mark fixture runs and actual vendor validation separately. If a tool requires licensing, approval or a hosted OAuth flow absent from ATM, keep it a clearly labeled handoff and add the actual blocker/acceptance gate to `scripts/build_release_docs.py`.

User-created tools should go through `atm make scaffold / validate / install`, never by editing SQLite. Built-in registry changes are repository code review, not silent runtime plugin discovery. Do not copy third-party GPL/AGPL code into an MIT package merely because its CLI is open source.

## Testing and reporting

Run the full suite and inspect failure paths, permissions, schema errors, request reuse, unknown submissions and file validation. Update `docs/TEST_REPORT.md` from actual reports; do not reuse an old passing test total after modifications. Generate the 66-item coverage map and ensure each research item has explicit implemented scope and remaining work.

`python scripts/run_validation.py` produces machine-readable reports when `pytest-json-report` is installed. CI config is supplied but is not evidence of an online run. A release should contain source, tests, locally built wheel, checksums, roadmap and test limitations. Do not publish, spend from a user account, merge PRs, or alter production while validating a contribution unless separately authorized.
