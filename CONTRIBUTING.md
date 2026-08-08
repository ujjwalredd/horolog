# Contributing to Horolog

Thank you for your interest in contributing to Horolog! Horolog is an open-source, self-hosted AI calendar engine that defends user focus time. We welcome contributions of all kinds, including bug fixes, feature proposals, documentation improvements, and performance enhancements.

---

## 📜 Principles & Core Constraints

Before making changes, please keep our core invariants in mind:

1. **The placement engine (`services/api/horolog/solver/`) is the core product.**
   - Everything else (HTTP endpoints, database, LLM capture, frontend UI) is I/O built around it.
   - The engine operates purely on **15-minute integer slots** relative to a horizon origin. It must remain free of I/O, datetimes, and timezone logic.
2. **Stability & Bounded Churn (Minimal Perturbation Placement)**:
   - When a new meeting or event lands in a schedule, Horolog **only moves blocks that collided**. Re-planning must never cause a cascading shift of unaffected tasks across the week.
   - The property tests in [`services/api/tests/test_solver.py`](services/api/tests/test_solver.py) pin these invariants. All property tests must pass on every PR.
3. **Honest Shortfall**:
   - Time that does not fit is reported in `unmet`, never dropped silently.
4. **Local-First & Privacy Preserving**:
   - Zero telemetry. Nothing leaves the host machine unless explicitly configured by the user (e.g. cloud LLM providers).

---

## 🛠️ Development Setup

### Requirements
- **Python**: 3.12+
- **Node.js**: 20+
- **`uv`**: Recommended Python package manager (`curl -LsSf https://astral.sh/uv/install.sh | sh`)

### Initial Setup

```bash
# Clone the repository
git clone https://github.com/ujjwalredd/horolog.git
cd horolog

# Initialize Python virtual environment & dependencies
cd services/api && uv venv --python 3.12 && uv pip install -e ".[dev]" && cd -

# Initialize Web frontend dependencies
cd apps/web && npm install && cd -

# Copy example environment configuration
cp .env.example .env
```

### Running Locally

To launch both the API backend and Next.js frontend together with dynamic free-port selection:

```bash
npm run dev
```

```
  Horolog
  api  http://localhost:8001
  web  http://localhost:3000
```

---

## 🧪 Testing & Verification

Run the full automated check suite before submitting a pull request:

```bash
# Run full suite (Ruff linting, Ruff formatting check, Mypy strict, Pytest, TypeScript & Next.js build)
npm run check

# Run Python API tests only
npm test

# Run solver benchmark
npm run bench
```

### Benchmarking Rule for Placement Engine Edits
If you touch anything in `services/api/horolog/solver/`, you **must** run `npm run bench` before and after your changes and include the benchmark output table in your Pull Request description.

Example benchmark output:
```
horizon 2016 slots (21 days), 9:00-18:00 workday
demand held at 85% of open capacity | 7 runs each

 intents   reqs   load  blocks  cold p50  cold p95  warm p50  warm p95  unmet  churn
      30     70   84%     107      3.8ms     4.6ms     3.0ms     5.3ms      5      0
     100    232   86%     224     13.6ms    14.8ms     8.9ms    16.9ms      8      0
     300    700  185%     335     59.6ms    92.2ms    54.2ms    64.2ms    365      0
```

---

## 📥 Submitting a Pull Request

1. **Fork the repository** and create a feature branch (`git checkout -b feature/my-feature`).
2. Keep commits concise and descriptive.
3. Ensure `npm run check` passes cleanly.
4. Open a Pull Request against the `main` branch. Describe the motivation for the change and include any relevant benchmark numbers or screenshots.

---

## 📄 License

By contributing to Horolog, you agree that your contributions will be licensed under the project's [AGPL-3.0 License](LICENSE).
