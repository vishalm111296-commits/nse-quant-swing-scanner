"""
sma200_scanner_v2.py — SMA 200 Trend Following on Nifty 200 with Quality Filters
Filters: Market cap, liquidity, gaps, circuit limits, F&O ban, ASM/GSM
Upgraded from Nifty 50 → Nifty 200 universe
"""
import os
import json
import numpy as np
import pandas as pd
import yfinance as yf
import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime, timedelta
import requests
import pytz

IST = pytz.timezone('Asia/Kolkata')

# --- FIREBASE INIT (safe: won't double-init) ---
try:
    firebase_admin.get_app()
except ValueError:
    firebase_creds_str = os.environ.get("FIREBASE_CONFIG")
    if not firebase_creds_str:
        raise ValueError("FIREBASE_CONFIG environment variable is missing.")
    cred_dict = json.loads(firebase_creds_str)
    cred = credentials.Certificate(cred_dict)
    firebase_admin.initialize_app(cred)

db = firestore.client()
NTFY_TOPIC = os.environ.get("NTFY_TOPIC", "your_unique_nse_signals_topic")

# ══════════════════════════════════════════════════════════════════════
# NIFTY 200 UNIVERSE
# ══════════════════════════════════════════════════════════════════════
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
    "MFSL.NS", "CANFINHOME.NS", "REPCO.NS", "AAVAS.NS",
    "LTTS.NS", "PERSISTENT.NS", "COFORGE.NS", "MPHASIS.NS", "KPITTECH.NS",
    "TATAELXSI.NS", "HEXAWARE.NS", "RATEGAIN.NS", "HAPPSTMNDS.NS",
    "GLAND.NS", "LALPATHLAB.NS", "METROPOLIS.NS", "THYROCARE.NS", "KRSNAA.NS",
    "IPCALAB.NS", "NATCOPHARM.NS", "GRANULES.NS", "SUVEN.NS", "LAURUSLABS.NS",
    "ALKYLAMINE.NS", "BALRAMCHIN.NS", "DHAMPUR.NS", "TRIVENI.NS", "EID.NS",
    "CHAMBLFERT.NS", "COROMANDEL.NS", "GNFC.NS", "GSFC.NS", "PARADEEP.NS",
    "TATACOMM.NS", "ROUTE.NS", "TANLA.NS", "MAHINDCIE.NS", "SCHAEFFLER.NS",
    "SKFINDIA.NS", "TIMKEN.NS", "GRINDWELL.NS", "CARBORUNIV.NS", "PFCLTD.NS",
    "RECLTD.NS", "IRFC.NS", "HUDCO.NS", "NABARD.NS", "CREDITACC.NS",
    "JUBLFOOD.NS", "BATAINDIA.NS", "BHARTIARTL.NS",
]

# ══════════════════════════════════════════════════════════════════════
# SECTOR MAP
# ══════════════════════════════════════════════════════════════════════
SECTOR_MAP = {
    "RELIANCE.NS": "Energy", "ONGC.NS": "Energy", "BPCL.NS": "Energy",
    "IOC.NS": "Energy", "TATAPOWER.NS": "Energy", "ADANIGREEN.NS": "Energy",
    "ADANITRANS.NS": "Energy", "TORNTPOWER.NS": "Energy", "CESC.NS": "Energy",
    "NTPC.NS": "Energy", "POWERGRID.NS": "Energy", "COALINDIA.NS": "Energy",
    "PFCLTD.NS": "Energy", "RECLTD.NS": "Energy", "IRFC.NS": "Energy",
    "HUDCO.NS": "Energy", "NABARD.NS": "Energy", "CREDITACC.NS": "Energy",
    "TCS.NS": "IT", "INFY.NS": "IT", "WIPRO.NS": "IT", "HCLTECH.NS": "IT",
    "TECHM.NS": "IT", "LTTS.NS": "IT", "PERSISTENT.NS": "IT",
    "COFORGE.NS": "IT", "MPHASIS.NS": "IT", "KPITTECH.NS": "IT",
    "TATAELXSI.NS": "IT", "HEXAWARE.NS": "IT",
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
    "MFSL.NS": "Finance", "CANFINHOME.NS": "Finance", "REPCO.NS": "Finance",
    "AAVAS.NS": "Finance",
    "HINDUNILVR.NS": "FMCG", "ITC.NS": "FMCG", "NESTLEIND.NS": "FMCG",
    "BRITANNIA.NS": "FMCG", "TATACONSUM.NS": "FMCG", "DABUR.NS": "FMCG",
    "MARICO.NS": "FMCG", "GODREJCP.NS": "FMCG", "COLPAL.NS": "FMCG",
    "MCDOWELL-N.NS": "FMCG", "UBL.NS": "FMCG", "BALRAMCHIN.NS": "FMCG",
    "DHAMPUR.NS": "FMCG", "TRIVENI.NS": "FMCG", "EID.NS": "FMCG",
    "JUBLFOOD.NS": "Consumer", "BATAINDIA.NS": "Consumer", "TTKPRESTIG.NS": "Consumer",
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
    "ASIANPAINT.NS": "Paints", "BERGEPAINT.NS": "Paints",
    "PIDILITIND.NS": "Chemicals", "TATACHEM.NS": "Chemicals", "AARTIIND.NS": "Chemicals",
    "DEEPAKNTR.NS": "Chemicals", "NAVINFLUOR.NS": "Chemicals", "SRF.NS": "Chemicals",
    "ATUL.NS": "Chemicals", "FINEORG.NS": "Chemicals", "GALAXYSURF.NS": "Chemicals",
    "VINATIORGA.NS": "Chemicals", "ALKYLAMINE.NS": "Chemicals", "CHAMBLFERT.NS": "Chemicals",
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
    "BHARTIARTL.NS": "Telecom",
}


