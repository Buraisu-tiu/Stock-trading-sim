import pandas as pd
import requests
import os
from flask import Flask, render_template, request, redirect, url_for, session
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from datetime import datetime
import random

app = Flask(__name__)

# List of API keys
api_keys = [
    'ctitlv1r01qgfbsvh1dgctitlv1r01qgfbsvh1e0',
    'ctitnthr01qgfbsvh59gctitnthr01qgfbsvh5a0',
    # Add more keys as needed
]

# Fetch the PostgreSQL database URI from the environment variable
database_uri = os.environ.get("DATABASE_URL")
if not database_uri:
    raise ValueError("No DATABASE_URL set for Flask application")

print(f"DATABASE_URL: {database_uri}")  # Print the database URI to verify
app.config['SQLALCHEMY_DATABASE_URI'] = database_uri
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    'pool_size': 10,
    'max_overflow': 20,
    'pool_timeout': 300,
    'pool_recycle': 3600,
    'connect_args': {'connect_timeout': 30}
}
app.secret_key = 'your_secret_key'
db = SQLAlchemy(app) 
migrate = Migrate(app, db)


class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)
    balance = db.Column(db.Float, nullable=False, default=1000.0)
    
    def total_account_value(self):
        total_value = self.balance
        for portfolio in self.portfolios:
            df = fetch_stock_data(portfolio.symbol)
            if df is not None:
                latest_price = df.iloc[0]['c']
                total_value += portfolio.shares * latest_price
        return round(total_value, 2)


class Portfolio(db.Model):
    __tablename__ = 'portfolios'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    symbol = db.Column(db.String(10), nullable=False)
    shares = db.Column(db.Float, nullable=False)
    purchase_price = db.Column(db.Float, nullable=False)  # Add this column
    user = db.relationship('User', backref=db.backref('portfolios', lazy=True))
    
class Transaction(db.Model):
    __tablename__ = 'transactions'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    symbol = db.Column(db.String(10), nullable=False)
    shares = db.Column(db.Float, nullable=False)
    price = db.Column(db.Float, nullable=False)
    total_amount = db.Column(db.Float, nullable=False)
    transaction_type = db.Column(db.String(4), nullable=False)  # 'BUY' or 'SELL'
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    profit_loss = db.Column(db.Float, nullable=True)  # Add this column
    user = db.relationship('User', backref=db.backref('transactions', lazy=True))

def init_db():
    with app.app_context():
        db.create_all()

@app.route('/')
def home():
    return redirect(url_for('login'))

def get_random_api_key():
    return random.choice(api_keys)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        new_user = User(username=username, password=password)
        db.session.add(new_user)
        db.session.commit()
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username, password=password).first()
        if user:
            session['user_id'] = user.id
            return redirect(url_for('dashboard'))
        else:
            return 'Invalid credentials'
    return render_template('login.html')

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user_id = session['user_id']
    user = db.session.get(User, user_id)  # Use Session.get() method
    portfolio = Portfolio.query.filter_by(user_id=user_id).all()
    return render_template('dashboard.html', user=user, portfolio=portfolio)

@app.route('/leaderboard')
def leaderboard():
    users = User.query.all()
    leaderboard_data = []
    for user in users:
        account_value = user.total_account_value()
        leaderboard_data.append({
            'username': user.username,
            'account_value': account_value
        })
    leaderboard_data.sort(key=lambda x: x['account_value'], reverse=True)
    return render_template('leaderboard.html', leaderboard=leaderboard_data)

@app.route('/history')
def transaction_history():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user_id = session['user_id']
    user = db.session.get(User, user_id)
    transactions = Transaction.query.filter_by(user_id=user_id).order_by(Transaction.timestamp.desc()).all()
    
    history = []
    for t in transactions:
        profit_loss = t.profit_loss if t.profit_loss is not None else 0.0
        history.append({
            'date': t.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
            'type': t.transaction_type,
            'symbol': t.symbol,
            'shares': t.shares,
            'price': t.price,
            'total': t.total_amount,
            'profit_loss': round(profit_loss, 2)
        })
    
    return render_template('history.html', history=history, user=user)




@app.route('/portfolio')
def view_portfolio():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user_id = session['user_id']
    user = db.session.get(User, user_id)
    portfolios = Portfolio.query.filter_by(user_id=user_id).all()
    portfolio_data = []
    total_value = 0
    for entry in portfolios:
        symbol = entry.symbol
        shares = round(entry.shares, 2)
        purchase_price = round(entry.purchase_price, 2)
        df = fetch_stock_data(symbol)
        if df is not None:
            latest_price = round(df.iloc[0]['c'], 2)
            stock_value = round(shares * latest_price, 2)
            portfolio_data.append({
                'symbol': symbol,
                'shares': shares,
                'purchase_price': purchase_price,
                'latest_price': latest_price,
                'value': stock_value
            })
            total_value += stock_value
    total_value = round(total_value, 2)
    return render_template('portfolio.html', user=user, portfolio=portfolio_data, total_value=total_value)

