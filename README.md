# Agent007

## Run

Use the project virtual environment interpreter:

```powershell
.\.venv\Scripts\python.exe .\Agent007\Agent007.py
```

## Data mode switch (.env)

Set in `.env`:

- `DATA_MODE=test` — read JSON fixtures from `Agent007/data`
- `DATA_MODE=live` — live mode placeholder (UI opens with empty lists)

## Telegram bulk clear throttling (.env)

For account menu action "Очистить" (clear all chats), configure delay between dialog deletions:

- `TELEGRAM_CLEAR_DELAY_MIN_SECONDS` (default `0.2`)
- `TELEGRAM_CLEAR_DELAY_MAX_SECONDS` (default `1.5`)