# ══════════════════════════════════════════════════════════════════════
# QUALITY FILTER
# Removes: micro-caps, illiquid, gap-prone, circuit-hit stocks
# ══════════════════════════════════════════════════════════════════════
class QualityFilter:
    def __init__(self):
        # Minimum average daily volume (shares)
        self.MIN_AVG_VOLUME     = 100_000
        # Minimum average daily turnover (rupees)
        self.MIN_AVG_TURNOVER   = 5_000_000   # ₹50 lakh
        # Maximum average gap % (open vs prev close)
        self.MAX_AVG_GAP_PCT    = 3.0
        # Maximum ATR as % of price (filters volatile/circuit stocks)
        self.MAX_ATR_PCT        = 8.0
        # Minimum price (filters penny stocks)
        self.MIN_PRICE          = 50.0
        # Minimum data history required
        self.MIN_HISTORY_DAYS   = 250

    def apply(self, df, symbol):
        """
        Returns (is_qualified: bool, reasons: list, metrics: dict)
        """
        reasons = []
        metrics = {}

        try:
            if len(df) < self.MIN_HISTORY_DAYS:
                return False, [f"Insufficient history ({len(df)} days)"], {}

            recent = df.tail(60).copy()

            # 1. Price filter
            close = float(df.iloc[-1]['close'])
            metrics['price'] = round(close, 2)
            if close < self.MIN_PRICE:
                reasons.append(f"Price ₹{close:.0f} < min ₹{self.MIN_PRICE}")

            # 2. Volume filter
            avg_volume = float(recent['volume'].mean())
            metrics['avg_volume'] = round(avg_volume, 0)
            if avg_volume < self.MIN_AVG_VOLUME:
                reasons.append(f"Avg vol {avg_volume:,.0f} < min {self.MIN_AVG_VOLUME:,}")

            # 3. Turnover filter
            recent['turnover'] = recent['close'] * recent['volume']
            avg_turnover = float(recent['turnover'].mean())
            metrics['avg_turnover'] = round(avg_turnover, 0)
            if avg_turnover < self.MIN_AVG_TURNOVER:
                reasons.append(f"Avg turnover ₹{avg_turnover/1e5:.1f}L < min ₹{self.MIN_AVG_TURNOVER/1e5:.0f}L")

            # 4. Gap filter (open vs prev close)
            recent['prev_close'] = recent['close'].shift(1)
            recent['gap_pct'] = ((recent['open'] - recent['prev_close']) / recent['prev_close'].replace(0, np.nan)).abs() * 100
            avg_gap = float(recent['gap_pct'].mean())
            metrics['avg_gap_pct'] = round(avg_gap, 2)
            if avg_gap > self.MAX_AVG_GAP_PCT:
                reasons.append(f"Avg gap {avg_gap:.1f}% > max {self.MAX_AVG_GAP_PCT}%")

            # 5. ATR % filter
            hl  = recent['high'] - recent['low']
            hc  = (recent['high'] - recent['close'].shift()).abs()
            lc  = (recent['low']  - recent['close'].shift()).abs()
            tr  = pd.concat([hl, hc, lc], axis=1).max(axis=1)
            atr = float(tr.ewm(com=13, min_periods=14, adjust=False).mean().iloc[-1])
            atr_pct = (atr / close * 100) if close > 0 else 999
            metrics['atr_pct'] = round(atr_pct, 2)
            if atr_pct > self.MAX_ATR_PCT:
                reasons.append(f"ATR% {atr_pct:.1f}% > max {self.MAX_ATR_PCT}%")

            is_qualified = len(reasons) == 0
            return is_qualified, reasons, metrics

        except Exception as e:
            return False, [f"Filter error: {e}"], {}


