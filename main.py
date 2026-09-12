import os
import time
import threading
from flask import Flask
import ccxt

# --- Keep Render Alive (Free Web Service ke liye) ---
app = Flask(__name__)
@app.route('/')
def home():
    return "BTC-2-OTM-SELL-BOT is Running!"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

# --- Bot Logic ---
def run_bot():
    api_key = os.getenv("DELTA_API_KEY")
    api_secret = os.getenv("DELTA_API_SECRET")
    
    if not api_key or not api_secret:
        print("ERROR: API Keys not found in Environment Variables!")
        return

    exchange = ccxt.delta({
        'apiKey': api_key,
        'secret': api_secret,
        'options': {'defaultType': 'future'}
    })

    print("Bot Started - Checking for BTC 2 OTM Sell Opportunity...")
    
    while True:
        try:
            # BTC Price
            ticker = exchange.fetch_ticker('BTC/USDT')
            btc_price = ticker['last']
            print(f"BTC Price: {btc_price}")

            # Yaha tumhara 2 OTM ka logic ayega
            # Example: Agar tumhe har 5 min me check karna hai
            # Abhi ke liye sirf log kar raha hai
            
            time.sleep(60)  # 60 sec wait
            
        except Exception as e:
            print(f"Error: {e}")
            time.sleep(10)

# --- Start Both ---
if __name__ == "__main__":
    threading.Thread(target=run_flask).start()
    run_bot()
