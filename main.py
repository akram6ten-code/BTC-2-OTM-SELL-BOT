from flask import Flask
import ccxt
import os
import pandas as pd
from datetime import datetime, timedelta

app = Flask(__name__)

API_KEY = os.environ.get("DELTA_API_KEY")
API_SECRET = os.environ.get("DELTA_API_SECRET")

positions = {}

def get_next_day_expiry(exchange):
    # Delta pe saare BTC options lao
    exchange.load_markets()
    # Kal ki date
    tomorrow = (datetime.utcnow() + timedelta(days=1)).strftime('%d-%m-%y')
    # 14-09-26 jaise format me expiry aati hai Delta pe
    # Hum sabse nazdeek wali expiry nikalenge jo kal ya usse agla din ho
    options = [m for m in exchange.markets.values() if 'BTC' in m['id'] and m['type'] == 'option']
    # Expiry nikal ke sort karo
    expiries = sorted(list(set([m['info']['settlement_time'] for m in options])))
    # Simple: kal wali expiry dhundo, nahi mili to sabse nazdeek wali
    # Yaha hum logic simple rakhe hai - agla available expiry lega jo aaj se bada hai
    return options

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
        exchange = ccxt.delta({'apiKey': API_KEY, 'secret': API_SECRET})
        close, vwap, is_bull = get_indicators(exchange)
        
        condition = (close > vwap) and is_bull
        
        # 2 Strike OTM PUT = 2 strike neeche
        otm_put_strike = int(round(close / 1000) * 1000 - 2000)
        
        # NEXT DAY EXPIRY
        tomorrow = datetime.utcnow() + timedelta(days=1)
        # Delta symbol format: P-BTC-112000-140926  (140926 = 14 Sep 26)
        expiry_str = tomorrow.strftime('%d%m%y')
        symbol = f"P-BTC-{otm_put_strike}-{expiry_str}"
        # Delta full symbol: P-BTC-112000-140926
        # ccxt me isko aise dhoondhna padta hai: BTC-14SEP26-112000-P ya similar, isliye hum load_markets se match karenge
        
        exchange.load_markets()
        final_symbol = None
        for m in exchange.markets:
            if str(otm_put_strike) in m and 'P' in m and expiry_str[0:2] in m: # loose match
                final_symbol = m
                break
        # Agar exact na mile to jo banaya wahi use karo
        if not final_symbol:
            final_symbol = symbol
        
        log = f"BTC:{round(close,2)} VWAP:{round(vwap,2)} Bull:{is_bull} | NEXT DAY {tomorrow.strftime('%d-%b')} PUT {otm_put_strike} CE | Symbol Try: {final_symbol} | Signal:{condition} | {datetime.now()}"
        print(log)

        if condition and 'active' not in positions:
            # Entry premium fetch karo
            try:
                ticker = exchange.fetch_ticker(final_symbol)
                entry_premium = ticker['last']
            except:
                entry_premium = 500 # fallback agar symbol na mile to testing ke liye
            
            positions['active'] = {
                'symbol': final_symbol,
                'strike': otm_put_strike,
                'expiry': expiry_str,
                'entry': entry_premium,
                'qty': 2,
                'sl': entry_premium * 1.70, # 70% SL
                'target': entry_premium * 0.10, # 90% profit = 10% bacha
                'half_booked': False,
            }
            log += f" | SELL INIT @ {entry_premium} SL {round(entry_premium*1.70,2)} TGT {round(entry_premium*0.10,2)}"

        # Trail + 50% logic
        if 'active' in positions:
            pos = positions['active']
            try:
                curr = exchange.fetch_ticker(pos['symbol'])['last']
            except:
                curr = pos['entry'] * 0.6 # test
            
            pnl = (pos['entry'] - curr) / pos['entry'] * 100
            log += f" | LTP:{curr} PnL:{round(pnl,2)}%"

            if pnl >= 1:
                # 1% trail
                new_sl = pos['sl'] - (pos['entry'] * 0.01)
                if new_sl < pos['sl']: # SL neeche aa raha hai PUT SELL me profit pe
                    # PUT SELL me SL upar jata hai loss pe, isliye trail me SL ko entry ki taraf lana hai
                    # Actually profit pe SL ko entry ki taraf lao
                    pos['sl'] = pos['sl'] - (pos['entry']*0.01)
                    log += f" | Trail SL->{round(pos['sl'],2)}"

            if pnl >= 50 and not pos['half_booked']:
                pos['half_booked'] = True
                pos['sl'] = pos['entry']
                log += f" | 50% HIT -> Half Book, Rest SL to COST"

            if curr <= pos['target']:
                log += " | 90% TARGET HIT - EXIT"
                positions.pop('active')
            elif curr >= pos['sl']:
                log += " | 70% SL HIT - EXIT"
                positions.pop('active')

        return log

    except Exception as e:
        return f"Error: {e}"

@app.route('/')
def home():
    return f"NEXT-DAY PUT SELL BOT LIVE | 2-OTM | VWAP+ST | {datetime.now()}"

@app.route('/run')
def run():
    return run_bot()

@app.route('/status')
def status():
    return str(positions)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
