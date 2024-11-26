import os
import logging
from dotenv import load_dotenv
from flask import Flask, jsonify
from sqlalchemy import desc
from shared.models import BaseVolume, Coin, OpenInterest, Price, db

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def create_app():
    app = Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL')
    db.init_app(app)

    return app

app = create_app()

@app.route('/api/interestingcoins', methods=['GET'])
def get_interesting_coins():
    try:
        max_oi_timestamp = db.session.query(db.func.max(OpenInterest.timestamp)).scalar()

        recent_open_interests = db.session.query(OpenInterest).filter(OpenInterest.timestamp == max_oi_timestamp, OpenInterest.percentage_change > 2).all()

        oi_symbols = {oi.coin_symbol for oi in recent_open_interests}

        interesting_vol_symbols = set()

        for oi_symbol in oi_symbols:
            recent_volumes = db.session.query(BaseVolume).filter_by(coin_symbol=oi_symbol).order_by(
                desc(BaseVolume.timestamp)
            ).limit(4).all()
            if len(recent_volumes) == 4:
                percentage_change_sum = sum(vol.percentage_change for vol in recent_volumes)
                if percentage_change_sum > 10:
                    interesting_vol_symbols.add(oi_symbol)

        interesting_symbols = oi_symbols.intersection(interesting_vol_symbols)

        response_data = [{"symbol": symbol} for symbol in interesting_symbols]
        return jsonify(response_data)
    except Exception as e:
        logger.error(f"Error in get_interesting_coins: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/coins', methods=['GET'])
def get_coins():
    try:
        coins = Coin.query.all()
        return jsonify([coin.symbol for coin in coins])
    except Exception as e:
        logger.error(f"Error in get_coins: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/prices/<string:symbol>', methods=['GET'])
def get_price(symbol):
    try:
        prices = Price.query.filter_by(coin_symbol=symbol).all()
        return jsonify([{"timestamp": price.timestamp, "price": price.price} for price in prices])
    except Exception as e:
        logger.error(f"Error in get_price for {symbol}: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/prices', methods=['GET'])
def get_prices():
    try:
        prices = Price.query.all()
        return jsonify([{"symbol": price.coin_symbol ,"timestamp": price.timestamp, "price": price.price} for price in prices])
    except Exception as e:
        logger.error(f"Error in get_prices: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/open_interest/<string:symbol>', methods=['GET'])
def get_open_interest(symbol):
    try:
        open_interest = OpenInterest.query.filter_by(coin_symbol=symbol).all()
        return jsonify([{"timestamp": oi.timestamp, "open_interest": oi.open_interest, "percentage_change": oi.percentage_change} for oi in open_interest])
    except Exception as e:
        logger.error(f"Error in get_open_interest for {symbol}: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/open_interest', methods=['GET'])
def get_open_interests():
    try:
        open_interest = OpenInterest.query.all()
        return jsonify([{"symbol": oi.coin_symbol ,"timestamp": oi.timestamp, "open_interest": oi.open_interest, "percentage_change": oi.percentage_change} for oi in open_interest])
    except Exception as e:
        logger.error(f"Error in get_open_interests: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/base_volume/<string:symbol>', methods=['GET'])
def get_base_volume(symbol):
    try:
        base_volume = BaseVolume.query.filter_by(coin_symbol=symbol).all()
        return jsonify([{"timestamp": vol.timestamp, "volume": vol.volume, "percentage_change": vol.percentage_change} for vol in base_volume])
    except Exception as e:
        logger.error(f"Error in get_base_volume for {symbol}: {str(e)}")
        return jsonify({"error": str(e)}), 500
    
@app.route('/api/base_volume', methods=['GET'])
def get_base_volumes():
    try:
        base_volume = BaseVolume.query.all()
        return jsonify([{"symbol": vol.coin_symbol ,"timestamp": vol.timestamp, "volume": vol.volume, "percentage_change": vol.percentage_change} for vol in base_volume])
    except Exception as e:
        logger.error(f"Error in get_base_volumes: {str(e)}")
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(debug=True,host='0.0.0.0', port=5001, use_reloader=False)