# scripts/

One-off operational and developer scripts. Things that are useful but don't belong in the application code.

Empty in tranche 1. Likely future contents:

- `seed-sandbox-tenant.py` — create a sandbox tenant with a supervisor PIN for local dev
- `import-from-smart-care.py` — Phase 10 ETL from the smart-care-ai database
- `import-from-nexusltc.py` — Phase 10 ETL from the NexusLTC database
- `phi-scrub-fixtures.py` — anonymize a snapshot of real data for tests

## Convention

- Python scripts are runnable via `uv run python scripts/<name>.py` so they pick up the project venv.
- Each script has a docstring at the top describing what it does, what inputs it needs, and what side effects it has.
- Destructive scripts require an explicit `--yes-really` flag.
