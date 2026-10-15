# MODASR ECOSYSTEM (English summary)

A multi-messenger AI assistant (Telegram, Bale, and Rubika — present in code but
**intentionally not enabled by default**, pending final confirmation) sharing one
OpenRouter-based AI core, plus a web admin panel.

The Persian [`README.md`](README.md) is the primary, most up-to-date document. This file
is a shorter English companion for contributors who don't read Persian; when the two
disagree, trust `README.md` and `docs/TEST_REPORT.md`.

## Architecture
- `packages/core/` — shared config loader, SQLite database (versioned migrations), the
  `PlatformAdapter` interface, and `ai/openrouter.py` (the active AI client).
- `apps/telegram-bot/`, `apps/bale-bot/`, `apps/rubika-bot/` — one adapter + polling
  loop per platform, all built on the same shared `PlatformAdapter` and OpenRouter client.
- `apps/web-panel/` — a small JSON API server using only Python's standard library
  (no Flask/FastAPI) plus a static, no-build-step HTML/CSS/JS frontend (RTL, Persian).
- `infra/` — systemd unit files and an Ubuntu install script.
- `scripts/` — service control, backup/restore, live connectivity test scripts, and a
  pre-publish secret scanner.
- `tests/` — a `unittest`-based suite covering all of the above (no `pytest` dependency).

## Quick start
```bash
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# fill in OPENROUTER_API_KEY and at least one of BOT_TOKEN / BALE_BOT_TOKEN
python3 -m unittest discover -s tests -p "test_*.py" -v
python3 apps/telegram-bot/main.py
```

## Honesty notes (please read before trusting any claim in this repo)
- Every "tested" claim in `docs/TEST_REPORT.md` specifies whether it was a **mocked**
  unit/integration test or a **live** test against a real API — these are never conflated.
- Rubika's adapter talks to `botapi.rubika.ir` using a bot token (not a personal-account
  login), which looks like an official bot platform rather than the unofficial
  personal-account API considered earlier in this project's history — but this has not
  been independently verified against Rubika's own documentation in this environment.
  It stays out of the default systemd service list until explicitly confirmed.
- The VPS install script and systemd units were syntax-verified (`systemd-analyze verify`,
  `bash -n`) and the backup/restore scripts were functionally tested end-to-end, but a
  full install on a real fresh Ubuntu VPS has not been performed by the assistant.

See `docs/` for full details.
