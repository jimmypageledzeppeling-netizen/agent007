# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project status

Step 1 (environment) is complete and verified; steps 2 (Tkinter UI) and 3 (users/auth) are untouched. What exists: venv, pinned dependencies, linters, config, logging, health checks, tests, a running MySQL + Kafka pair from `docker-compose.yml`, and a git repository. What does not: any UI, database schema, Telegram integration, or CI/CD.

`.env` still carries the `change-me` placeholder passwords, and the MySQL container was initialized with them — changing them means `docker compose down -v` (data loss). Telegram API credentials are deliberately absent until account work starts.

## Specification files (source of truth)

The spec lives in `Agent007/.claude/` and is written in Russian. Read it before starting work:

- `Promt.md` — project description and the standing engineering requirements. Applies to all work.
- `step1.md`, `step2.md`, `step3.md` — implementation steps, executed in order.

Each step file carries a `# Status: incomplete` marker at the bottom. **Update that marker to `complete` when a step is finished** — it is how progress is tracked across sessions. (`step2.md` is currently missing its marker; add one when you touch it.)

Current step state: step1 `complete` (with a "Что сделано / Осталось" checklist), step2 unmarked, step3 incomplete.

## Target architecture (per spec)

Full-screen desktop application for managing multiple Telegram accounts: Telegram API connection, chat/message management, task automation, media sending, notification and filter configuration, and activity analytics.

| Concern | Choice |
|---|---|
| Language | Python |
| UI | Tkinter |
| Database | MySQL |
| Task queue | Kafka |
| Packaging | virtualenv + Docker |

### UI structure rules (from `step2.md`)

These are explicit spec constraints, not suggestions:

- One file per UI element — each window, panel, and button is its own module, pluggable into the main app.
- One class per window/panel, owning that element's behavior and its interaction with the rest of the app.
- Group modules by functional block (accounts, chats, messages).

### Auth model (from `step3.md`)

Superuser/admin account creates users, assigns roles and permissions; the app has its own authentication and authorization layer on top of that.

## Engineering requirements (from `Promt.md`)

- SOLID, DRY, KISS, YAGNI; use design patterns where they earn their place.
- PEP8; static analysis via **pylint** and **flake8**.
- Async and multithreaded where the workload calls for it.
- **Error logging goes to a separate file under `./Log/`.**
- Every change is run through tests before it is considered done; unit tests are part of the change, not a follow-up.
- Code comments and documentation accompany the code.
- Monitoring/alerting for application health; CI/CD pipeline.

## Visual Studio project layout

The solution is `Agent007.slnx` (Visual Studio, Python Tools) → `Agent007/Agent007.pyproj`, startup file `Agent007.py`. `<Build Project="false" />` — the solution does not build; it is a file container and debug launcher only.

**New `.py` files must be added to the `<ItemGroup>` in `Agent007.pyproj` as `<Compile Include="..." />`**, otherwise they will not show up in the Visual Studio solution explorer even though Python imports them fine.

## Layout

```
Agent007/app/       application package (config, logging_config, health)
Agent007/scripts/   operational scripts (check_env.py)
Agent007/tests/     pytest suite
Agent007/Agent007.py  entry point (VS <StartupFile>)
Log/                app.log + errors.log, git-ignored
```

`pyproject.toml` puts `Agent007/` on `pythonpath`, so modules import as `app.config`, not `Agent007.app.config`.

## Commands

All commands run from the repository root with the venv interpreter.

```powershell
.venv\Scripts\python.exe -m pytest                          # full suite
.venv\Scripts\python.exe -m pytest -m integration            # needs docker compose up -d
.venv\Scripts\python.exe -m pytest Agent007\tests\test_config.py::test_get_settings_is_cached
.venv\Scripts\python.exe -m flake8 Agent007
.venv\Scripts\python.exe -m pylint Agent007\app Agent007\scripts Agent007\tests Agent007\Agent007.py
.venv\Scripts\python.exe Agent007\scripts\check_env.py       # MySQL/Kafka/Telegram connectivity
.venv\Scripts\python.exe Agent007\Agent007.py                # run the app

docker compose up -d      # MySQL 8.4 + Kafka 3.9 (KRaft)
docker compose down       # add -v to drop data volumes
```

MySQL is published on host port **3307**, not 3306 — the Windows `MySQL80` service already owns 3306 on this machine. Kafka advertises `localhost:9092`; the bind hosts in `docker-compose.yml` must stay empty (`PLAINTEXT://:9092`), because the image would otherwise copy `0.0.0.0` into `advertised.listeners` and the broker refuses to start.

Both linters are expected to stay clean (pylint at 10.00/10); every suppression in the code carries a comment explaining why.

Tests marked `integration` are auto-skipped unless `-m integration` is passed — see `pytest_collection_modifyitems` in `Agent007/tests/conftest.py`.

## Conventions established in step 1

- **Configuration**: only `app/config.py` reads the environment. Everything else takes a `Settings` instance; secrets are `SecretStr` so they stay out of logs and reprs. `get_settings()` is `lru_cache`d.
- **Logging**: never call `logging.basicConfig`. Use `app.logging_config.get_logger(__name__)`, or `setup_logging()` once at an entry point. `Log/errors.log` must keep receiving ERROR+ only — this is a spec requirement with a test guarding it.
- **Health checks** return a `CheckResult` rather than raising, so one dead dependency does not mask the others.
- `Settings.model_copy(update=...)` skips validation — a plain `str` will not be coerced to `SecretStr`. Build a fresh `Settings(...)` in tests instead.
