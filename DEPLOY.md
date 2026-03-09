# Romanian Bot – Deploy & Troubleshooting

## Quick start (local)

1. Copy `.env.example` to `.env` and fill in:
   - `TELEGRAM_BOT_TOKEN` – from [@BotFather](https://t.me/BotFather)
   - `ANTHROPIC_API_KEY` – from [console.anthropic.com](https://console.anthropic.com)

2. Run:
   ```bash
   pip install -r requirements.txt
   python bot.py
   ```

## Deploy to Railway

### One-time setup

1. **Create Railway project** and add a new service from this repo.

2. **Set environment variables** in Railway:
   - `TELEGRAM_BOT_TOKEN`
   - `ANTHROPIC_API_KEY`
   - Optional: `TIMEZONE` (default: America/Chicago), `ANTHROPIC_MODEL` (default: claude-opus-4-6)

3. **Enable GitHub auto-deploy** (recommended):
   - Add these secrets to your GitHub repo (Settings → Secrets and variables → Actions):
     - `RAILWAY_TOKEN` – from Railway → Project → Settings → Tokens → Create Token
     - `RAILWAY_SERVICE_ID` – from Railway → press ⌘K → Copy Service ID
   - Every push to `main` will deploy via `.github/workflows/deploy-railway.yml`

### Manual deploy (if no GitHub integration)

```bash
railway login
railway link   # link to your project
railway up
```

## Troubleshooting

| Symptom | Fix |
|--------|-----|
| "Sorry, something went wrong" | Check Railway logs for the real error. Often: missing `ANTHROPIC_API_KEY` or invalid model. Set `ANTHROPIC_MODEL=claude-opus-4-6` if unsure. |
| "Translation service temporarily unavailable" | Anthropic API rate limit or outage. Bot retries 3× with backoff. Wait and try again. |
| Weekly report never arrives | User must send `/start` or `/weekly` at least once so the bot knows where to send. Reports run Friday 8am (your `TIMEZONE`). |
| Deploy doesn’t update | If using GitHub Actions: ensure `RAILWAY_TOKEN` and `RAILWAY_SERVICE_ID` are set. Otherwise run `railway up` manually. |
| No response at all | Bot deletes webhook on startup (webhook blocks polling). Try `/ping` – if you get "Pong!", the bot is running. |

## Resilience (why it shouldn't stop)

- **Model fallback**: If Opus fails (deprecated, 404), tries `claude-opus-4-5-20251101` then `claude-3-5-sonnet-latest`
- **Non-blocking**: Translations run in a thread pool so the bot stays responsive
- **Database**: DB errors are caught; handlers return empty data instead of crashing
- **Weekly report**: Scheduled job catches all errors and logs; bot keeps running
- **Error handler**: Never raises; bot process stays up
- **DB path fallback**: If default path fails (e.g. read-only), uses `/tmp` (data won't persist)

## Files

- `bot.py` – main bot logic
- `translator.py` – Anthropic API calls (translate, Q&A, weekly report)
- `scheduler.py` – weekly report logic (scheduling via bot’s JobQueue)
- `database.py` – SQLite storage
- `config.py` – env vars, loads `.env` locally
