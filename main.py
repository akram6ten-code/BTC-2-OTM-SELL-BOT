from flask import Flask
import ccxt
import os
import pandas as pd
from datetime import datetime, timedelta

app = Flask(__name__)
API_KEY = os.environ.get("DELTA_API_KEY")
API_SECRET = os.environ.get("DELTA_API_SECRET")

positions = {}
LEVERAGE = 200
QTY = 100  # 100 lot

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
        exchange = ccxt.delta({
            'apiKey': API_KEY,
            'secret': API_SECRET,
            'urls': {'api': 'https://api.demo.delta.exchange'}
        })
        
        close, vwap, is_bull = get_indicators(exchange)
        condition = (close > vwap) and is_bull
        
        # 2 Strike OTM PUT
        otm_put_strike = int(round(close / 1000) * 1000 - 2000)
        tomorrow = datetime.utcnow() + timedelta(days=1)
        expiry_str = tomorrow.strftime('%d%m%y')
        symbol = f"P-BTC-{otm_put_strike}-{expiry_str}"

        log = f"DEMO | Lev:{LEVERAGE}x Qty:{QTY} | BTC:{round(close,2)} VWAP:{round(vwap,2)} Bull:{is_bull} | Symbol:{symbol} | Signal:{condition}"

        # ENTRY
        if condition and 'active' not in positions:
            # Leverage set - Delta me
            try:
                exchange.set_leverage(LEVERAGE, symbol)
            except:
                pass # demo pe kabhi fail hota hai, ignore
            
            ticker = exchange.fetch_ticker(symbol)
            entry = ticker['last']
            
            # REAL SELL ORDER - 100 lot
            # exchange.create_order(symbol, 'limit', 'sell', QTY, entry)
            
            positions['active'] = {
                'symbol': symbol,
                'entry': entry,
                'sl': entry * 1.70,      # 70% SL
                'target': entry * 0.10, # 90% profit
                'qty': QTY,
                'half_booked': False
            }
            log += f" | SELL {QTY} LOT @ {entry} | SL:{round(entry*1.7,2)} TGT:{round(entry*0.1,2)}"

        # EXIT / TRAIL LOGIC
        if 'active' in positions:
            pos = positions['active']
            curr = exchange.fetch_ticker(pos['symbol'])['last']
            pnl = (pos['entry'] - curr) / pos['entry'] * 100
            log += f" | LTP:{curr} PnL:{round(pnl,2)}%"

            # 1% Trail
            if pnl >= 1:
                pos['sl'] = pos['sl'] - (pos['entry']*0.01)
                log += f" Trail SL->{round(pos['sl'],2)}"

            # 50% pe half book
            if pnl >= 50 and not pos['half_booked']:
                # exchange.create_order(pos['symbol'], 'limit', 'buy', QTY/2, curr) # half buy to close
                pos['half_booked'] = True
                pos['qty'] = QTY/2
                pos['sl'] = pos['entry']
                log += f" | 50% HIT Half Booked {QTY/2} lot, SL to COST"

            if curr <= pos['target']:
                # exchange.create_order(pos['symbol'], 'limit', 'buy', pos['qty'], curr)
                log += " | 90% TARGET HIT EXIT"
                positions.pop('active')
            elif curr >= pos['sl']:
                log += " | 70% SL HIT EXIT"
                positions.pop('active')

        return log
    except Exception as e:
        return f"Error: {e}"

@app.route('/')
def home():
    return f"BOT LIVE 200x 100LOT {datetime.now()}"

@app.route('/run')
def run():
    return run_bot()

@app.route('/status')
def status():
    return str(positions)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
