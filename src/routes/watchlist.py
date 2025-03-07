# src/routes/watchlist.py
from flask import Blueprint, jsonify, session, request
from utils.db import db
from services.market_data import fetch_stock_data, fetch_crypto_data, calculate_price_change
from datetime import datetime

watchlist_bp = Blueprint('watchlist', __name__)

@watchlist_bp.route('/api/add_to_watchlist', methods=['POST'])
def add_to_watchlist():
    if 'user_id' not in session:
        return jsonify({'error': 'User not authenticated'}), 401

    user_id = session['user_id']
    data = request.json
    symbol = data.get('symbol')
    asset_type = data.get('asset_type')

    if not symbol or not asset_type:
        return jsonify({'error': 'Missing symbol or asset type'}), 400

    if asset_type == 'crypto':
        symbol = f"CRYPTO:{symbol}"

    watchlist_ref = db.collection('watchlists').document(user_id)
    watchlist_doc = watchlist_ref.get()

    if watchlist_doc.exists:
        watchlist = watchlist_doc.to_dict()
        symbols = watchlist.get('symbols', [])
        if symbol not in symbols:
            symbols.append(symbol)
            watchlist_ref.update({'symbols': symbols})
    else:
        watchlist_ref.set({'symbols': [symbol]})

    return jsonify({'success': True, 'message': 'Added to watchlist'})

def fetch_watchlist(user_id: str) -> list[dict]:
    try:
        watchlist_ref = db.collection('watchlists').document(user_id)
        watchlist_doc = watchlist_ref.get()

        if not watchlist_doc.exists:
            return []

        watchlist_data = watchlist_doc.to_dict()
        symbols = watchlist_data.get('symbols', [])
        processed_items = []

        for symbol in symbols:
            asset_type = 'crypto' if symbol.startswith('CRYPTO:') else 'stock'
            symbol_name = symbol.replace('CRYPTO:', '')

            try:
                price_data = (fetch_crypto_data(symbol_name) if asset_type == 'crypto' 
                            else fetch_stock_data(symbol_name))

                if not price_data or 'error' in price_data:
                    continue

                current_price = price_data.get('close') or price_data.get('price', 0)
                prev_price = price_data.get('prev_close', current_price)

                change_pct, change_str = calculate_price_change(current_price, prev_price)

                processed_items.append({
                    'symbol': symbol_name,
                    'asset_type': asset_type,
                    'current_price': f"${current_price:.2f}",
                    'price_change': change_str,
                    'change_percentage': change_pct,
                    'added_date': watchlist_data.get('added_date', datetime.utcnow()),
                    'notes': watchlist_data.get('notes', ''),
                    'alert_price': watchlist_data.get('alert_price')
                })

            except Exception as e:
                continue

        return sorted(processed_items, 
                     key=lambda x: abs(x['change_percentage']), 
                     reverse=True)

    except Exception as e:
        return []