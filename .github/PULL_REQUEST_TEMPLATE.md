## Description

Provide a summary of the changes introduced by this PR and the rationale behind them.

- Fixes #(issue)
- Feature / Enhancement / Bug Fix / Refactor

## Scope of Changes

- [ ] Solver / Engine (`services/api/horolog/solver/`)
- [ ] Domain models / Database (`services/api/horolog/domain/`, `db.py`)
- [ ] Calendar Sync / LLM Providers (`providers.py`, `llm.py`, `capture.py`)
- [ ] API endpoints (`api.py`)
- [ ] Frontend Web App (`apps/web/`)
- [ ] Documentation / CI / Infra

## Placement Engine Benchmark (Required if `solver/` modified)

If this PR modifies `services/api/horolog/solver/`, attach the output of `npm run bench` before and after your changes:

```
# Paste benchmark results here
```

## Checklist

- [ ] `npm run check` passes without errors (lint, format, types, pytest, Next.js build)
- [ ] Added or updated tests covering the new functionality
- [ ] Updated documentation (`README.md`, `ARCHITECTURE.md`, `.env.example`) if relevant
