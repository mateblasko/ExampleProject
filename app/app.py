import logging
import os
import ccxt.async_support
from flask import Flask
from dotenv import load_dotenv
from datetime import datetime, UTC, timedelta
import ccxt
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from psycopg2 import IntegrityError
from shared.models import BaseVolume, Coin, OpenInterest, Price, db
import asyncio

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def create_app():
    app = Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL')
    db.init_app(app)

    with app.app_context():
        db.create_all()

    return app

app = create_app()

exchange_options = {
    'options': {
        'defaultType': 'future',  # Refers to perpetual futures
    }
}

exchange = ccxt.binance(exchange_options)

def init_database_coins(tickers):
    try:
        for ticker in tickers:
            existing_coin = Coin.query.filter_by(symbol=ticker).first()
            if not existing_coin:
                coin = Coin(symbol=ticker)
                db.session.add(coin)
        db.session.commit()
        logger.info("Symbols initialized successfully")
    except IntegrityError as e:
        db.session.rollback()
        logger.error(f"Database init failed: {e}")

def update_database(entries):
    try:
        db.session.add_all(entries)
        db.session.commit()
        logger.info("Data committed to the database successfully.")
    except IntegrityError as e:
        db.session.rollback()
        logger.error(f"Database commit failed: {e}")

def get_last_from_db(model,symbol):
    return model.query.filter_by(coin_symbol=symbol).order_by(model.timestamp.desc()).first()

def fetch_all_coins():
    with app.app_context():
        try:
            symbols = []
            result = exchange.load_markets()
            for key in result.keys():
                market = result[key]
                if market['swap']:
                    symbols.append(key)
            init_database_coins(symbols)
        except Exception as e:
            logger.error(f"Failed to fetch all symbols: {e}")

def fetch_top_symbols():
    try:
        fetch_all_coins()
        tickers = sorted(exchange.fetch_tickers().values(), key=lambda x: x.get('baseVolume', 0), reverse=True)
        top_tickers = tickers[:20]
        top_tickers = [ticker['symbol'] for ticker in top_tickers]
        logger.info("Updated top 20 symbols successfully")
    except Exception as e:
        logger.error(f"Failed to update top symbols: {e}")
    return top_tickers

top_tickers = fetch_top_symbols()

async def fetch_volume():
    volume_data = []
    try:
        tasks = []
        for symbol in top_tickers:
            tasks.append(fetch_volume_for_symbol(symbol))
        results = await asyncio.gather(*tasks)
        current_timestamp = datetime.now(UTC)
        for result, symbol in results:
            if result:
                last_entry = (get_last_from_db(BaseVolume,symbol))
                if last_entry is not None:
                    last_timestamp = last_entry.timestamp
                    time_difference = current_timestamp - last_timestamp
                    if time_difference <= timedelta(hours=1):
                        current_volume = float(result[1][5])
                        last_volume = float(last_entry.volume)
                        new_percentage_change = ((current_volume - last_volume) / last_volume) * 100
                    else:
                        new_percentage_change = 0
                else:
                    new_percentage_change = 0
                base_volume_entry = BaseVolume(
                    coin_symbol = symbol,
                    timestamp = current_timestamp,
                    volume = result[1][5],
                    percentage_change = new_percentage_change
                )
                volume_data.append(base_volume_entry)
            else:
                logger.error(f"Empty results data: {symbol} {result}")
        update_database(volume_data)

    except Exception as e:
        logger.error(f"Failed to fetch volume data: {e}")

async def fetch_volume_for_symbol(symbol):
    async_exchange = ccxt.async_support.binance(exchange_options) 
    try:
        timestamp =  int((datetime.now() - timedelta(minutes=30)).timestamp() * 1000)
        result = await async_exchange.fetch_ohlcv(symbol,'15m',timestamp)
        if 'msg' in result:
            return None
        return result, symbol
    except Exception as e:
        logger.error(f"Failed to fetch volume data from exchange: {symbol} {result} {e}")
    finally:
        await async_exchange.close()

