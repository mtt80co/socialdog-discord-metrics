import os
import requests
import json
import logging
import schedule
import threading
import time

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
SCRAPFLY_API_KEY = os.getenv('SCRAPFLY_API_KEY')
X_COM_PROFILE_URL = os.getenv('X_COM_PROFILE_URL')
DISCORD_WEBHOOK_URL = os.getenv('DISCORD_WEBHOOK_URL')

# Validate environment variables
if not all([SCRAPFLY_API_KEY, X_COM_PROFILE_URL, DISCORD_WEBHOOK_URL]):
    logger.error("Missing required environment variables")
    exit(1)

def scrape_x_com():
    """Scrape X.com metrics using Scrapfly API."""
    try:
        headers = {
            'Authorization': f'Bearer {SCRAPFLY_API_KEY}',
            'Content-Type': 'application/json',
        }
        params = {
            'url': X_COM_PROFILE_URL,
            'render_js': 'true',
            'country_code': 'US',
        }
        
        logger.info("Attempting to scrape X.com metrics...")
        response = requests.get('https://api.scrapfly.io/scrape', headers=headers, params=params)
        
        if response.status_code == 200:
            data = response.json()
            
            # Extract metrics with default values
            impressions = data.get('impressions', 0)
            interactions = data.get('interactions', 0)
            followers = data.get('followers', 0)
            profile_clicks = data.get('profile_clicks', 0)
            
            logger.info(f"Scraped metrics: Impressions={impressions}, Interactions={interactions}")
            return impressions, interactions, followers, profile_clicks
        else:
            logger.error(f"Scraping failed: {response.status_code} - {response.text}")
            return None, None, None, None
    
    except requests.RequestException as e:
        logger.error(f"Request error: {e}")
        return None, None, None, None
    except json.JSONDecodeError as e:
        logger.error(f"JSON parsing error: {e}")
        return None, None, None, None

def send_to_discord(impressions, interactions, followers, profile_clicks):
    """Send scraped metrics to Discord webhook."""
    if any(metric is None for metric in [impressions, interactions, followers, profile_clicks]):
        logger.warning("No metrics to send")
        return
    
    try:
        message = {
            'content': f"📊 X.com Metrics:\n"
                       f"• Impressions: {impressions}\n"
                       f"• Interactions: {interactions}\n"
                       f"• Followers: {followers}\n"
                       f"• Profile Clicks: {profile_clicks}"
        }
        
        logger.info("Sending metrics to Discord...")
        response = requests.post(DISCORD_WEBHOOK_URL, json=message)
        
        if response.status_code == 204:
            logger.info("Successfully sent metrics to Discord")
        else:
            logger.error(f"Discord webhook failed: {response.status_code} - {response.text}")
    
    except requests.RequestException as e:
        logger.error(f"Error sending to Discord: {e}")

def metrics_job():
    """Job to scrape X.com metrics and send to Discord."""
    logger.info("Starting metrics collection job...")
    impressions, interactions, followers, profile_clicks = scrape_x_com()
    send_to_discord(impressions, interactions, followers, profile_clicks)
    logger.info("Metrics job completed")

def run_scheduler():
    """Run scheduler to periodically collect and send metrics."""
    logger.info("Starting scheduler...")
    metrics_job()  # Run immediately on startup
    
    # Schedule job every hour
    schedule.every(1).hour.do(metrics_job)
    
    while True:
        schedule.run_pending()
        time.sleep(60)

if __name__ == '__main__':
    # Start scheduler in a separate thread
    scheduler_thread = threading.Thread(target=run_scheduler)
    scheduler_thread.daemon = True
    scheduler_thread.start()
    
    # Start Flask or simple web server to keep app alive
    from flask import Flask
    app = Flask(__name__)
    
    @app.route('/')
    def home():
        return "X.com Metrics Scraper is running"
    
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', 10000)))