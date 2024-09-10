import os
import requests
import json
from flask import Flask, render_template, request
from datetime import datetime, timedelta
from hijri_converter import Gregorian, Hijri
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = Flask(__name__)

CACHE_FILE = 'gold_price_cache.json'


def get_cached_gold_price():
    """Read the cached gold price from a file."""
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, 'r') as f:
            cache_data = json.load(f)
            cache_time = datetime.fromisoformat(cache_data['timestamp'])

            # Check if the cached data is from today
            if cache_time.date() == datetime.now().date():
                return cache_data['gold_price']
    return None


def cache_gold_price(price):
    """Save the gold price to a cache file with a timestamp."""
    with open(CACHE_FILE, 'w') as f:
        cache_data = {
            'timestamp': datetime.now().isoformat(),
            'gold_price': price
        }
        json.dump(cache_data, f)


def fetch_gold_price_from_api():
    """Fetch the gold price from GoldAPI.io."""
    api_key = os.getenv('GOLD_API_KEY')
    url = "https://www.goldapi.io/api/XAU/USD"

    try:
        print(f"Fetching gold price from GoldAPI.io...")  # Debugging line
        headers = {'x-access-token': api_key, 'Content-Type': 'application/json'}
        response = requests.get(url, headers=headers)
        response.raise_for_status()  # Raise an exception for HTTP errors

        data = response.json()

        # Extract the gold price from the response
        gold_price_per_ounce_usd = data['price']
        gold_price_per_gram_usd = gold_price_per_ounce_usd / 31.1035  # 1 ounce = 31.1035 grams
        nisaab_value = 85 * gold_price_per_gram_usd
        return round(nisaab_value, 2)  # Round to 2 decimal places

    except Exception as e:
        print(f"An error occurred while fetching the gold price: {e}")
        return None


def get_gold_price_usd():
    """Get the gold price from the cache or fetch from the API if needed."""
    cached_price = get_cached_gold_price()
    if cached_price is not None:
        print("Using cached gold price.")
        return cached_price

    # If no cached price is found or it's outdated, fetch from the API
    gold_price = fetch_gold_price_from_api()
    if gold_price is not None:
        cache_gold_price(gold_price)
    return gold_price


# Functions to convert dates
def convert_gregorian_to_hijri(g_date):
    """Convert Gregorian date to Hijri date."""
    return Gregorian.fromdate(g_date).to_hijri()


def convert_hijri_to_gregorian(h_date):
    """Convert Hijri date to Gregorian date."""
    return Hijri(h_date.year, h_date.month, h_date.day).to_gregorian()


@app.route('/', methods=['GET', 'POST'])
def index():
    nisaab_value = get_gold_price_usd()  # Fetch the Nisaab value in USD
    next_dates = None

    if request.method == 'POST':
        threshold_date_str = request.form['threshold_date']
        threshold_date = datetime.strptime(threshold_date_str, '%Y-%m-%d')

        # Convert to Hijri
        hijri_date = convert_gregorian_to_hijri(threshold_date)
        next_dates = []

        # Calculate next 10 years' payment dates in Hijri
        for i in range(10):
            next_hijri_date = Hijri(hijri_date.year + i, hijri_date.month, hijri_date.day)
            next_gregorian_date = next_hijri_date.to_gregorian()
            next_dates.append(next_gregorian_date)

    return render_template('index.html', nisaab_value=nisaab_value, dates=next_dates)


if __name__ == '__main__':
    app.run(debug=True)
