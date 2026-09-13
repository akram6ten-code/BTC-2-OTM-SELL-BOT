from flask import Flask, jsonify
from datetime import datetime
import pytz, requests, os

app = Flask(__name__)

# ===== FINAL JUJU BOT - DELTA DEMO ONLY =====
DEMO_URL = "https://api.demo.delta.exchange"
OTM = 0.5
GAP = 70  # Tera 70 ka gap - FIX
START_HOUR = 7
LAST_ENTRY_HOUR = 14

trade = {"active": False, "sell": 0, "sl": 0, "strike": "", "side": "", "gap": 70}

def now_ist():
    return datetime.now(pytz.timezone('Asia/Kolkata'))

def get_btc():
    try:
        r = requests.get(f"{DEMO_URL}/v2/tickers/BTCUSD", timeout=5).json()
        price = float(r['result']['mark_price'])
        # GREEN / RED - Yaha RSI+Supertrend ayega, abhi price se
        trend = "GREEN" if price > 113500 else "RED"
        return price, trend
    except:
        return None, "ERROR"

@app.route('/')
def home():
    btc, trend = get_btc()
    t = now_ist()
    return jsonify({
        "BOT": "DEMO 0.5% OTM SELL",
        "TIME": t.strftime("%H:%M:%S"),
        "BTC": btc,
        "TREND": trend,
        "TRADE": trade,
        "LOGIC": "80 Sell -> 150 SL (Gap 70). 70 aayi -> SL 140"
    })

@app.route('/run')
def run():
    global trade
    t = now_ist()
    btc, trend = get_btc()

    if t.hour < START_HOUR:
        return jsonify({"STATUS": f"WAIT - 7 AM se start hai, abhi {t.strftime('%H:%M')} hai"})
    
    if t.hour >= 15 and t.minute >= 15:
        trade = {"active": False, "sell": 0, "sl": 0, "strike": "", "side": "", "gap": 70}
        return jsonify({"STATUS": "SQUARE OFF 3:15 PM - DEMO"})

    # TRADE CHAL RAHA HAI TO TRAIL KAR
    if trade["active"]:
        # Is jagah us option ka LTP DEMO API se ayega
        ltp = 70  # Example
        if ltp < trade["sell"]:
            new_sl = ltp + GAP  # 70 + 70 = 140
            if new_sl < trade["sl"]:
                trade["sl"] = new_sl
                trade["sell"] = ltp
                return jsonify({"STATUS": f"TRAIL - LTP {ltp} -> New SL {new_sl}", "TRADE": trade})
        if ltp >= trade["sl"]:
            trade = {"active": False, "sell": 0, "sl": 0, "strike": "", "side": "", "gap": 70}
            return jsonify({"STATUS": "SL HIT 150 - EXIT DEMO"})
        return jsonify({"STATUS": "HOLD", "TRADE": trade})

    # 2 PM ke baad nayi entry nahi
    if t.hour >= LAST_ENTRY_HOUR:
        return jsonify({"STATUS": "WAIT - 2 PM ke baad nayi entry band, kal 7 AM check"})

    # CONDITION MATCH NAHI HUI TO WAIT
    if trend not in ["GREEN", "RED"]:
        return jsonify({"STATUS": f"WAIT - Condition match nahi, 5 min baad check [BTC {btc}]"})

    # NAYI ENTRY - 0.5% OTM
    otm_amt = btc * OTM / 100
    if trend == "GREEN":
        strike = int(round((btc - otm_amt)/100)*100)
        trade = {"active": True, "sell": 80, "sl": 150, "strike": f"{strike} PUT", "side": "PUT SELL GREEN", "gap": 70}
    else:
        strike = int(round((btc + otm_amt)/100)*100)
        trade = {"active": True, "sell": 80, "sl": 150, "strike": f"{strike} CALL", "side": "CALL SELL RED", "gap": 70}

    return jsonify({"STATUS": f"DEMO ENTRY - {trade['side']} {trade['strike']} SELL 80 SL 150", "TRADE": trade})

if __name__ == "__main__":
    app.run()
