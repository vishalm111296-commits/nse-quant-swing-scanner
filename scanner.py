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
firebase_creds_str = os.environ.get("FIREBASE_CONFIG")
if not firebase_creds_str:
    raise ValueError("FIREBASE_CONFIG environment variable is missing.")
cred_dict = json.loads(firebase_creds_str)
cred = credentials.Certificate(cred_dict)
firebase_admin.initialize_app(cred)
db = firestore.client()

NTFY_TOPIC = os.environ.get("NTFY_TOPIC", "your_unique_nse_signals_topic")
IST = pytz.timezone('Asia/Kolkata')

NSE_HOLIDAYS = [
    '2026-01-26', '2026-03-25', '2026-04-02', '2026-04-03',
    '2026-04-14', '2026-05-01', '2026-08-15', '2026-10-02',
    '2026-10-20', '2026-10-21', '2026-11-05', '2026-12-25'
]
HOLIDAY_CAL = np.busdaycalendar(holidays=NSE_HOLIDAYS)

# --- SECTOR MAP ---
SECTOR_MAP = {
    "RELIANCE.NS": "Energy", "ONGC.NS": "Energy", "BPCL.NS": "Energy",
    "IOC.NS": "Energy", "TATAPOWER.NS": "Energy", "ADANIGREEN.NS": "Energy",
    "ADANITRANS.NS": "Energy", "TORNTPOWER.NS": "Energy", "CESC.NS": "Energy",
    "NTPC.NS": "Energy", "POWERGRID.NS": "Energy", "COALINDIA.NS": "Energy",
    "PFCLTD.NS": "Energy", "RECLTD.NS": "Energy", "IRFC.NS": "Energy",
    "HUDCO.NS": "Energy",
    "TCS.NS": "IT", "INFY.NS": "IT", "WIPRO.NS": "IT", "HCLTECH.NS": "IT",
    "TECHM.NS": "IT", "LTTS.NS": "IT", "PERSISTENT.NS": "IT",
    "COFORGE.NS": "IT", "MPHASIS.NS": "IT", "KPITTECH.NS": "IT",
    "TATAELXSI.NS": "IT", "HEXAWARE.NS": "IT", "NIITTECH.NS": "IT",
    "RATEGAIN.NS": "IT", "HAPPSTMNDS.NS": "IT", "TATACOMM.NS": "IT",
    "ROUTE.NS": "IT", "TANLA.NS": "IT", "NAUKRI.NS": "IT",
    "HDFCBANK.NS": "Banks", "ICICIBANK.NS": "Banks", "SBIN.NS": "Banks",
    "KOTAKBANK.NS": "Banks", "AXISBANK.NS": "Banks", "INDUSINDBK.NS": "Banks",
    "BANKBARODA.NS": "Banks", "PNB.NS": "Banks", "CANBK.NS": "Banks",
    "UNIONBANK.NS": "Banks", "IDFCFIRSTB.NS": "Banks", "FEDERALBNK.NS": "Banks",
    "BANDHANBNK.NS": "Banks", "RBLBANK.NS": "Banks", "KARURVYSYA.NS": "Banks",
    "SOUTHBANK.NS": "Banks",
    "BAJFINANCE.NS": "Finance", "BAJAJFINSV.NS": "Finance", "MUTHOOTFIN.NS": "Finance",
    "CHOLAFIN.NS": "Finance", "SHRIRAMFIN.NS": "Finance", "BAJAJHLDNG.NS": "Finance",
    "HDFCLIFE.NS": "Finance", "SBILIFE.NS": "Finance", "ICICIPRULI.NS": "Finance",
    "MFSL.NS": "Finance", "CANFINHOME.NS": "Finance", "GRUH.NS": "Finance",
    "REPCO.NS": "Finance", "AAVAS.NS": "Finance", "CREDITACC.NS": "Finance",
    "NABARD.NS": "Finance",
    "HINDUNILVR.NS": "FMCG", "ITC.NS": "FMCG", "NESTLEIND.NS": "FMCG",
    "BRITANNIA.NS": "FMCG", "TATACONSUM.NS": "FMCG", "DABUR.NS": "FMCG",
    "MARICO.NS": "FMCG", "GODREJCP.NS": "FMCG", "COLPAL.NS": "FMCG",
    "MCDOWELL-N.NS": "FMCG", "UBL.NS": "FMCG", "BALRAMCHIN.NS": "FMCG",
    "DHAMPUR.NS": "FMCG", "TRIVENI.NS": "FMCG", "EID.NS": "FMCG",
    "SUNPHARMA.NS": "Pharma", "CIPLA.NS": "Pharma", "DRREDDY.NS": "Pharma",
    "DIVISLAB.NS": "Pharma", "ZYDUSLIFE.NS": "Pharma", "LUPIN.NS": "Pharma",
    "AUROPHARMA.NS": "Pharma", "BIOCON.NS": "Pharma", "ALKEM.NS": "Pharma",
    "TORNTPHARM.NS": "Pharma", "GLAXO.NS": "Pharma", "PFIZER.NS": "Pharma",
    "ABBOTINDIA.NS": "Pharma", "SANOFI.NS": "Pharma", "GLAND.NS": "Pharma",
    "IPCALAB.NS": "Pharma", "NATCOPHARM.NS": "Pharma", "GRANULES.NS": "Pharma",
    "SUVEN.NS": "Pharma", "LAURUSLABS.NS": "Pharma",
    "LALPATHLAB.NS": "Healthcare", "METROPOLIS.NS": "Healthcare",
    "THYROCARE.NS": "Healthcare", "KRSNAA.NS": "Healthcare", "APOLLOHOSP.NS": "Healthcare",
    "MARUTI.NS": "Auto", "TITAN.NS": "Auto", "EICHERMOT.NS": "Auto",
    "HEROMOTOCO.NS": "Auto", "BAJAJ-AUTO.NS": "Auto", "M&M.NS": "Auto",
    "MRF.NS": "Auto", "APOLLOTYRE.NS": "Auto", "CEATLTD.NS": "Auto",
    "BALKRISIND.NS": "Auto", "JKTYRE.NS": "Auto", "MOTHERSON.NS": "Auto",
    "MINDAIND.NS": "Auto", "ENDURANCE.NS": "Auto", "CRAFTSMAN.NS": "Auto",
    "MAHINDCIE.NS": "Auto", "SCHAEFFLER.NS": "Auto", "SKFINDIA.NS": "Auto",
    "TIMKEN.NS": "Auto", "SUPRAJIT.NS": "Auto", "VARROC.NS": "Auto",
    "LT.NS": "Infra", "ADANIENT.NS": "Infra", "ADANIPORTS.NS": "Infra",
    "GMRINFRA.NS": "Infra", "IRB.NS": "Infra", "KNRCON.NS": "Infra",
    "NCC.NS": "Infra", "PNCINFRA.NS": "Infra", "HGINFRA.NS": "Infra",
    "GPPL.NS": "Infra", "CONCOR.NS": "Infra", "IRCTC.NS": "Infra",
    "INDIGO.NS": "Infra", "SPICEJET.NS": "Infra", "INDIGRID.NS": "Infra",
    "JSWSTEEL.NS": "Metals", "TATASTEEL.NS": "Metals", "HINDALCO.NS": "Metals",
    "VEDL.NS": "Metals", "HINDZINC.NS": "Metals", "NMDC.NS": "Metals",
    "SAIL.NS": "Metals", "JINDALSTEL.NS": "Metals", "RATNAMANI.NS": "Metals",
    "APLAPOLLO.NS": "Metals", "WELCORP.NS": "Metals", "RAMKRISHNA.NS": "Metals",
    "ASIANPAINT.NS": "Paints", "BERGEPAINT.NS": "Paints", "PIDILITIND.NS": "Chemicals",
    "TATACHEM.NS": "Chemicals", "AARTIIND.NS": "Chemicals", "DEEPAKNTR.NS": "Chemicals",
    "NAVINFLUOR.NS": "Chemicals", "SRF.NS": "Chemicals", "ATUL.NS": "Chemicals",
    "FINEORG.NS": "Chemicals", "GALAXYSURF.NS": "Chemicals", "VINATIORGA.NS": "Chemicals",
    "ALKYLAMINE.NS": "Chemicals", "CHAMBLFERT.NS": "Chemicals",
    "COROMANDEL.NS": "Chemicals", "GNFC.NS": "Chemicals", "GSFC.NS": "Chemicals",
    "PARADEEP.NS": "Chemicals",
    "ULTRACEMCO.NS": "Cement", "GRASIM.NS": "Cement",
    "HAVELLS.NS": "Electricals", "VOLTAS.NS": "Electricals", "SIEMENS.NS": "Electricals",
    "ABB.NS": "Electricals", "BOSCHLTD.NS": "Electricals", "CUMMINSIND.NS": "Electricals",
    "THERMAX.NS": "Electricals", "POLYCAB.NS": "Electricals", "KEI.NS": "Electricals",
    "FINOLEX.NS": "Electricals", "VGUARD.NS": "Electricals", "WHIRLPOOL.NS": "Electricals",
    "SYMPHONY.NS": "Electricals", "GRINDWELL.NS": "Electricals", "CARBORUNIV.NS": "Electricals",
    "DMART.NS": "Retail", "TRENT.NS": "Retail", "NYKAA.NS": "Retail",
    "ZOMATO.NS": "Consumer Tech", "PAYTM.NS": "Consumer Tech", "NAZARA.NS": "Consumer Tech",
    "DLF.NS": "Realty", "GODREJPROP.NS": "Realty", "OBEROIRLTY.NS": "Realty",
    "PRESTIGE.NS": "Realty", "SOBHA.NS": "Realty",
    "ZEEL.NS": "Media", "SUNTV.NS": "Media", "PVRINOX.NS": "Media", "NETWORK18.NS": "Media",
    "PAGEIND.NS": "Textiles", "MANYAVAR.NS": "Textiles",
    "ASTRAL.NS": "Building Mat", "SUPREMEIND.NS": "Building Mat",
    "PRINCEPIPE.NS": "Building Mat", "NILKAMAL.NS": "Building Mat",
    "TTKPRESTIG.NS": "Consumer", "JUBLFOOD.NS": "Consumer", "BATAINDIA.NS": "Consumer",
    # FIX: BHARTIARTL.NS was missing from SECTOR_MAP — mapped to Telecom
    "BHARTIARTL.NS": "Telecom",
}