async def fetch_open_interest():
    open_interest_data = []
    try:
        tasks = []
        for symbol in top_tickers:
            tasks.append(fetch_open_interest_for_symbol(symbol))
        results = await asyncio.gather(*tasks)
        current_timestamp = datetime.now(UTC)
        for result in results:
            if result:
                last_entry = (get_last_from_db(OpenInterest,result['symbol']))
                if last_entry is not None:
                    last_timestamp = last_entry.timestamp
                    time_difference = current_timestamp - last_timestamp
                    if time_difference <= timedelta(hours=1):
                        current_open_interest = float(result['openInterestAmount'])
                        last_open_interest = float(last_entry.open_interest)
                        new_percentage_change = ((current_open_interest - last_open_interest) / last_open_interest) * 100
                    else:
                        new_percentage_change = 0
                else:
                    new_percentage_change = 0
                new_open_interest_entry = OpenInterest(
                    coin_symbol = result['symbol'],
                    timestamp = current_timestamp,
                    open_interest = result['openInterestAmount'],
                    percentage_change = new_percentage_change
                )
            open_interest_data.append(new_open_interest_entry)
        update_database(open_interest_data)

    except Exception as e:
        logger.error(f"Failed to fetch open interest data: {e}")
    return open_interest_data

async def fetch_open_interest_for_symbol(symbol):
    async_exchange = ccxt.async_support.binance(exchange_options) 
    try:
        result = await async_exchange.fetch_open_interest(symbol)
        if 'msg' in result:
            return None
        return result
    except Exception as e:
        logger.error(f"Failed to fetch open interest data from exchange: {symbol} {result} {e}")
    finally:
        await async_exchange.close()

async def fetch_prices():
    try:
        price_data = []
        results = await fetch_prices_for_symbol(top_tickers)
        current_timestamp = datetime.now(UTC)
        for result in results.values():
            price_entry = Price(
                coin_symbol = result['symbol'],
                timestamp = current_timestamp,
                price=result['last']
            )
            price_data.append(price_entry)
        update_database(price_data)

    except Exception as e:
        logger.error(f"Failed to fetch prices: {e}")

async def fetch_prices_for_symbol(symbols):
    async_exchange = ccxt.async_support.binance(exchange_options) 
    try:
        result = await async_exchange.fetch_tickers(symbols)
        if 'msg' in result:
            logger.error(f"Failed to fetch prices from exchange: {symbols} {result['msg']} {e}")
            return None
        return result
    except Exception as e:
        logger.error(f"Failed to fetch prices from exchange: {symbols} {e}")
    finally:
        await async_exchange.close()

def fetch_volume_job():
    with app.app_context():
        asyncio.run(fetch_volume())

def fetch_open_interest_job():
    with app.app_context():
        asyncio.run(fetch_open_interest())

def fetch_prices_job():
    with app.app_context():
        asyncio.run(fetch_prices())

if __name__ == "__main__":
    fetch_crypto_prices_trigger = CronTrigger(second='0')
    fetch_top_symbols_trigger = CronTrigger(minute='0')
    fetch_open_interest_trigger = CronTrigger(minute='1, 16, 31, 46')
    fetch_volume_trigger = CronTrigger(minute='1, 16, 31, 46') 
    scheduler = BackgroundScheduler()
    scheduler.add_job(fetch_prices_job, fetch_crypto_prices_trigger)
    scheduler.add_job(fetch_top_symbols, fetch_top_symbols_trigger)
    scheduler.add_job(fetch_open_interest_job, fetch_open_interest_trigger)
    scheduler.add_job(fetch_volume_job, fetch_volume_trigger)
    scheduler.start()
    logger.info("Scheduler started successfully")
    app.run(debug=True, host='0.0.0.0', port=5000, use_reloader=False)