# Intraday Sathi — NSE Intraday AI Paper-Trading Assistant

**Paper trading only. No real orders, ever.** Data comes from free Yahoo Finance feeds and is delayed (~15 min) and
sometimes missing. AI models are statistical, trained on ~60 days of data for a few large stocks, and can be wrong.
No accuracy or profit is guaranteed. Not investment advice.

## Folder structure
```
.devcontainer/devcontainer.json        Codespaces setup (Python 3.11, port 8000)
.github/workflows/build-apk.yml        Builds the APK and publishes it to Releases
backend/                               FastAPI + XGBoost
  run.sh  requirements.txt  .env.example
  app/ config.py db.py universe.py data.py indicators.py ml.py paper.py auto.py analytics.py news.py main.py
  tests/ conftest.py test_core.py test_api.py
android/                               Kotlin + Jetpack Compose (Material 3)
  settings.gradle.kts build.gradle.kts gradle.properties
  app/build.gradle.kts
  app/src/main/AndroidManifest.xml, res/values/{strings,themes}.xml
  app/src/main/java/com/intradaysathi/app/ MainActivity Theme Api Json AppVm Screens .kt
  app/src/test/.../JsonTest.kt
```

## Setup from an Android phone only (use Chrome, "Desktop site" ON helps)
1. **GitHub**: sign in at github.com → New repository → name `intraday-sathi` → Create.
2. Open the repo → press `.` (or change `github.com` to `github.dev` in the address) to open the web editor.
   In the Explorer, tap **⋯ → Upload...** and upload `IntradaySathi.zip`. Open the terminal (Terminal menu →
   New Terminal; if unavailable use step 3 first) and run:
   ```
   unzip IntradaySathi.zip && cp -r IntradaySathi/. . && rm -rf IntradaySathi IntradaySathi.zip
   git add -A && git commit -m "Intraday Sathi" && git push origin HEAD:main
   ```
3. **Backend**: on the repo page tap **Code → Codespaces → Create codespace on main**. In its terminal:
   ```
   bash backend/run.sh
   ```
   After ~15 s it prints `BACKEND URL: https://<name>-8000.app.github.dev/`. If it doesn't become public,
   run `gh codespace ports visibility 8000:public -c $CODESPACE_NAME`. Keep the Codespace running
   (it sleeps after inactivity; the free tier has monthly hour limits).
4. **APK**: pushing to `main` triggers **Actions → Build Android APK** (≈5-10 min). When green, open the repo's
   **Releases → Intraday Sathi APK (latest)** on your phone, download `IntradaySathi.apk`, and install it
   (allow "install unknown apps" for your browser).
5. Open the app → ⚙ Settings → paste the backend URL → Save.
6. **AI tab → Train 5m** (1-3 minutes), then Train 15m. Until trained, signals are simple rule-based fallbacks.

## Run tests (in the Codespace terminal)
```
cd backend && python -m pytest -q
```

## Using it
- **Home**: market overview, watchlist signals. **Stocks**: search → chart, signal, paper order, fundamentals, news, NSE announcements.
- **Portfolio**: virtual ₹1,00,000, positions, P&L. **Auto**: start/pause/resume/stop/emergency stop, daily loss limit, max trades.
- **AI**: win rate, profit factor, drawdown, daily/weekly/monthly P&L, model versions, train/retrain/rollback.
- Automation runs inside the backend (so keep the Codespace awake). Entries 09:20-15:00 IST on weekdays, only with a trained model; all positions squared off at 15:15 IST.

## Known limitations
- Data: Yahoo Finance, delayed, rate-limited, occasionally empty. NSE announcements often block cloud IPs → shown as "unavailable".
- Sentiment is a keyword lexicon, not a language model. Fundamentals may have gaps (listed as n/a).
- Paper fills use the last delayed price with no slippage/brokerage; shorts block full notional as margin.
- Retraining blends outcomes of completed AI paper trades (weighted) with fresh candle data and only activates a model that is not worse than the current one; use Rollback to revert.
- Debug APK, cleartext HTTP allowed so a local backend URL works.

## Troubleshooting
- In the app: ⚙ Settings → **Test connection**. It shows exactly what the backend returned.
- "Backend did not return JSON ... Received: ..." means something other than the API answered
  (sleeping Codespace, private port, or a GitHub sign-in/warning page). Restart `bash backend/run.sh`,
  make port 8000 Public, and test `<url>/health` in the phone browser.
- If installing a new APK says "App not installed", uninstall the old app first (debug builds are signed with a new key on each GitHub build).
