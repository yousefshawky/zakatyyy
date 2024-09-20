import os
import json
import logging
from flask import Flask, render_template, request
from datetime import datetime
from hijri_converter import Gregorian, Hijri
from dotenv import load_dotenv
import hashlib
import aiohttp
import asyncio
import time
import requests

# Load environment variables
load_dotenv()

app = Flask(__name__)

# Configuration for local testing
IS_LOCAL = os.getenv('IS_LOCAL', 'True') == 'False'

CACHE_FILE = 'gold_price_cache.json'

MAILCHIMP_CLIENT_ID = os.getenv('MAILCHIMP_CLIENT_ID')
MAILCHIMP_CLIENT_SECRET = os.getenv('MAILCHIMP_CLIENT_SECRET')

# Configure logging
logging.basicConfig(level=logging.DEBUG if IS_LOCAL else logging.INFO)
logger = logging.getLogger(__name__)

def get_cached_gold_price():
    """Read the cached gold price from a file."""
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, 'r') as f:
            cache_data = json.load(f)
            cache_time = datetime.fromisoformat(cache_data['timestamp'])

            # Check if the cached data is from today
            if cache_time.date() == datetime.now().date():
                logger.debug("Using cached gold price.")
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
    logger.debug("Gold price cached successfully.")

def fetch_gold_price_from_api():
    """Fetch the price of 85 grams of gold from GoldAPI.io."""
    api_key = os.getenv('GOLD_API_KEY')  # Add your GoldAPI.io key in .env
    url = "https://www.goldapi.io/api/XAU/USD"  # Gold price in USD per ounce (31.1035 grams)

    headers = {
        "x-access-token": api_key,
        "Content-Type": "application/json"
    }

    try:
        response = requests.get(url, headers=headers)

        if response.status_code == 200:
            data = response.json()
            gold_price_per_ounce = data.get("price", None)  # Price of 1 ounce (31.1035 grams) of gold in USD
            if gold_price_per_ounce:
                # Convert to price of 85 grams
                grams_per_ounce = 31.1035
                gold_price_for_85_grams = (85 / grams_per_ounce) * gold_price_per_ounce

                logger.debug(f"Gold price per ounce: {gold_price_per_ounce}")
                logger.debug(f"Gold price for 85 grams: {gold_price_for_85_grams}")

                return round(gold_price_for_85_grams, 2)  # Returning the value rounded to 2 decimal places
            else:
                logger.error(f"Gold price not found in the API response: {data}")
                return None
        else:
            logger.error(f"Failed to fetch gold price. Status code: {response.status_code}, Response: {response.text}")
            return None
    except Exception as e:
        logger.error(f"Error while fetching gold price: {str(e)}")
        return None


def get_gold_price_usd():
    """Get the gold price for 85 grams from the cache or API."""
    cached_price = get_cached_gold_price()
    if cached_price is not None:
        logger.debug("Using cached gold price.")
        return cached_price  # Already the price for 85 grams of gold

    gold_price = fetch_gold_price_from_api()
    if gold_price is not None:
        cache_gold_price(gold_price)
        return gold_price  # Already the price for 85 grams of gold
    return None


def format_date_for_mailchimp(date_str):
    """Convert date from YYYY-MM-DD to the format expected by Mailchimp."""
    if not date_str:
        return ''
    try:
        date_obj = datetime.strptime(date_str, '%Y-%m-%d')
        formatted_date = date_obj.strftime('%m/%d/%Y')  # Format in MM/DD/YYYY
        logger.debug(f"Formatted date {date_str} to {formatted_date}")
        return formatted_date
    except ValueError:
        logger.error(f"Invalid date format: {date_str}")
        return ''

