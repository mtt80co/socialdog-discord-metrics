import os
import requests
import json
import logging
import schedule
import threading
import time
from typing import List, Dict, Optional
from flask import Flask
from bs4 import BeautifulSoup

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
SCRAPFLY_API_KEY = os.getenv('SCRAPFLY_API_KEY')
X_COM_PROFILE_URL = os.getenv('X_COM_PROFILE_URL', 'https://x.com/Meteo_Kingdom')
DISCORD_WEBHOOK_URL = os.getenv('DISCORD_WEBHOOK_URL')

# Validate environment variables
if not all([SCRAPFLY_API_KEY, X_COM_PROFILE_URL, DISCORD_WEBHOOK_URL]):
    logger.error("Missing required environment variables")
    exit(1)

class Scraper:
    def __init__(self, api_key: str, profile_url: str):
        self.api_key = api_key
        self.profile_url = profile_url

    def scrape_profile(self) -> Optional[str]:
        """Scrape the X.com profile page to extract all post data."""
        try:
            headers = {
                'Authorization': f'Bearer {self.api_key}',
                'Content-Type': 'application/json',
            }
            params = {
                'url': self.profile_url,
                'render_js': 'true',
                'wait_for': '5s',  # Allow time for JavaScript to load
                'country_code': 'US',
            }

            logger.info("Attempting to scrape X.com profile...")
            response = requests.get('https://api.scrapfly.io/scrape', headers=headers, params=params, timeout=30)

            if response.status_code == 200:
                logger.info("Scraping successful!")
                # Log response for debugging
                logger.info(f"Response content: {response.text[:500]}...")
                return response.text
            else:
                logger.error(f"Scraping failed: {response.status_code} - {response.text}")
                return None

        except requests.RequestException as e:
            logger.error(f"Request error: {e}")
            return None

    def extract_posts(self, html: str) -> List[Dict]:
        """Extract all posts from the scraped HTML."""
        soup = BeautifulSoup(html, 'html.parser')
        posts = []

        try:
            # Adjust selectors based on actual HTML structure
            post_elements = soup.find_all('div', class_='post-class')  # Adjust the class name
            for post in post_elements:
                posts.append({
                    'content': post.get_text(strip=True),
                    'impressions': post.get('data-impressions', 0),  # Example of extracting metadata
                    'engagements': post.get('data-engagements', 0),  # Example of extracting metadata
                })

            logger.info(f"Extracted {len(posts)} posts.")
            return posts

        except Exception as e:
            logger.error(f"Error extracting posts: {e}")
            return []

def send_to_discord(posts: List[Dict]):
    """Send all scraped posts to Discord webhook."""
    if not posts:
        logger.warning("No posts to send")
        return

    for post in posts:
        try:
            message = {
                'content': f"📄 Post Analytics:\n"
                           f"• Content: {post['content']}\n"
                           f"• Impressions: {post.get('impressions', 0)}\n"
                           f"• Engagements: {post.get('engagements', 0)}"
            }

            logger.info("Sending post analytics to Discord...")
            response = requests.post(DISCORD_WEBHOOK_URL, json=message)

            if response.status_code == 204:
                logger.info("Successfully sent post analytics to Discord")
            else:
                logger.error(f"Discord webhook failed: {response.status_code} - {response.text}")

        except requests.RequestException as e:
            logger.error(f"Error sending to Discord: {e}")

def metrics_job(scraper: Scraper):
    """Job to scrape all posts and send them to Discord."""
    logger.info("Starting metrics collection job...")
    html = scraper.scrape_profile()
    if html:
        posts = scraper.extract_posts(html)
        send_to_discord(posts)
    logger.info("Metrics job completed")

def run_scheduler(scraper: Scraper):
    """Run scheduler to periodically scrape all posts and send metrics."""
    logger.info("Starting scheduler...")
    # Execute the job immediately
    metrics_job(scraper)

    # Schedule job every hour
    schedule.every(1).hour.do(metrics_job, scraper=scraper)

    while True:
        schedule.run_pending()
        time.sleep(60)

if __name__ == '__main__':
    scraper = Scraper(api_key=SCRAPFLY_API_KEY, profile_url=X_COM_PROFILE_URL)

    # Start scheduler in a separate thread
    scheduler_thread = threading.Thread(target=run_scheduler, args=(scraper,))
    scheduler_thread.daemon = True
    scheduler_thread.start()

    # Start Flask web server to keep app alive
    app = Flask(__name__)

    @app.route('/')
    def home():
        return "X.com Metrics Scraper is running"

    app.run(host='0.0.0.0', port=int(os.getenv('PORT', 10000)))
