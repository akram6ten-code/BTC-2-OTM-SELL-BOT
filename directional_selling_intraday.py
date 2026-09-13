from flask import Flask, jsonify
from datetime import datetime
import pytz, requests
app = Flask(__name__)

OTM_PERCENT = 0.5
SL_PERCENT = 50
ENTRY_START = 7
LAST_ENTRY = 14
trade = {"sell_price": 0, "sl_price": 0, "strike": "", "side": ""}

def ist_now():
    return datetime.now(pytz.timezone('Asia/Kolkata'))

def is_entry_time():
    now = ist_now()
    if now.hour < ENTRY_START: return False, f"WAIT - 7 AM se start, abhi {now.strftime('%H:%M')}"
    if now.hour >= 15: return False, "CLOSED - 3:15 PM square off"
    return True, "Market ON"

def get_btc_info():
    try:
        r = requests.get("https://api.delta.exchange/v2/tickers/BTCUSD", timeout=10).json()
        btc = float(r['result']['mark_price'])
        direction = "BULLISH" if btc > 113000 else "BEARISH"
        return btc, direction
    except Exception as e:
        return None, str(e)

@app.route('/')
def home():
    ok, msg = is_entry_time()
    btc, direction = get_btc_info()
    return jsonify({"bot": "directional_selling_intraday", "status": msg, "btc": btc, "direction": direction, "trade": trade})

@app.route('/run')
def run_bot():
    global trade
    ok, msg = is_entry_time()
    if not ok: return jsonify({"status": msg})
    btc_price, direction = get_btc_info()
    now = ist_now()
    if trade["sell_price"] != 0:
        current_ltp = 84
        gap = trade["sell_price"] * 0.5
        if current_ltp < trade["sell_price"]:
            new_sl = current_ltp + gap
            if new_sl < trade["sl_price"]:
                trade["sl_price"] = new_sl
                return jsonify({"status": f"TRAIL - New SL {new_sl}", "trade": trade})
        if current_ltp >= trade["sl_price"]:
            trade = {"sell_price": 0, "sl_price": 0, "strike": "", "side": ""}
            return jsonify({"status": "SL HIT - Exit"})
        return jsonify({"status": "HOLD", "trade": trade})
    if now.hour >= LAST_ENTRY:
        return jsonify({"status": "WAIT - 2 PM ke baad entry band, kal dekhenge"})
    otm = btc_price * OTM_PERCENT / 100
    if direction == "BULLISH":
        strike = int(round((btc_price - otm)/100)*100)
        sell_price = 85
        trade.update({"sell_price": sell_price, "sl_price": sell_price*1.5, "strike": f"{strike} PUT", "side": "PUT SELL"})
    else:
        strike = int(round((btc_price + otm)/100)*100)
        sell_price = 85
        trade.update({"sell_price": sell_price, "sl_price": sell_price*1.5, "strike": f"{strike} CALL", "side": "CALL SELL"})
    return jsonify({"status": f"ENTRY - {trade['side']} {trade['strike']}", "trade": trade})

if __name__ == "__main__":
    app.run()
