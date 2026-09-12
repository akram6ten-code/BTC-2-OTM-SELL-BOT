from flask import Flask
import ccxt
import os
import pandas as pd
from datetime import datetime, timedelta

app = Flask(__name__)

API_KEY = os.environ.get("DELTA_API_KEY")
API_SECRET = os.environ.get("DELTA_API_SECRET")

positions = {}

def get_indicators(exchange):
    ohlcv = exchange.fetch_ohlcv('BTC/USD', '15m', limit=100)
    df = pd.DataFrame(ohlcv, columns=['time','open','high','low','close','volume'])
    df['vwap'] = (df['close'] * df['volume']).cumsum() / df['volume'].cumsum()
    hl2 = (df['high'] + df['low']) / 2
    atr = (df['high'] - df['low']).rolling(10).mean()
    df['st_lower'] = hl2 - (3 * atr)
    df['supertrend_bull'] = df['close'] > df['st_lower']
    last = df.iloc[-1]
    return last['close'], last['vwap'], last['supertrend_bull']

def run_bot():
    try:
        # DEMO ACCOUNT ke liye ye URL important hai
        exchange = ccxt.delta({
            'apiKey': API_KEY,
            'secret': API_SECRET,
            'urls': {
                'api': 'https://api.demo.delta.exchange'
            }
        })
        close, vwap, is_bull = get_indicators(exchange)
        condition = (close > vwap) and is_bull
        otm_put_strike = int(round(close / 1000) * 1000 - 2000)
        tomorrow = datetime.utcnow() + timedelta(days=1)
        expiry_str = tomorrow.strftime('%d%m%y')
        symbol = f"P-BTC-{otm_put_strike}-{expiry_str}"
        
        log = f"DEMO | BTC:{round(close,2)} VWAP:{round(vwap,2)} Bull:{is_bull} | NEXT DAY {tomorrow.strftime('%d-%b')} PUT {otm_put_strike} | Symbol:{symbol} | Signal:{condition}"
        print(log)

        if condition and 'active' not in positions:
            try:
                ticker = exchange.fetch_ticker(symbol)
                entry = ticker['last']
            except:
                entry = 500
            positions['active'] = {'symbol': symbol, 'entry': entry, 'sl': entry*1.70, 'target': entry*0.10, 'half_booked': False}
            log += f" | DEMO SELL {symbol} @ {entry}"

        return log
    except Exception as e:
        return f"Error: {e}"

@app.route('/')
def home():
    return f"DEMO PUT-SELL BOT LIVE | {datetime.now()}"

@app.route('/run')
def run():
    return run_bot()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
