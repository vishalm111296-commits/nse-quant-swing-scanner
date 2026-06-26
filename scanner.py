import os
import json
import yfinance as yf
import pandas as pd
import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime
import requests
import pytz
import numpy as np

# --- INITIALIZATION & CONFIG ---
# Load Firebase service account JSON from GitHub Secrets
firebase_creds_str = os.environ.get("FIREBASE_CONFIG")
if not firebase_creds_str:
    raise ValueError("FIREBASE_CONFIG environment variable is missing.")

# Parse JSON string to dictionary and initialize Firebase Admin SDK
cred_dict = json.loads(firebase_creds_str)
cred = credentials.Certificate(cred_dict)
firebase_admin.initialize_app(cred)
db = firestore.client()

# Initialize push notification topic and IST timezone
NTFY_TOPIC = os.environ.get("NTFY_TOPIC", "your_unique_nse_signals_topic")
IST = pytz.timezone('Asia/Kolkata')

# Define NSE trading holidays for 2026 (update annually every January)
NSE_HOLIDAYS = [
    '2026-01-26', '2026-03-25', '2026-04-02', '2026-04-03',
    '2026-04-14', '2026-05-01', '2026-08-15', '2026-10-02',
    '2026-10-20', '2026-10-21', '2026-11-05', '2026-12-25'
]
HOLIDAY_CAL = np.busdaycalendar(holidays=NSE_HOLIDAYS)


# --- UTILITY FUNCTIONS ---
# Send push notifications to mobile phone via ntfy.sh
def send_notification(title, message):
    try:
        requests.post(
            f"https://ntfy.sh/{NTFY_TOPIC}",
            data=message.encode('utf-8'),
            headers={"Title": title},
            timeout=10
        )
    except Exception as e:
        print(f"Notification failed: {e}")


