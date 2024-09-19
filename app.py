import os
import json
import logging
from flask import Flask, render_template, request, redirect, url_for
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
IS_LOCAL = os.getenv('IS_LOCAL', 'True') == 'False'  # Set to 'False' when deploying to Fly.io

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
    """Fetch the gold price from GoldAPI.io."""
    api_key = os.getenv('GOLD_API_KEY')  # Add your GoldAPI.io key in .env
    url = "https://www.goldapi.io/api/XAU/USD"  # Gold price in USD

    headers = {
        "x-access-token": api_key,
        "Content-Type": "application/json"
    }

    try:
        response = requests.get(url, headers=headers)

        if response.status_code == 200:
            data = response.json()
            gold_price = data.get("price", None)
            if gold_price:
                logger.debug(f"Fetched gold price: {gold_price}")
                return gold_price
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
    """Get the gold price from the cache or use a static value for testing."""
    cached_price = get_cached_gold_price()
    if cached_price is not None:
        logger.debug("Using cached gold price.")
        return cached_price

    gold_price = fetch_gold_price_from_api()
    if gold_price is not None:
        cache_gold_price(gold_price)
    return gold_price

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
    nisaab_value = get_gold_price_usd()  # Fetch the Nisaab value in USD
    next_dates = None

    if request.method == 'POST' and 'calculate_dates' in request.form:
        # Step 1: Calculate Zakat dates
        threshold_date_str = request.form['threshold_date']
        threshold_date = datetime.strptime(threshold_date_str, '%Y-%m-%d')

        # Convert to Hijri
        hijri_date = convert_gregorian_to_hijri(threshold_date)
        next_dates = []

        # Calculate next 10 years' payment dates in Hijri
        for i in range(10):
            next_hijri_date = Hijri(hijri_date.year + i, hijri_date.month, hijri_date.day)
            next_gregorian_date = next_hijri_date.to_gregorian()
            formatted_date = next_gregorian_date.strftime('%Y-%m-%d')
            next_dates.append(formatted_date)

        logger.info(f"Calculated Zakat payment dates: {next_dates}")

    elif request.method == 'POST' and 'send_reminders' in request.form:
        # Step 3: Collect email and recalculate dates, then send to Mailchimp
        email = request.form['email']
        threshold_date_str = request.form['threshold_date']
        threshold_date = datetime.strptime(threshold_date_str, '%Y-%m-%d')

        # Convert to Hijri
        hijri_date = convert_gregorian_to_hijri(threshold_date)
        next_dates = []

        # Calculate next 10 years' payment dates in Hijri
        for i in range(10):
            next_hijri_date = Hijri(hijri_date.year + i, hijri_date.month, hijri_date.day)
            next_gregorian_date = next_hijri_date.to_gregorian()
            formatted_date = next_gregorian_date.strftime('%Y-%m-%d')
            next_dates.append(formatted_date)

        logger.info(f"Calculated Zakat payment dates for Mailchimp: {next_dates}")

        # Send to Mailchimp
        if email:
            await add_subscriber_to_mailchimp(email, next_dates)

    return render_template('index.html', nisaab_value=nisaab_value, dates=next_dates)

@app.route('/oauth/callback')
def oauth_callback():
    """Handle the OAuth callback from Mailchimp."""
    auth_code = request.args.get('code')
    token_url = 'https://login.mailchimp.com/oauth2/token'
    redirect_uri = 'http://localhost:5000/oauth/callback' if IS_LOCAL else 'https://zakat-reminder.fly.dev/oauth/callback'

    data = {
        'grant_type': 'authorization_code',
        'client_id': MAILCHIMP_CLIENT_ID,
        'client_secret': MAILCHIMP_CLIENT_SECRET,
        'redirect_uri': redirect_uri,
        'code': auth_code
    }

    # Make the request to get the access token
    response = requests.post(token_url, data=data)

    # Check for a successful response
    if response.status_code == 200:
        token_info = response.json()
        access_token = token_info.get('access_token')
        logger.info('Access Token:', access_token)
        return "Successfully authenticated with Mailchimp!"
    else:
        logger.error(f"Failed to authenticate: {response.text}")
        return f"Failed to authenticate: {response.text}"

if __name__ == '__main__':
    app.run(debug=IS_LOCAL)
