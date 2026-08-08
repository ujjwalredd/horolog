# Horolog API Service

Python 3.12+ backend API and continuous scheduling engine for [Horolog](https://github.com/ujjwalredd/horolog).

## Overview

The `horolog` package provides:
- **Solver Engine** (`horolog.solver`): High-performance greedy first-fit placement with Minimal Perturbation Placement (MPP) stability guarantees.
- **Structured LLM Extraction** (`horolog.llm`, `horolog.capture`): Grammar-constrained decoding over local (Ollama/vLLM) or remote (Anthropic/OpenAI) language models.
- **Calendar Synchronization** (`horolog.providers`): Dynamic expansion for published `.ics` feeds and live CalDAV servers.
- **FastAPI HTTP & SSE Stream** (`horolog.api`): REST endpoints and real-time Server-Sent Events broadcasting.

## Development

```bash
uv venv --python 3.12
uv pip install -e ".[dev]"
pytest -q
```