# Calculate RSI using Wilder's exact smoothing (com=period-1, min_periods=period)
# This matches TradingView and Zerodha Kite — NOT standard EWM
def compute_rsi_wilder(close, period=14):
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = (-delta.clip(upper=0))
    avg_gain = gain.ewm(com=period - 1, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(com=period - 1, min_periods=period, adjust=False).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


# Download lightweight OHLCV data without indicators (used only for trade management)
def download_ohlc(ticker, period="1mo"):
    df = yf.download(ticker, period=period, interval="1d", progress=False, auto_adjust=True)
    if df.empty:
        return df
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df.columns = [c.lower() for c in df.columns]
    return df


# Download full 1Y OHLCV data and compute all technical indicators (used for scanning)
def download_and_prep(ticker, period="1y"):
    df = yf.download(ticker, period=period, interval="1d", progress=False, auto_adjust=True)
    if df.empty:
        return df
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df.columns = [c.lower() for c in df.columns]

    # Compute Moving Averages
    df['EMA_20'] = df['close'].ewm(span=20, adjust=False).mean()
    df['EMA_50'] = df['close'].ewm(span=50, adjust=False).mean()
    df['SMA_200'] = df['close'].rolling(200).mean()
    df['avg_vol_20'] = df['volume'].rolling(20).mean()

    # Compute Wilder's RSI (matches TradingView/Kite exactly)
    df['RSI_14'] = compute_rsi_wilder(df['close'], 14)

    # Compute Wilder's ATR — com=13 means alpha=1/14, not standard EWM
    hl = df['high'] - df['low']
    hc = (df['high'] - df['close'].shift()).abs()
    lc = (df['low'] - df['close'].shift()).abs()
    tr = pd.concat([hl, hc, lc], axis=1).max(axis=1)
    df['ATRr_14'] = tr.ewm(com=13, min_periods=14, adjust=False).mean()

    return df


# --- NIFTY 200 UNIVERSE ---
# Full Nifty 200 constituent list with .NS suffix for Yahoo Finance
NIFTY_200 = [
    "RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "INFY.NS", "ICICIBANK.NS",
    "HINDUNILVR.NS", "SBIN.NS", "BHARTIARTL.NS", "ITC.NS", "KOTAKBANK.NS",
    "LT.NS", "AXISBANK.NS", "ASIANPAINT.NS", "MARUTI.NS", "SUNPHARMA.NS",
    "TITAN.NS", "BAJFINANCE.NS", "NESTLEIND.NS", "WIPRO.NS", "ULTRACEMCO.NS",
    "ONGC.NS", "NTPC.NS", "POWERGRID.NS", "TECHM.NS", "HCLTECH.NS",
    "BAJAJFINSV.NS", "GRASIM.NS", "ADANIENT.NS", "JSWSTEEL.NS", "TATASTEEL.NS",
    "COALINDIA.NS", "INDUSINDBK.NS", "CIPLA.NS", "DRREDDY.NS", "DIVISLAB.NS",
    "BRITANNIA.NS", "EICHERMOT.NS", "HEROMOTOCO.NS", "BAJAJ-AUTO.NS", "TATACONSUM.NS",
    "APOLLOHOSP.NS", "ADANIPORTS.NS", "HINDALCO.NS", "VEDL.NS", "BPCL.NS",
    "IOC.NS", "HDFCLIFE.NS", "SBILIFE.NS", "ICICIPRULI.NS", "PIDILITIND.NS",
    "DABUR.NS", "MARICO.NS", "GODREJCP.NS", "COLPAL.NS", "BERGEPAINT.NS",
    "HAVELLS.NS", "VOLTAS.NS", "WHIRLPOOL.NS", "SIEMENS.NS", "ABB.NS",
    "BOSCHLTD.NS", "CUMMINSIND.NS", "THERMAX.NS", "MCDOWELL-N.NS", "UBL.NS",
    "MUTHOOTFIN.NS", "CHOLAFIN.NS", "SHRIRAMFIN.NS", "BAJAJHLDNG.NS", "M&M.NS",
    "TATAPOWER.NS", "ADANIGREEN.NS", "ADANITRANS.NS", "TORNTPOWER.NS", "CESC.NS",
    "ZYDUSLIFE.NS", "LUPIN.NS", "AUROPHARMA.NS", "BIOCON.NS", "ALKEM.NS",
    "TORNTPHARM.NS", "GLAXO.NS", "PFIZER.NS", "ABBOTINDIA.NS", "SANOFI.NS",
    "DMART.NS", "TRENT.NS", "NYKAA.NS", "ZOMATO.NS", "PAYTM.NS",
    "NAUKRI.NS", "INDIGRID.NS", "INDIGO.NS", "SPICEJET.NS", "IRCTC.NS",
    "DLF.NS", "GODREJPROP.NS", "OBEROIRLTY.NS", "PRESTIGE.NS", "SOBHA.NS",
    "BANKBARODA.NS", "PNB.NS", "CANBK.NS", "UNIONBANK.NS", "IDFCFIRSTB.NS",
    "FEDERALBNK.NS", "BANDHANBNK.NS", "RBLBANK.NS", "KARURVYSYA.NS", "SOUTHBANK.NS",
    "MRF.NS", "APOLLOTYRE.NS", "CEATLTD.NS", "BALKRISIND.NS", "JKTYRE.NS",
    "TATACHEM.NS", "PIDILITIND.NS", "AARTIIND.NS", "DEEPAKNTR.NS", "NAVINFLUOR.NS",
    "SRF.NS", "ATUL.NS", "FINEORG.NS", "GALAXYSURF.NS", "VINATIORGA.NS",
    "PAGEIND.NS", "MANYAVAR.NS", "TTKPRESTIG.NS", "VGUARD.NS", "SYMPHONY.NS",
    "POLYCAB.NS", "KEI.NS", "FINOLEX.NS", "SUPRAJIT.NS", "VARROC.NS",
    "MOTHERSON.NS", "MINDAIND.NS", "ENDURANCE.NS", "CRAFTSMAN.NS", "RAMKRISHNA.NS",
    "HINDZINC.NS", "NMDC.NS", "SAIL.NS", "JINDALSTEL.NS", "RATNAMANI.NS",
    "APLAPOLLO.NS", "WELCORP.NS", "GMRINFRA.NS", "IRB.NS", "KNRCON.NS",
    "NCC.NS", "PNCINFRA.NS", "HGINFRA.NS", "GPPL.NS", "CONCOR.NS",
    "ASTRAL.NS", "SUPREMEIND.NS", "PRINCEPIPE.NS", "FINOLEX.NS", "NILKAMAL.NS",
    "ZEEL.NS", "SUNTV.NS", "PVRINOX.NS", "NAZARA.NS", "NETWORK18.NS",
    "MFSL.NS", "CANFINHOME.NS", "GRUH.NS", "REPCO.NS", "AAVAS.NS",
    "LTTS.NS", "PERSISTENT.NS", "COFORGE.NS", "MPHASIS.NS", "KPITTECH.NS",
    "TATAELXSI.NS", "HEXAWARE.NS", "NIITTECH.NS", "RATEGAIN.NS", "HAPPSTMNDS.NS",
    "GLAND.NS", "LALPATHLAB.NS", "METROPOLIS.NS", "THYROCARE.NS", "KRSNAA.NS",
    "IPCALAB.NS", "NATCOPHARM.NS", "GRANULES.NS", "SUVEN.NS", "LAURUSLABS.NS",
    "ALKYLAMINE.NS", "BALRAMCHIN.NS", "DHAMPUR.NS", "TRIVENI.NS", "EID.NS",
    "CHAMBLFERT.NS", "COROMANDEL.NS", "GNFC.NS", "GSFC.NS", "PARADEEP.NS",
    "TATACOMM.NS", "ROUTE.NS", "TANLA.NS", "MAHINDCIE.NS", "SCHAEFFLER.NS",
    "SKFINDIA.NS", "TIMKEN.NS", "GRINDWELL.NS", "CARBORUNIV.NS", "PFCLTD.NS",
    "RECLTD.NS", "IRFC.NS", "HUDCO.NS", "NABARD.NS", "CREDITACC.NS"
]


# --- TRADE MANAGEMENT ---
# Check all active trades against latest OHLC for SL hit, Target hit, or 10-day Time Stop
def update_active_trades():
    print("Checking active trades...")
    active_docs = db.collection("signals").where("status", "==", "ACTIVE").stream()
    today = datetime.now(IST).date()

    for doc in active_docs:
        sig = doc.to_dict()
        ticker = sig["ticker"]

        # Use lightweight OHLC download (no indicator computation needed here)
        df = download_ohlc(ticker, period="1mo")
        if len(df) < 1:
            continue

        latest = df.iloc[-1]
        new_status = "ACTIVE"
        exit_price = None

        # Log if Yahoo Finance hasn't published today's candle yet
        latest_date = df.index[-1].date()
        if latest_date != today:
            print(f"INFO: {ticker} using previous candle {latest_date} (today's not yet available).")

        low = float(latest['low'])
        high = float(latest['high'])
        close = float(latest['close'])

        # Check Stop Loss hit (intraday low touched SL price)
        if low <= sig['stop_loss']:
            exit_price = sig['stop_loss']
            new_status = "LOSS"
        # Check Target hit (intraday high reached target price)
        elif high >= sig['target']:
            exit_price = sig['target']
            new_status = "WIN"
        # Check 10-trading-day Time Stop using NSE holiday calendar
        else:
            try:
                entry_date = datetime.strptime(sig['date'], "%Y-%m-%d").date()
                trading_days = int(np.busday_count(entry_date, today, busdaycal=HOLIDAY_CAL))
                if trading_days >= 10:
                    exit_price = close
                    new_status = "TIME_EXIT"
            except Exception as e:
                print(f"Date parsing error for {ticker}: {e}")

        # If trade closed, update Firestore record and send push notification
        if new_status != "ACTIVE":
            pnl = ((exit_price - sig['entry']) / sig['entry']) * 100
            db.collection("signals").document(doc.id).update({
                "status": new_status,
                "exit_price": float(exit_price),
                "pnl_percentage": round(float(pnl), 4)
            })
            send_notification(
                f"Trade Closed: {new_status}",
                f"{ticker} exited at \u20b9{exit_price:.2f}. PnL: {pnl:.2f}%"
            )


# --- MARKET SCANNING ---
# Scan Nifty 200 for new ATR-Volume Demand Pullback strategy entries
def scan_market():
    print("Scanning for new signals...")
    today_str = datetime.now(IST).strftime("%Y-%m-%d")
    today = datetime.now(IST).date()

    for symbol in NIFTY_200:
        try:
            # Deduplication: skip symbol if an active trade already exists
            existing = db.collection("signals")\
                .where("ticker", "==", symbol)\
                .where("status", "==", "ACTIVE")\
                .limit(1).stream()
            if any(True for _ in existing):
                continue

            # Download full year of data with all indicators computed
            df = download_and_prep(symbol, period="1y")
            if len(df) < 200:
                continue

            latest = df.iloc[-1]

            # Strict date guard: skip if Yahoo Finance returned stale data
            latest_date = df.index[-1].date()
            if latest_date != today:
                print(f"WARNING: {symbol} stale candle ({latest_date}), skipping.")
                continue

            # Extract scalar values from the latest candle row
            close = float(latest['close'])
            open_ = float(latest['open'])
            high = float(latest['high'])
            low = float(latest['low'])
            volume = float(latest['volume'])
            ema20 = float(latest['EMA_20'])
            ema50 = float(latest['EMA_50'])
            sma200 = float(latest['SMA_200'])
            atr = float(latest['ATRr_14'])
            rsi = float(latest['RSI_14'])
            avg_vol = float(latest['avg_vol_20'])

            # Consolidated NaN guard for all required indicator values
            required_vals = [atr, avg_vol, rsi, ema20, ema50, sma200]
            if any(pd.isna(v) for v in required_vals) or avg_vol == 0:
                continue

            # Prevent division by zero (circuit-limit stocks have zero range)
            candle_range = high - low
            if candle_range == 0:
                continue

            # --- STRATEGY CONDITIONS ---
            # Condition 1: Uptrend — price above 200 SMA, 20 EMA above 50 EMA
            trend_cond = (close > sma200) and (ema20 > ema50)

            # Condition 2: Pullback — intraday low touched EMA, close confirmed above it
            touch_ema20 = (low <= ema20 * 1.005) and (close >= ema20 * 0.998)
            touch_ema50 = (low <= ema50 * 1.005) and (close >= ema50 * 0.998)
            pullback_cond = touch_ema20 or touch_ema50

            # Condition 3: Trigger — bullish candle closing in upper half of range
            trigger_cond = (close > open_) and (((close - low) / candle_range) > 0.5)

            # Condition 4: Volume — surge of 1.5x the 20-day average
            vol_cond = volume > 1.5 * avg_vol

            # --- SIGNAL GENERATION ---
            if trend_cond and pullback_cond and trigger_cond and vol_cond:
                entry = close
                sl = low - (1.5 * atr)       # SL = candle low minus 1.5x ATR
                risk = entry - sl
                if risk <= 0:                 # Safety check against negative risk
                    continue
                target = entry + (2 * risk)  # Target = 1:2 Risk-Reward minimum

                # Confidence score: 50 base + up to 50 bonus points
                score = 50
                if volume > 2 * avg_vol: score += 15       # Strong volume surge
                if 40 <= rsi <= 55: score += 15            # RSI in pullback zone
                if ema20 > ema50 > sma200: score += 20     # Perfect trend alignment

                # Build signal document for Firestore
                signal_data = {
                    "ticker": symbol,
                    "date": today_str,
                    "entry": round(entry, 2),
                    "stop_loss": round(sl, 2),
                    "target": round(target, 2),
                    "atr": round(atr, 2),
                    "rrr": "1:2",
                    "confidence": int(score),
                    "status": "ACTIVE",
                    "exit_price": None,
                    "pnl_percentage": None,
                    "created_at": datetime.now(IST).isoformat()
                }

                db.collection("signals").add(signal_data)
                send_notification(
                    f"\U0001f7e2 NEW SIGNAL: {symbol}",
                    f"Entry: \u20b9{entry:.2f} | SL: \u20b9{sl:.2f} | T1: \u20b9{target:.2f} | Score: {score}"
                )

        except Exception as e:
            print(f"Error processing {symbol}: {e}")


# --- MAIN EXECUTION ---
if __name__ == "__main__":
    update_active_trades()
    scan_market()
    print("=== Done ===")
