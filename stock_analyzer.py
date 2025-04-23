import requests
import pandas as pd
import datetime
import os
import logging
from app import db
from models import Stock, Signal

# Get environment variables
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_ID = os.getenv("TELEGRAM_ID")

def send_telegram_message(message):
    """Send a message to Telegram"""
    if not TELEGRAM_TOKEN or not TELEGRAM_ID:
        logging.warning("Telegram credentials not set, skipping message")
        return False
    
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_ID,
        "text": message,
        "parse_mode": "Markdown"
    }
    
    try:
        response = requests.post(url, data=payload)
        if response.status_code == 200:
            return True
        else:
            logging.error(f"Failed to send telegram message: {response.text}")
            return False
    except Exception as e:
        logging.error(f"Exception when sending telegram message: {str(e)}")
        return False

def fetch_stock_data(symbol):
    """Fetch stock data from Yahoo Finance"""
    # Using Yahoo Finance CSV URL
    end = datetime.datetime.now()
    start = end - datetime.timedelta(days=90)
    
    # Calculate Unix timestamps
    period1 = int((start - datetime.datetime(1970, 1, 1)).total_seconds())
    period2 = int((end - datetime.datetime(1970, 1, 1)).total_seconds())
    
    url = f"https://query1.finance.yahoo.com/v7/finance/download/{symbol}.NS?period1={period1}&period2={period2}&interval=1d&events=history"
    
    try:
        df = pd.read_csv(url)
        logging.debug(f"Successfully fetched stock data for {symbol}")
        return df
    except Exception as e:
        logging.error(f"Failed to fetch stock data for {symbol}: {str(e)}")
        return None

def calculate_signals(df, stock):
    """Calculate technical indicators and generate trading signals"""
    if df is None or len(df) < 20:
        logging.warning(f"Not enough data for {stock.symbol} to calculate signals")
        return None
    
    # Calculate EMA (Exponential Moving Average)
    df['EMA20'] = df['Close'].ewm(span=20).mean()
    
    # Calculate RSI (Relative Strength Index)
    delta = df['Close'].diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.rolling(window=14).mean()
    avg_loss = loss.rolling(window=14).mean()
    
    # Handle division by zero
    avg_loss = avg_loss.replace(0, 0.001)
    rs = avg_gain / avg_loss
    df['RSI'] = 100 - (100 / (1 + rs))
    
    # Get latest data point
    latest = df.iloc[-1]
    
    # Generate signal
    signal_data = None
    
    if latest['RSI'] < 30 and latest['Close'] > latest['EMA20']:
        # BUY Signal
        signal_message = f"📈 *BUY Signal* for `{stock.symbol}`\nName: {stock.name}\nPrice: ₹{latest['Close']:.2f}\nRSI: {latest['RSI']:.2f}, EMA20: {latest['EMA20']:.2f}"
        signal_data = {
            'type': 'BUY',
            'price': latest['Close'],
            'rsi': latest['RSI'],
            'ema': latest['EMA20'],
            'message': signal_message
        }
    elif latest['RSI'] > 70 and latest['Close'] < latest['EMA20']:
        # SELL Signal
        signal_message = f"📉 *SELL Signal* for `{stock.symbol}`\nName: {stock.name}\nPrice: ₹{latest['Close']:.2f}\nRSI: {latest['RSI']:.2f}, EMA20: {latest['EMA20']:.2f}"
        signal_data = {
            'type': 'SELL',
            'price': latest['Close'],
            'rsi': latest['RSI'],
            'ema': latest['EMA20'],
            'message': signal_message
        }
    
    return signal_data

def run_stock_analysis():
    """Run analysis for all active stocks and send signals"""
    stocks = Stock.query.filter_by(active=True).all()
    
    if not stocks:
        logging.warning("No active stocks found for analysis")
        return
    
    signals_sent = 0
    
    for stock in stocks:
        logging.info(f"Analyzing stock: {stock.symbol}")
        df = fetch_stock_data(stock.symbol)
        
        if df is not None and len(df) > 20:
            signal_data = calculate_signals(df, stock)
            
            if signal_data:
                # Create signal record
                signal = Signal(
                    stock_id=stock.id,
                    signal_type=signal_data['type'],
                    price=signal_data['price'],
                    rsi=signal_data['rsi'],
                    ema=signal_data['ema']
                )
                
                # Save to database
                db.session.add(signal)
                db.session.commit()
                
                # Send Telegram message
                message_sent = send_telegram_message(signal_data['message'])
                
                if message_sent:
                    signal.message_sent = True
                    db.session.commit()
                    signals_sent += 1
                    logging.info(f"Signal sent for {stock.symbol}: {signal_data['type']}")
                else:
                    logging.warning(f"Failed to send signal for {stock.symbol}")
    
    logging.info(f"Analysis complete. Sent {signals_sent} signals.")
    return signals_sent