# --- UTILITY FUNCTIONS ---
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


def compute_rsi_wilder(close, period=14):
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = (-delta.clip(upper=0))
    avg_gain = gain.ewm(com=period - 1, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(com=period - 1, min_periods=period, adjust=False).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def download_ohlc(ticker, period="1mo"):
    df = yf.download(ticker, period=period, interval="1d", progress=False, auto_adjust=True)
    if df.empty:
        return df
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df.columns = [c.lower() for c in df.columns]
    return df


def download_and_prep(ticker, period="1y"):
    df = yf.download(ticker, period=period, interval="1d", progress=False, auto_adjust=True)
    if df.empty:
        return df
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df.columns = [c.lower() for c in df.columns]
    df['EMA_20'] = df['close'].ewm(span=20, adjust=False).mean()
    df['EMA_50'] = df['close'].ewm(span=50, adjust=False).mean()
    df['SMA_200'] = df['close'].rolling(200).mean()
    df['avg_vol_20'] = df['volume'].rolling(20).mean()
    df['RSI_14'] = compute_rsi_wilder(df['close'], 14)
    hl = df['high'] - df['low']
    hc = (df['high'] - df['close'].shift()).abs()
    lc = (df['low'] - df['close'].shift()).abs()
    tr = pd.concat([hl, hc, lc], axis=1).max(axis=1)
    df['ATRr_14'] = tr.ewm(com=13, min_periods=14, adjust=False).mean()
    return df


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
    "TATACHEM.NS", "AARTIIND.NS", "DEEPAKNTR.NS", "NAVINFLUOR.NS",
    "SRF.NS", "ATUL.NS", "FINEORG.NS", "GALAXYSURF.NS", "VINATIORGA.NS",
    "PAGEIND.NS", "MANYAVAR.NS", "TTKPRESTIG.NS", "VGUARD.NS", "SYMPHONY.NS",
    "POLYCAB.NS", "KEI.NS", "FINOLEX.NS", "SUPRAJIT.NS", "VARROC.NS",
    "MOTHERSON.NS", "MINDAIND.NS", "ENDURANCE.NS", "CRAFTSMAN.NS", "RAMKRISHNA.NS",
    "HINDZINC.NS", "NMDC.NS", "SAIL.NS", "JINDALSTEL.NS", "RATNAMANI.NS",
    "APLAPOLLO.NS", "WELCORP.NS", "GMRINFRA.NS", "IRB.NS", "KNRCON.NS",
    "NCC.NS", "PNCINFRA.NS", "HGINFRA.NS", "GPPL.NS", "CONCOR.NS",
    "ASTRAL.NS", "SUPREMEIND.NS", "PRINCEPIPE.NS", "NILKAMAL.NS",
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
    "RECLTD.NS", "IRFC.NS", "HUDCO.NS", "NABARD.NS", "CREDITACC.NS",
    "BHARTIARTL.NS"
]


