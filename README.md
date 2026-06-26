# ⚡ NSE Quant Swing Scanner

A **production-grade, 100% free, mobile-first** quantitative swing trading system for the Indian NSE/BSE market. Built to run entirely from an Android phone.

## Strategy: ATR-Volume Demand Pullback

| Condition | Rule |
|-----------|------|
| Universe | Nifty 200 stocks |
| Trend | Close > 200 SMA AND 20 EMA > 50 EMA |
| Pullback | Intraday low touches 20 EMA or 50 EMA (within 0.5%) |
| Trigger | Bullish candle closing in upper 50% of day's range |
| Volume | Trigger candle volume > 1.5x 20-day average |
| Stop Loss | Low of trigger candle − (1.5 × ATR₁₄) |
| Target | Entry + (2 × Risk) — minimum 1:2 RRR |
| Time Stop | Exit at close if trade not resolved within 10 trading days |

## Tech Stack (100% Free Tier)

| Layer | Technology |
|-------|------------|
| Compute | GitHub Actions (cron job) |
| Language | Python 3.11 |
| Data | yfinance |
| Math | Native Pandas + NumPy (Wilder's Smoothing) |
| Database | Firebase Cloud Firestore |
| Frontend | React 18 + Vite + Tailwind CSS |
| Hosting | Vercel |
| Notifications | ntfy.sh |

## Architecture

```
GitHub Actions (4:15 PM IST daily)
    │
    ├── update_active_trades() — checks SL/Target/Time-Stop for open positions
    └── scan_market()          — scans Nifty 200 for new entry signals
            │
            ├── Firebase Firestore ───► React Dashboard (Vercel PWA)
            └── ntfy.sh ───────────► Android Push Notification
```

## Deployment (Android Phone Only)

### Step 1: Firebase Setup
1. Go to [console.firebase.google.com](https://console.firebase.google.com)
2. Create project → Add Web App → Copy config values
3. Project Settings → Service Accounts → **Generate new private key** (download JSON)
4. Firestore Database → Create database (Test mode)
5. Firestore Rules → Paste and publish:
```javascript
rules_version = '2';
service cloud.firestore {
  match /databases/{database}/documents {
    match /signals/{document} {
      allow read: if true;
      allow write: if false;
    }
  }
}
```

### Step 2: GitHub Secrets
1. Go to this repo → Settings → Secrets and variables → Actions
2. Add secret `FIREBASE_CONFIG` → paste entire JSON from Step 1
3. Add secret `NTFY_TOPIC` → set a unique string (e.g. `my_nse_alerts_xyz99`)

### Step 3: ntfy.sh Notifications
1. Install **ntfy** app from Play Store
2. Subscribe to your exact topic string from Step 2

### Step 4: Vercel Frontend Deploy
1. Go to [vercel.com](https://vercel.com) → New Project → Import this GitHub repo
2. Add Environment Variables (from Firebase Web App config):
   - `VITE_FIREBASE_API_KEY`
   - `VITE_FIREBASE_AUTH_DOMAIN`
   - `VITE_FIREBASE_PROJECT_ID`
   - `VITE_FIREBASE_STORAGE_BUCKET`
   - `VITE_FIREBASE_MESSAGING_SENDER_ID`
   - `VITE_FIREBASE_APP_ID`
3. Deploy → open URL in Chrome → **Add to Home Screen** (PWA)

### Step 5: First Run
1. Go to Actions tab → Daily NSE Scanner → **Run workflow**
2. Check logs for any errors
3. Open your Vercel URL to see signals

## Audit History

This codebase passed **4 independent audit passes** resolving 20 bugs:

| Pass | Key Findings |
|------|--------------|
| Pass 1 | yfinance MultiIndex crash, pandas_ta column mismatch, missing deduplication |
| Pass 2 | pandas_ta + pandas 2.x incompatibility (silent crash), stale yfinance pin |
| Pass 3 | RSI/ATR used standard EWM not Wilder's smoothing (wrong SL prices) |
| Pass 4 | NSE holidays outdated (2025 not 2026), stale candle guard missing, cron timing |

## Annual Maintenance

> **Every January:** Update `NSE_HOLIDAYS` in `scanner.py` with the official NSE holiday list for the new year. Verify at [nseindia.com/holiday-calendar](https://www.nseindia.com/holiday-calendar).

## License

MIT — Free to use, modify, and deploy.
