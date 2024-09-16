import os
import requests
import json
from flask import Flask, render_template, request
from datetime import datetime, timedelta
from hijri_converter import Gregorian, Hijri
from dotenv import load_dotenv
import hashlib

# Load environment variables
load_dotenv()

app = Flask(__name__)

CACHE_FILE = 'gold_price_cache.json'

MAILCHIMP_CLIENT_ID = os.getenv('MAILCHIMP_CLIENT_ID')
MAILCHIMP_CLIENT_SECRET = os.getenv('MAILCHIMP_CLIENT_SECRET')


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
    # Disable API calls by returning a fixed value
    print("Gold API calls are currently disabled for testing.")
    return 6863.98  # Example static value for testing

    # Uncomment the lines below to re-enable API calls
    # api_key = os.getenv('GOLD_API_KEY')
    # url = "https://www.goldapi.io/api/XAU/USD"

    # try:
    #     print(f"Fetching gold price from GoldAPI.io...")  # Debugging line
    #     headers = {'x-access-token': api_key, 'Content-Type': 'application/json'}
    #     response = requests.get(url, headers=headers)
    #     response.raise_for_status()  # Raise an exception for HTTP errors

    #     data = response.json()

    #     # Extract the gold price from the response
    #     gold_price_per_ounce_usd = data['price']
    #     gold_price_per_gram_usd = gold_price_per_ounce_usd / 31.1035  # 1 ounce = 31.1035 grams
    #     nisaab_value = 85 * gold_price_per_gram_usd
    #     return round(nisaab_value, 2)  # Round to 2 decimal places

    # except Exception as e:
    #     print(f"An error occurred while fetching the gold price: {e}")
    #     return None


def get_gold_price_usd():
    """Get the gold price from the cache or use a static value for testing."""
    cached_price = get_cached_gold_price()
    if cached_price is not None:
        print("Using cached gold price.")
        return cached_price

    # Use a fixed value to avoid wasting API quota during testing
    gold_price = fetch_gold_price_from_api()
    if gold_price is not None:
        cache_gold_price(gold_price)
    return gold_price


def add_subscriber_to_mailchimp(email, zakat_dates):
    """Add or update subscriber in Mailchimp list with Zakat dates."""
    subscriber_hash = hashlib.md5(email.lower().encode()).hexdigest()
    server_prefix = os.getenv('MAILCHIMP_SERVER_PREFIX')  # e.g., 'us1'
    list_id = os.getenv('MAILCHIMP_LIST_ID')
    url = f'https://{server_prefix}.api.mailchimp.com/3.0/lists/{list_id}/members/{subscriber_hash}'

    # Ensure all dates are properly formatted
    merge_fields = {
        "MMERGE5": zakat_dates[0] if zakat_dates[0] else '',
        "MMERGE6": zakat_dates[1] if zakat_dates[1] else '',
        "MMERGE7": zakat_dates[2] if zakat_dates[2] else '',
        "MMERGE8": zakat_dates[3] if zakat_dates[3] else '',
        "MMERGE9": zakat_dates[4] if zakat_dates[4] else '',
        "MMERGE10": zakat_dates[5] if zakat_dates[5] else '',
        "MMERGE11": zakat_dates[6] if zakat_dates[6] else '',
        "MMERGE12": zakat_dates[7] if zakat_dates[7] else '',
        "MMERGE13": zakat_dates[8] if zakat_dates[8] else '',
        "MMERGE14": zakat_dates[9] if zakat_dates[9] else '',
    }

    # Debugging: Print merge fields
    print(f"Merge fields being sent to Mailchimp: {merge_fields}")

    # Prepare data for Mailchimp API
    data = {
        "email_address": email,
        "status_if_new": "subscribed",
        "status": "subscribed",
        "merge_fields": merge_fields,  # Include only the valid merge fields
        "tags": ["Pending Payment"]
    }

    headers = {"Authorization": f"apikey {os.getenv('MAILCHIMP_API_KEY')}"}

    # Debugging: Print the data payload
    print(f"Sending data to Mailchimp: {data}")

    response = requests.put(url, json=data, headers=headers)

    # Debugging: Print response from Mailchimp
    print(f"Response Status Code: {response.status_code}")
    print(f"Response Body: {response.text}")

    if response.status_code in [200, 204]:
        print("Subscriber added or updated successfully.")
    else:
        print(f"Failed to add or update subscriber: {response.text}")


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
        email = request.form['email']  # Ensure the form collects the user's email
        threshold_date_str = request.form['threshold_date']
        threshold_date = datetime.strptime(threshold_date_str, '%Y-%m-%d')

        # Convert to Hijri
        hijri_date = convert_gregorian_to_hijri(threshold_date)
        next_dates = []

        # Calculate next 10 years' payment dates in Hijri
        for i in range(10):
            next_hijri_date = Hijri(hijri_date.year + i, hijri_date.month, hijri_date.day)
            next_gregorian_date = next_hijri_date.to_gregorian()

            # Format the date to dd/mm/yyyy
            formatted_date = next_gregorian_date.strftime('%d/%m/%Y')
            next_dates.append(formatted_date)

        # Add or update subscriber in Mailchimp
        add_subscriber_to_mailchimp(email, next_dates)

    return render_template('index.html', nisaab_value=nisaab_value, dates=next_dates)


@app.route('/oauth/callback')
def oauth_callback():
    """Handle the OAuth callback from Mailchimp."""
    auth_code = request.args.get('code')
    token_url = 'https://login.mailchimp.com/oauth2/token'
    redirect_uri = 'https://zakat-reminder.fly.dev/oauth/callback'

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
        print('Access Token:', access_token)
        return "Successfully authenticated with Mailchimp!"
    else:
        return f"Failed to authenticate: {response.text}"


if __name__ == '__main__':
    app.run(debug=True)