# --- TRADE MANAGEMENT ---
def update_active_trades():
    print("Checking active trades...")
    active_docs = db.collection("signals").where("status", "==", "ACTIVE").stream()
    today = datetime.now(IST).date()
    for doc in active_docs:
        sig = doc.to_dict()
        ticker = sig["ticker"]
        df = download_ohlc(ticker, period="1mo")
        if len(df) < 1:
            continue
        latest = df.iloc[-1]
        latest_date = df.index[-1].date()

        # FIX: Do not act on stale candle data — skip if candle is not today's
        if latest_date != today:
            print(f"WARNING: {ticker} has stale candle ({latest_date}), skipping trade update.")
            continue

        new_status = "ACTIVE"
        exit_price = None
        low   = float(latest['low'])
        high  = float(latest['high'])
        close = float(latest['close'])
        if low <= sig['stop_loss']:
            exit_price = sig['stop_loss']
            new_status = "LOSS"
        elif high >= sig['target']:
            exit_price = sig['target']
            new_status = "WIN"
        else:
            try:
                entry_date   = datetime.strptime(sig['date'], "%Y-%m-%d").date()
                trading_days = int(np.busday_count(entry_date, today, busdaycal=HOLIDAY_CAL))
                if trading_days >= 10:
                    exit_price = close
                    new_status = "TIME_EXIT"
            except Exception as e:
                print(f"Date parsing error for {ticker}: {e}")
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