@app.route('/buy', methods=['GET', 'POST'])
def buy():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user_id = session['user_id']
    user = db.session.get(User, user_id)  # Use Session.get() method
    if request.method == 'POST':
        symbol = request.form['symbol']
        df = fetch_stock_data(symbol)
        if df is not None:
            latest_price = float(df.iloc[0]['c'])  # Convert to native Python float
            shares = float(request.form['shares'])  # Convert to native Python float
            cost = latest_price * shares  # No need to convert as both are already floats
            if user.balance >= cost:
                portfolio = Portfolio.query.filter_by(user_id=user_id, symbol=symbol).first()
                if portfolio:
                    portfolio.shares = float(portfolio.shares) + shares  # Convert to native Python float
                else:
                    portfolio = Portfolio(user_id=user_id, symbol=symbol, shares=shares, purchase_price=latest_price)
                    db.session.add(portfolio)
                user.balance -= cost  # No need to convert as it's already a float
                
                # Log the buy transaction
                transaction = Transaction(user_id=user_id, symbol=symbol, shares=shares, price=latest_price, total_amount=cost, transaction_type='BUY')
                db.session.add(transaction)
                
                db.session.commit()
                return redirect(url_for('dashboard'))
            else:
                return "Insufficient balance to buy shares."
        else:
            return "Failed to fetch stock data."
    return render_template('buy.html', user=user)


@app.route('/sell', methods=['GET', 'POST'])
def sell():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user_id = session['user_id']
    user = db.session.get(User, user_id)  # Use Session.get() method
    if request.method == 'POST':
        symbol = request.form['symbol']
        df = fetch_stock_data(symbol)
        if df is not None:
            latest_price = float(df.iloc[0]['c'])  # Convert to native Python float
            shares_to_sell = float(request.form['shares'])  # Convert to native Python float
            portfolio = Portfolio.query.filter_by(user_id=user_id, symbol=symbol).first()
            if portfolio and portfolio.shares >= shares_to_sell:
                proceeds = latest_price * shares_to_sell  # No need to convert as both are already floats
                portfolio.shares -= shares_to_sell  # No need to convert as it's already a float
                if portfolio.shares == 0:
                    db.session.delete(portfolio)
                user.balance += proceeds  # No need to convert as it's already a float

                # Calculate and save profit/loss for the transaction
                profit_loss = (latest_price - portfolio.purchase_price) * shares_to_sell
                transaction = Transaction(user_id=user_id, symbol=symbol, shares=shares_to_sell, price=latest_price, total_amount=proceeds, transaction_type='SELL', profit_loss=round(profit_loss, 2))
                db.session.add(transaction)
                db.session.commit()
                return redirect(url_for('dashboard'))
            else:
                return "Insufficient shares to sell."
        else:
            return "Failed to fetch stock data."
    return render_template('sell.html', user=user)


@app.route('/delete_account', methods=['GET', 'POST'])
def delete_account():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_id = session['user_id']
    user = db.session.get(User, user_id)  # Use Session.get() method

    if request.method == 'POST':
        # Delete user's portfolios
        Portfolio.query.filter_by(user_id=user_id).delete()
        
        # Delete user's transactions
        Transaction.query.filter_by(user_id=user_id).delete()

        # Delete user account
        db.session.delete(user)
        db.session.commit()
        
        session.pop('user_id', None)
        return redirect(url_for('home'))

    return render_template('confirm_delete.html', user=user)

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    return redirect(url_for('login'))

def fetch_stock_data(symbol):
    api_key = get_random_api_key()
    url = f'https://finnhub.io/api/v1/quote?symbol={symbol}&token={api_key}'
    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        if "c" in data:
            df = pd.DataFrame([{
                "t": pd.Timestamp.now(),
                "c": round(data["c"], 2),
                "h": round(data["h"], 2),
                "l": round(data["l"], 2),
                "o": round(data["o"], 2),
                "pc": round(data["pc"], 2)
            }])
            df.set_index('t', inplace=True)
            return df
        else:
            print("No results found in API response.")
            return None
    except requests.exceptions.RequestException as e:
        print(f"API request failed: {e}")
        return None

if __name__ == '__main__':
    init_db()
    app.run(debug=True)