async def add_subscriber_to_mailchimp(email, zakat_dates):
    """Add or update subscriber in Mailchimp list with Zakat dates asynchronously."""
    start_time = time.time()  # Start timing
    subscriber_hash = hashlib.md5(email.lower().encode()).hexdigest()
    server_prefix = os.getenv('MAILCHIMP_SERVER_PREFIX', 'us1')
    list_id = os.getenv('MAILCHIMP_LIST_ID')
    url = f'https://{server_prefix}.api.mailchimp.com/3.0/lists/{list_id}/members/{subscriber_hash}'

    # Format dates correctly for Mailchimp
    merge_fields = {
        "MMERGE5": format_date_for_mailchimp(zakat_dates[0]) if len(zakat_dates) > 0 else '',
        "MMERGE6": format_date_for_mailchimp(zakat_dates[1]) if len(zakat_dates) > 1 else '',
        "MMERGE7": format_date_for_mailchimp(zakat_dates[2]) if len(zakat_dates) > 2 else '',
        "MMERGE8": format_date_for_mailchimp(zakat_dates[3]) if len(zakat_dates) > 3 else '',
        "MMERGE9": format_date_for_mailchimp(zakat_dates[4]) if len(zakat_dates) > 4 else '',
        "MMERGE10": format_date_for_mailchimp(zakat_dates[5]) if len(zakat_dates) > 5 else '',
        "MMERGE11": format_date_for_mailchimp(zakat_dates[6]) if len(zakat_dates) > 6 else '',
        "MMERGE12": format_date_for_mailchimp(zakat_dates[7]) if len(zakat_dates) > 7 else '',
        "MMERGE13": format_date_for_mailchimp(zakat_dates[8]) if len(zakat_dates) > 8 else '',
        "MMERGE14": format_date_for_mailchimp(zakat_dates[9]) if len(zakat_dates) > 9 else '',
    }

    # Log the merge fields before sending to the API
    logger.debug(f"Prepared merge fields for Mailchimp: {merge_fields}")

    # Prepare data for Mailchimp API
    data = {
        "email_address": email,
        "status_if_new": "subscribed",
        "status": "subscribed",
        "merge_fields": merge_fields,
        "tags": ["Pending Payment"]
    }

    headers = {"Authorization": f"apikey {os.getenv('MAILCHIMP_API_KEY')}"}

    # Make the real API call
    logger.info("Sending data to Mailchimp...")
    async with aiohttp.ClientSession() as session:
        async with session.put(url, json=data, headers=headers) as response:
            end_time = time.time()  # End timing
            duration = end_time - start_time
            response_text = await response.text()
            logger.info(f"Mailchimp API call duration: {duration:.2f} seconds")
            logger.info(f"Response Status Code: {response.status}")
            logger.info(f"Response Body: {response_text}")

            if response.status in [200, 204]:
                logger.info("Subscriber added or updated successfully.")
            else:
                logger.error(f"Failed to add or update subscriber: {response_text}")

def convert_gregorian_to_hijri(g_date):
    """Convert Gregorian date to Hijri date."""
    return Gregorian.fromdate(g_date).to_hijri()

def convert_hijri_to_gregorian(h_date):
    """Convert Hijri date to Gregorian date."""
    return Hijri(h_date.year, h_date.month, h_date.day).to_gregorian()


@app.route('/', methods=['GET', 'POST'])
async def index():
    # Fetch the current gold price in USD for 85 grams (Nisaab value)
    nisaab_value = get_gold_price_usd()  # Ensure this value is correct and not multiplied by 85 twice.

    next_dates = None

    if request.method == 'POST':
        # Step 1: Check which form was submitted (calculate dates or send reminders)
        if 'calculate_dates' in request.form:
            threshold_date_str = request.form.get('threshold_date')
            if threshold_date_str:
                # Step 2: Calculate Zakat dates
                threshold_date = datetime.strptime(threshold_date_str, '%Y-%m-%d')
                next_dates = calculate_zakat_dates(threshold_date)
                logger.info(f"Calculated Zakat payment dates: {next_dates}")
            else:
                logger.error("Threshold date is missing.")

        elif 'send_reminders' in request.form:
            # Step 3: Collect email and recalculate dates, then send to Mailchimp
            email = request.form.get('email')
            threshold_date_str = request.form.get('threshold_date')

            if email and threshold_date_str:
                threshold_date = datetime.strptime(threshold_date_str, '%Y-%m-%d')
                next_dates = calculate_zakat_dates(threshold_date)
                logger.info(f"Calculated Zakat payment dates for Mailchimp: {next_dates}")

                # Send email reminders to Mailchimp
                await add_subscriber_to_mailchimp(email, next_dates)
            else:
                logger.error("Email or threshold date is missing.")

    # Pass nisaab_value and dates to the template
    return render_template('index.html', nisaab_value=nisaab_value, dates=next_dates)


def calculate_zakat_dates(threshold_date):
    """Helper function to calculate the next 10 years' Zakat payment dates, starting from the first future date."""
    hijri_date = convert_gregorian_to_hijri(threshold_date)
    next_dates = []

    # Get today's date in both Gregorian and Hijri
    today = datetime.now()
    hijri_today = convert_gregorian_to_hijri(today)

    # Start checking from the threshold Hijri year
    year_counter = hijri_date.year

    # Keep looping until we find the first future Hijri date (based on month/day comparison)
    while True:
        # Construct a potential future Zakat date based on the threshold month/day, and advancing the year
        potential_hijri_date = Hijri(year_counter, hijri_date.month, hijri_date.day)
        potential_gregorian_date = potential_hijri_date.to_gregorian()

        # Check if the potential Zakat date is in the future (after today)
        if potential_gregorian_date > today:
            # We've found the first future Zakat date, so break the loop
            break

        # If not, move to the next Hijri year
        year_counter += 1

    # Add the first future Zakat date and then calculate the next 9 dates
    for i in range(10):
        future_hijri_date = Hijri(year_counter + i, hijri_date.month, hijri_date.day)
        future_gregorian_date = future_hijri_date.to_gregorian()
        formatted_date = future_gregorian_date.strftime('%Y-%m-%d')
        next_dates.append(formatted_date)

    return next_dates


if __name__ == '__main__':
    app.run(debug=IS_LOCAL)