# --- MACRO REGIME FILTER ---
def check_market_regime():
    print("Checking market regime (Nifty 50 vs 50 EMA)...")
    try:
        nifty = yf.download("^NSEI", period="6mo", interval="1d", progress=False, auto_adjust=True)
        if nifty.empty:
            print("WARNING: Nifty data empty. Defaulting to bullish.")
            return True
        if isinstance(nifty.columns, pd.MultiIndex):
            nifty.columns = nifty.columns.get_level_values(0)
        nifty.columns = [c.lower() for c in nifty.columns]
        nifty['ema_50'] = nifty['close'].ewm(span=50, adjust=False).mean()
        latest = nifty.iloc[-1]
        is_bullish    = float(latest['close']) > float(latest['ema_50'])
        nifty_close   = round(float(latest['close']), 2)
        ema_50_val    = round(float(latest['ema_50']), 2)
        regime_status = "ON" if is_bullish else "OFF"
        db.collection("market_status").document("current").set({
            "regime":       regime_status,
            "nifty_close":  nifty_close,
            "nifty_ema50":  ema_50_val,
            "updated_at":   datetime.now(IST).isoformat()
        })
        print(f"Market Regime: {regime_status} | Nifty: {nifty_close} | EMA50: {ema_50_val}")
        if not is_bullish:
            send_notification(
                "\u26a0\ufe0f REGIME OFF \u2014 Market Bearish",
                f"Nifty 50 ({nifty_close}) is BELOW 50 EMA ({ema_50_val}). No new entries today."
            )
        return is_bullish
    except Exception as e:
        print(f"Regime check failed: {e}. Defaulting to bullish (fail-safe).")
        return True