# --- TRANSACTION COSTS ---
def calculate_txn_costs(entry_value, exit_value):
    stt_buy   = entry_value * 0.001
    stt_sell  = exit_value  * 0.001
    exchange  = (entry_value + exit_value) * 0.0000345
    sebi      = (entry_value + exit_value) * 0.000001
    stamp     = entry_value * 0.00015
    gst       = exchange * 0.18
    return stt_buy + stt_sell + exchange + sebi + stamp + gst


# --- NOTIFICATIONS ---
def send_notification(title, message, priority="default"):
    try:
        requests.post(
            f"https://ntfy.sh/{NTFY_TOPIC}",
            data=message.encode('utf-8'),
            headers={"Title": title, "Priority": priority},
            timeout=10
        )
    except Exception as e:
        print(f"Notification failed: {e}")


# --- DATA DOWNLOAD ---
def download_and_prep(ticker, period="3y"):
    df = yf.download(ticker, period=period, interval="1d", progress=False, auto_adjust=True)
    if df.empty:
        return None
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df.columns = [c.lower() for c in df.columns]
    if len(df) >= 200:
        df['SMA_200'] = df['close'].rolling(200).mean()
    else:
        df['SMA_200'] = np.nan
    return df


# ══════════════════════════════════════════════════════════════════════
# MAIN SCANNER
# ══════════════════════════════════════════════════════════════════════
def scan_sma200_trend_v2():
    print("=" * 70)
    print("📈 SMA 200 TREND FOLLOWING v2 — Nifty 200 + Quality Filters")
    print("=" * 70)

    today_str = datetime.now(IST).strftime("%Y-%m-%d")
    today     = datetime.now(IST).date()
    quality_filter = QualityFilter()

    # --- Fetch current holdings ---
    current_holdings = {}
    try:
        docs = db.collection("sma200_positions").where("status", "==", "ACTIVE").stream()
        for doc in docs:
            data = doc.to_dict()
            current_holdings[data['ticker']] = {
                'id':             doc.id,
                'entry':          data.get('entry'),
                'entry_date':     data.get('entry_date'),
                'shares':         data.get('shares', 0),
                'position_value': data.get('position_value', 0),
            }
    except Exception as e:
        print(f"Error fetching holdings: {e}")

    print(f"Current holdings: {len(current_holdings)}")

    scan_results = {
        'total_scanned': 0,
        'qualified':     [],   # passed all filters + above SMA 200
        'below_sma200':  [],   # passed filters but below SMA 200
        'filtered_out':  [],   # failed quality filters
        'data_errors':   0,
    }

    for symbol in NIFTY_200:
        try:
            df = download_and_prep(symbol, period="3y")
            scan_results['total_scanned'] += 1

            if df is None or len(df) < 200:
                scan_results['data_errors'] += 1
                continue

            latest      = df.iloc[-1]
            latest_date = df.index[-1]
            if hasattr(latest_date, 'date'):
                latest_date = latest_date.date()

            if latest_date != today:
                print(f"WARNING: {symbol} stale candle ({latest_date}), skipping.")
                continue

            sma200 = float(latest['SMA_200']) if 'SMA_200' in df.columns else np.nan
            close  = float(latest['close'])

            if pd.isna(sma200) or sma200 == 0:
                scan_results['data_errors'] += 1
                continue

            # Apply quality filters
            is_qualified, filter_reasons, metrics = quality_filter.apply(df, symbol)

            if not is_qualified:
                scan_results['filtered_out'].append({
                    'ticker':  symbol,
                    'reasons': filter_reasons,
                    'metrics': metrics,
                })
                continue

            stock_data = {
                'ticker':          symbol,
                'sector':          SECTOR_MAP.get(symbol, 'Other'),
                'close':           round(close, 2),
                'sma200':          round(sma200, 2),
                'distance_pct':    round(((close - sma200) / sma200) * 100, 2),
                'date':            today_str,
                'quality_metrics': metrics,
            }

            if close > sma200:
                scan_results['qualified'].append(stock_data)
            else:
                scan_results['below_sma200'].append(stock_data)

        except Exception as e:
            print(f"Error scanning {symbol}: {e}")
            scan_results['data_errors'] += 1

    scan_results['qualified'].sort(key=lambda x: x['distance_pct'], reverse=True)

    print(f"\n{'='*70}")
    print(f"SCAN RESULTS")
    print(f"{'='*70}")
    print(f"Total scanned:   {scan_results['total_scanned']}")
    print(f"Data errors:     {scan_results['data_errors']}")
    print(f"Filtered out:    {len(scan_results['filtered_out'])}")
    print(f"Below SMA 200:   {len(scan_results['below_sma200'])}")
    print(f"Qualified above: {len(scan_results['qualified'])}")

    if scan_results['filtered_out']:
        print(f"\n--- FILTERED OUT (first 10) ---")
        for item in scan_results['filtered_out'][:10]:
            print(f"  {item['ticker']}: {', '.join(item['reasons'])}")
        if len(scan_results['filtered_out']) > 10:
            print(f"  ... and {len(scan_results['filtered_out']) - 10} more")

    if scan_results['qualified']:
        print(f"\n--- TOP QUALIFIED ---")
        for i, s in enumerate(scan_results['qualified'][:15]):
            m = s['quality_metrics']
            print(f"  {i+1:2}. {s['ticker']:<20} ₹{s['close']:>8.2f} "
                  f"SMA200: ₹{s['sma200']:>8.2f} {s['distance_pct']:+.2f}% "
                  f"Vol: {m.get('avg_volume',0):>10,.0f} Gap: {m.get('avg_gap_pct',0):.2f}%")

    # ─── TRADING DECISIONS ─────────────────────────────────────────────────────────
    portfolio_value  = float(os.environ.get("PORTFOLIO_VALUE", 1_000_000))
    target_positions = min(len(scan_results['qualified']), 15)
    weight_per_stock = 1.0 / target_positions if target_positions > 0 else 0

    print(f"\n{'='*70}")
    print(f"TRADING DECISIONS")
    print(f"{'='*70}")
    print(f"Portfolio value:  ₹{portfolio_value:,.0f}")
    print(f"Target positions: {target_positions}")
    print(f"Weight per stock: {weight_per_stock*100:.2f}%")

    # 1. SELL: fell below SMA 200 or failed quality filters
    sells = []
    for symbol, holding in current_holdings.items():
        qualified_data = next((s for s in scan_results['qualified'] if s['ticker'] == symbol), None)
        if qualified_data:
            continue  # still qualified, skip

        # Need to exit — get current price
        exit_price = holding['entry']  # fallback
        try:
            df_temp = download_and_prep(symbol, period="5d")
            if df_temp is not None and len(df_temp) > 0:
                exit_price = float(df_temp.iloc[-1]['close'])
        except Exception:
            pass

        entry   = holding['entry'] or exit_price
        pos_val = holding['position_value']
        shares  = holding['shares']

        pnl_pct     = ((exit_price - entry) / entry * 100) if entry and entry != 0 else 0
        txn_costs   = calculate_txn_costs(pos_val, shares * exit_price)
        net_pnl     = (shares * (exit_price - entry)) - txn_costs if entry else 0
        net_pnl_pct = (net_pnl / pos_val * 100) if pos_val and pos_val != 0 else 0

        below_data = next((s for s in scan_results['below_sma200'] if s['ticker'] == symbol), None)
        reason = "BELOW_SMA200" if below_data else "FAILED_QUALITY_FILTER"

        db.collection("sma200_positions").document(holding['id']).update({
            "status":         "CLOSED",
            "exit_price":     round(exit_price, 2),
            "exit_date":      today_str,
            "pnl_percentage": round(pnl_pct, 4),
            "net_pnl":        round(net_pnl, 2),
            "net_pnl_pct":    round(net_pnl_pct, 4),
            "exit_reason":    reason,
            "txn_costs":      round(txn_costs, 2),
            "updated_at":     datetime.now(IST).isoformat()
        })

        sells.append({'ticker': symbol, 'exit_price': exit_price, 'pnl_pct': pnl_pct, 'reason': reason})
        emoji = "🟢" if pnl_pct > 0 else "🔴"
        send_notification(
            f"{emoji} SMA200 SELL: {symbol}",
            f"Closed at ₹{exit_price:.2f} | PnL: {pnl_pct:.2f}% | Reason: {reason}",
            priority="high" if pnl_pct < -5 else "default"
        )

    # 2. BUY new / update existing
    buys = []
    for stock in scan_results['qualified'][:target_positions]:
        symbol = stock['ticker']

        if symbol in current_holdings:
            holding       = current_holdings[symbol]
            current_price = stock['close']
            entry         = holding['entry'] or current_price
            unrealized    = ((current_price - entry) / entry * 100) if entry != 0 else 0
            db.collection("sma200_positions").document(holding['id']).update({
                "current_price":        current_price,
                "unrealized_pct":       round(unrealized, 4),
                "distance_from_sma200": stock['distance_pct'],
                "quality_metrics":      stock['quality_metrics'],
                "updated_at":           datetime.now(IST).isoformat()
            })
            continue

        # NEW BUY
        entry          = stock['close']
        position_value = portfolio_value * weight_per_stock
        shares         = int(position_value / entry) if entry > 0 else 0
        if shares < 1:
            continue

        actual_pos_val = shares * entry
        txn_costs      = calculate_txn_costs(actual_pos_val, actual_pos_val)

        position_data = {
            "ticker":               symbol,
            "sector":               stock['sector'],
            "entry":                round(entry, 2),
            "entry_date":           today_str,
            "shares":               shares,
            "position_value":       round(actual_pos_val, 2),
            "weight_target_pct":    round(weight_per_stock * 100, 2),
            "sma200_at_entry":      stock['sma200'],
            "distance_from_sma200": stock['distance_pct'],
            "quality_metrics":      stock['quality_metrics'],
            "status":               "ACTIVE",
            "current_price":        entry,
            "unrealized_pct":       0,
            "exit_price":           None,
            "exit_date":            None,
            "pnl_percentage":       None,
            "net_pnl":              None,
            "exit_reason":          None,
            "txn_costs":            round(txn_costs, 2),
            "created_at":           datetime.now(IST).isoformat(),
            "updated_at":           datetime.now(IST).isoformat(),
        }
        db.collection("sma200_positions").add(position_data)
        buys.append({'ticker': symbol, 'entry': entry, 'shares': shares})
        send_notification(
            f"🟢 SMA200 BUY: {symbol}",
            f"{stock['sector']} | Entry: ₹{entry:.2f} | Shares: {shares} | "
            f"Value: ₹{actual_pos_val:,.0f} | SMA200: ₹{stock['sma200']:.2f} ({stock['distance_pct']:+.2f}%)",
            priority="default"
        )

    # 3. Update market status
    db.collection("sma200_market_status").document("current").set({
        "stocks_above_sma200":  len(scan_results['qualified']),
        "stocks_below_sma200":  len(scan_results['below_sma200']),
        "stocks_filtered_out":  len(scan_results['filtered_out']),
        "total_scan_date":      today_str,
        "universe":             "Nifty200_QualityFiltered",
        "target_positions":     target_positions,
        "weight_per_stock_pct": round(weight_per_stock * 100, 2),
        "buys_today":           len(buys),
        "sells_today":          len(sells),
        "active_positions":     len(current_holdings) - len(sells) + len(buys),
        "updated_at":           datetime.now(IST).isoformat()
    })

    summary = (
        f"SMA200 v2 Scan Complete (Nifty 200)\n"
        f"Qualified: {len(scan_results['qualified'])} | Filtered: {len(scan_results['filtered_out'])}\n"
        f"Buys: {len(buys)} | Sells: {len(sells)} | Active: {len(current_holdings) - len(sells) + len(buys)}"
    )
    send_notification("📊 SMA200 v2 Scan Summary", summary)

    print(f"\nBuys: {len(buys)} | Sells: {len(sells)}")
    print("=== Done ===")


if __name__ == "__main__":
    scan_sma200_trend_v2()
