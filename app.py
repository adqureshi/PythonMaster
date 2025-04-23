import os
import logging
from datetime import datetime

from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase
from werkzeug.middleware.proxy_fix import ProxyFix
from apscheduler.schedulers.background import BackgroundScheduler

# Create base class for SQLAlchemy models
class Base(DeclarativeBase):
    pass

# Initialize Flask application and database
db = SQLAlchemy(model_class=Base)
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "dev_secret_key")
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

# Configure SQLAlchemy
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL", "sqlite:///stock_signals.db")
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_recycle": 300,
    "pool_pre_ping": True,
}
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# Initialize the database with the app
db.init_app(app)

# Import models and utility functions after initialization to avoid circular imports
with app.app_context():
    from models import Stock, Signal
    from stock_analyzer import run_stock_analysis
    from scheduler import initialize_scheduler

    # Create database tables
    db.create_all()
    
    # Initialize the scheduler
    scheduler = initialize_scheduler()
    
# Routes
@app.route('/')
def index():
    # Get the latest signals to display on the dashboard
    latest_signals = Signal.query.order_by(Signal.timestamp.desc()).limit(10).all()
    stock_count = Stock.query.count()
    return render_template('index.html', signals=latest_signals, stock_count=stock_count, now=datetime.now())

@app.route('/configure', methods=['GET', 'POST'])
def configure():
    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'add_stock':
            symbol = request.form.get('symbol').strip().upper()
            name = request.form.get('name').strip()
            
            # Check if stock already exists
            existing_stock = Stock.query.filter_by(symbol=symbol).first()
            if existing_stock:
                flash(f'Stock {symbol} already exists', 'warning')
            else:
                # Add new stock
                new_stock = Stock(symbol=symbol, name=name, active=True)
                db.session.add(new_stock)
                db.session.commit()
                flash(f'Stock {symbol} added successfully', 'success')
        
        elif action == 'update_stock':
            stock_id = request.form.get('stock_id')
            active = 'active' in request.form
            
            stock = Stock.query.get(stock_id)
            if stock:
                stock.active = active
                db.session.commit()
                flash(f'Stock {stock.symbol} updated', 'success')
        
        elif action == 'delete_stock':
            stock_id = request.form.get('stock_id')
            
            stock = Stock.query.get(stock_id)
            if stock:
                db.session.delete(stock)
                db.session.commit()
                flash(f'Stock {stock.symbol} deleted', 'success')
        
        elif action == 'run_analysis':
            run_stock_analysis()
            flash('Stock analysis completed', 'success')
            
        return redirect(url_for('configure'))
    
    stocks = Stock.query.all()
    return render_template('configure.html', stocks=stocks, now=datetime.now())

@app.route('/history')
def history():
    # Filter signals by stock if requested
    stock_symbol = request.args.get('stock')
    page = request.args.get('page', 1, type=int)
    
    # Query signals with pagination
    query = Signal.query.order_by(Signal.timestamp.desc())
    if stock_symbol:
        query = query.join(Stock).filter(Stock.symbol == stock_symbol)
    
    signals = query.paginate(page=page, per_page=20)
    stocks = Stock.query.all()
    
    return render_template('history.html', signals=signals, stocks=stocks, selected_stock=stock_symbol, now=datetime.now())

@app.template_filter('format_date')
def format_date(value, format='%Y-%m-%d %H:%M'):
    """Format a datetime to a readable string."""
    if value is None:
        return ""
    return value.strftime(format)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