# --- MARKET SCANNING ---
def scan_market():
    print("Scanning for new signals...")
    today_str = datetime.now(IST).strftime("%Y-%m-%d")
    today     = datetime.now(IST).date()

    is_bullish = check_market_regime()
    if not is_bullish:
        print("Regime OFF: Skipping new entries. Active trade management continues.")
        return

    for symbol in NIFTY_200:
        try:
            existing = db.collection("signals")\
                .where("ticker", "==", symbol)\
                .where("status", "==", "ACTIVE")\
                .limit(1).stream()
            if any(True for _ in existing):
                continue
            df = download_and_prep(symbol, period="1y")
            if len(df) < 200:
                continue
            latest      = df.iloc[-1]
            latest_date = df.index[-1].date()
            if latest_date != today:
                print(f"WARNING: {symbol} stale candle ({latest_date}), skipping.")
                continue
            close   = float(latest['close'])
            open_   = float(latest['open'])
            high    = float(latest['high'])
            low     = float(latest['low'])
            volume  = float(latest['volume'])
            ema20   = float(latest['EMA_20'])
            ema50   = float(latest['EMA_50'])
            sma200  = float(latest['SMA_200'])
            atr     = float(latest['ATRr_14'])
            rsi     = float(latest['RSI_14'])
            avg_vol = float(latest['avg_vol_20'])
            required_vals = [atr, avg_vol, rsi, ema20, ema50, sma200]
            if any(pd.isna(v) for v in required_vals) or avg_vol == 0:
                continue
            candle_range = high - low
            if candle_range == 0:
                continue
            trend_cond    = (close > sma200) and (ema20 > ema50)
            touch_ema20   = (low <= ema20 * 1.005) and (close >= ema20 * 0.998)
            touch_ema50   = (low <= ema50 * 1.005) and (close >= ema50 * 0.998)
            pullback_cond = touch_ema20 or touch_ema50
            trigger_cond  = (close > open_) and (((close - low) / candle_range) > 0.5)
            vol_cond      = volume > 1.5 * avg_vol
            if trend_cond and pullback_cond and trigger_cond and vol_cond:
                entry  = close
                sl     = low - (1.5 * atr)
                risk   = entry - sl
                if risk <= 0:
                    continue
                target = entry + (2 * risk)
                score  = 50
                if volume > 2 * avg_vol:   score += 15
                if 40 <= rsi <= 55:        score += 15
                if ema20 > ema50 > sma200: score += 20
                sector = SECTOR_MAP.get(symbol, "Other")
                signal_data = {
                    "ticker":         symbol,
                    "sector":         sector,
                    "date":           today_str,
                    "entry":          round(entry, 2),
                    "stop_loss":      round(sl, 2),
                    "target":         round(target, 2),
                    "atr":            round(atr, 2),
                    "rrr":            "1:2",
                    "confidence":     int(score),
                    "status":         "ACTIVE",
                    "exit_price":     None,
                    "pnl_percentage": None,
                    "created_at":     datetime.now(IST).isoformat()
                }
                db.collection("signals").add(signal_data)
                send_notification(
                    f"\U0001f7e2 NEW SIGNAL: {symbol}",
                    f"{sector} | Entry: \u20b9{entry:.2f} | SL: \u20b9{sl:.2f} | T1: \u20b9{target:.2f} | Score: {score}"
                )
        except Exception as e:
            print(f"Error processing {symbol}: {e}")


if __name__ == "__main__":
    update_active_trades()
    scan_market()
    print("=== Done ===")
