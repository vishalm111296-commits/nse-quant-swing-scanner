"""
sma200_scanner.py — SMA 200 Trend Following System (Separate from ATR-Volume Pullback)
Strategy: Weekly rebalance, buy when Close > SMA 200, sell when Close < SMA 200
Universe: Nifty 50 (proven in backtest files)
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

# --- FIREBASE INIT (safe: won't double-init if scanner.py already ran) ---
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

# --- NIFTY 50 UNIVERSE ---
NIFTY_50 = [
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
]

# --- SECTOR MAP FOR NIFTY 50 ---
SECTOR_MAP_50 = {
    "RELIANCE.NS": "Energy", "ONGC.NS": "Energy", "NTPC.NS": "Energy",
    "POWERGRID.NS": "Energy", "COALINDIA.NS": "Energy", "BPCL.NS": "Energy", "IOC.NS": "Energy",
    "TCS.NS": "IT", "INFY.NS": "IT", "WIPRO.NS": "IT", "HCLTECH.NS": "IT", "TECHM.NS": "IT",
    "HDFCBANK.NS": "Banks", "ICICIBANK.NS": "Banks", "SBIN.NS": "Banks", "KOTAKBANK.NS": "Banks",
    "AXISBANK.NS": "Banks", "INDUSINDBK.NS": "Banks",
    "BAJFINANCE.NS": "Finance", "BAJAJFINSV.NS": "Finance",
    "HDFCLIFE.NS": "Finance", "SBILIFE.NS": "Finance", "ICICIPRULI.NS": "Finance",
    "HINDUNILVR.NS": "FMCG", "ITC.NS": "FMCG", "NESTLEIND.NS": "FMCG",
    "BRITANNIA.NS": "FMCG", "TATACONSUM.NS": "FMCG",
    "SUNPHARMA.NS": "Pharma", "CIPLA.NS": "Pharma", "DRREDDY.NS": "Pharma", "DIVISLAB.NS": "Pharma",
    "MARUTI.NS": "Auto", "TITAN.NS": "Auto", "EICHERMOT.NS": "Auto",
    "HEROMOTOCO.NS": "Auto", "BAJAJ-AUTO.NS": "Auto",
    "LT.NS": "Infra", "ADANIENT.NS": "Infra", "ADANIPORTS.NS": "Infra",
    "ASIANPAINT.NS": "Paints", "PIDILITIND.NS": "Chemicals",
    "ULTRACEMCO.NS": "Cement", "GRASIM.NS": "Cement",
    "JSWSTEEL.NS": "Metals", "TATASTEEL.NS": "Metals", "HINDALCO.NS": "Metals", "VEDL.NS": "Metals",
    "APOLLOHOSP.NS": "Healthcare",
    "BHARTIARTL.NS": "Telecom",
}


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


# --- TRANSACTION COSTS ---
def calculate_txn_costs(entry_value, exit_value):
    """Calculate NSE transaction costs for a round trip."""
    stt_buy    = entry_value * 0.001
    stt_sell   = exit_value  * 0.001
    exchange   = (entry_value + exit_value) * 0.0000345
    sebi       = (entry_value + exit_value) * 0.000001
    stamp      = entry_value * 0.00015
    gst        = exchange * 0.18
    return stt_buy + stt_sell + exchange + sebi + stamp + gst


# --- DATA DOWNLOAD ---
def download_and_prep(ticker, period="2y"):
    df = yf.download(ticker, period=period, interval="1d", progress=False, auto_adjust=True)
    if df.empty:
        return None
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df.columns = [c.lower() for c in df.columns]
    df['SMA_200'] = df['close'].rolling(200).mean()
    return df


# --- SMA 200 TREND SCANNER ---
def scan_sma200_trend():
    """
    Weekly scan for SMA 200 Trend Following strategy.
    Buy: Close > SMA 200
    Sell: Close < SMA 200
    """
    print("=" * 60)
    print("📈 SMA 200 TREND FOLLOWING SCAN")
    print("=" * 60)

    today_str = datetime.now(IST).strftime("%Y-%m-%d")
    today     = datetime.now(IST).date()

    # --- Fetch current holdings ---
    current_holdings = {}
    try:
        docs = db.collection("sma200_positions").where("status", "==", "ACTIVE").stream()
        for doc in docs:
            data = doc.to_dict()
            current_holdings[data['ticker']] = {
                'id':              doc.id,
                'entry':           data.get('entry'),
                'entry_date':      data.get('entry_date'),
                'shares':          data.get('shares', 0),
                'position_value':  data.get('position_value', 0),
            }
    except Exception as e:
        print(f"Error fetching holdings: {e}")

    print(f"Current holdings: {len(current_holdings)}")

    above_sma200 = []
    below_sma200 = []

    for symbol in NIFTY_50:
        try:
            df = download_and_prep(symbol, period="2y")
            if df is None or len(df) < 200:
                continue

            latest      = df.iloc[-1]
            latest_date = df.index[-1]
            if hasattr(latest_date, 'date'):
                latest_date = latest_date.date()

            # Skip stale data
            if latest_date != today:
                print(f"WARNING: {symbol} stale candle ({latest_date}), skipping.")
                continue

            close  = float(latest['close'])
            sma200 = float(latest['SMA_200'])

            if pd.isna(sma200) or sma200 == 0:
                continue

            stock_data = {
                'ticker':       symbol,
                'sector':       SECTOR_MAP_50.get(symbol, 'Other'),
                'close':        round(close, 2),
                'sma200':       round(sma200, 2),
                'distance_pct': round(((close - sma200) / sma200) * 100, 2),
                'date':         today_str,
            }

            if close > sma200:
                above_sma200.append(stock_data)
            else:
                below_sma200.append(stock_data)

        except Exception as e:
            print(f"Error scanning {symbol}: {e}")

    # Sort by distance above SMA 200 (strongest trends first)
    above_sma200.sort(key=lambda x: x['distance_pct'], reverse=True)

    print(f"Stocks above SMA 200: {len(above_sma200)}")
    print(f"Stocks below SMA 200: {len(below_sma200)}")

    # --- 1. SELL positions that fell below SMA 200 ---
    sells = []
    for symbol, holding in current_holdings.items():
        below_data = next((s for s in below_sma200 if s['ticker'] == symbol), None)
        if below_data:
            exit_price = below_data['close']
            entry      = holding['entry']
            pos_val    = holding['position_value']
            shares     = holding['shares']

            # Guard division by zero
            pnl_pct    = ((exit_price - entry) / entry * 100) if entry and entry != 0 else 0
            txn_costs  = calculate_txn_costs(pos_val, shares * exit_price)
            net_pnl    = (shares * (exit_price - entry)) - txn_costs if entry else 0
            net_pnl_pct = (net_pnl / pos_val * 100) if pos_val and pos_val != 0 else 0

            db.collection("sma200_positions").document(holding['id']).update({
                "status":         "CLOSED",
                "exit_price":     exit_price,
                "exit_date":      today_str,
                "pnl_percentage": round(pnl_pct, 4),
                "net_pnl":        round(net_pnl, 2),
                "net_pnl_pct":    round(net_pnl_pct, 4),
                "exit_reason":    "BELOW_SMA200",
                "txn_costs":      round(txn_costs, 2),
                "updated_at":     datetime.now(IST).isoformat()
            })

            sells.append({'ticker': symbol, 'exit_price': exit_price, 'pnl_pct': pnl_pct})
            emoji = "🟢" if pnl_pct > 0 else "🔴"
            send_notification(
                f"{emoji} SMA200 SELL: {symbol}",
                f"Closed at ₹{exit_price:.2f} | PnL: {pnl_pct:.2f}% | Reason: Below SMA 200",
                priority="high" if pnl_pct < -5 else "default"
            )

    # --- 2. BUY new positions above SMA 200 ---
    portfolio_value  = float(os.environ.get("PORTFOLIO_VALUE", 1000000))
    target_positions = min(len(above_sma200), 10)
    weight_per_stock = 1.0 / target_positions if target_positions > 0 else 0

    buys = []
    for stock in above_sma200[:target_positions]:
        symbol = stock['ticker']

        if symbol in current_holdings:
            # Update unrealized PnL for existing holding
            holding      = current_holdings[symbol]
            current_price = stock['close']
            entry        = holding['entry'] or 0
            unrealized   = ((current_price - entry) / entry * 100) if entry != 0 else 0
            db.collection("sma200_positions").document(holding['id']).update({
                "current_price":        current_price,
                "unrealized_pct":       round(unrealized, 4),
                "distance_from_sma200": stock['distance_pct'],
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
        buys.append({'ticker': symbol, 'entry': entry, 'shares': shares, 'position_value': actual_pos_val})

        send_notification(
            f"🟢 SMA200 BUY: {symbol}",
            f"{stock['sector']} | Entry: ₹{entry:.2f} | Shares: {shares} | Value: ₹{actual_pos_val:,.0f} | SMA200: ₹{stock['sma200']:.2f} ({stock['distance_pct']:+.2f}%)",
            priority="default"
        )

    # --- 3. Update market status ---
    db.collection("sma200_market_status").document("current").set({
        "stocks_above_sma200":  len(above_sma200),
        "stocks_below_sma200":  len(below_sma200),
        "total_scan_date":      today_str,
        "target_positions":     target_positions,
        "weight_per_stock_pct": round(weight_per_stock * 100, 2),
        "buys_today":           len(buys),
        "sells_today":          len(sells),
        "active_positions":     len(current_holdings) - len(sells) + len(buys),
        "updated_at":           datetime.now(IST).isoformat()
    })

    summary = (
        f"SMA200 Weekly Scan Complete\n"
        f"Above SMA200: {len(above_sma200)} | Below: {len(below_sma200)}\n"
        f"Buys: {len(buys)} | Sells: {len(sells)} | Active: {len(current_holdings) - len(sells) + len(buys)}"
    )
    send_notification("📊 SMA200 Scan Summary", summary, priority="default")

    print(f"Buys: {len(buys)} | Sells: {len(sells)}")
    print("=== Done ===")


if __name__ == "__main__":
    scan_sma200_trend()
