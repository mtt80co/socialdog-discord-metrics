import os
import requests
import logging
import schedule
import threading
import time
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

    def scrape_profile(self) -> str:
        """Scrape the X.com profile page to extract HTML."""
        try:
            headers = {
                'Authorization': f'Bearer {self.api_key}',
                'Content-Type': 'application/json',
            }
            params = {
                'url': self.profile_url,
                'render_js': 'true',
                'wait_for': '10s',  # Increased wait time
                'country_code': 'US',
            }

            logger.info("Attempting to scrape X.com profile...")
            response = requests.get('https://api.scrapfly.io/scrape', headers=headers, params=params, timeout=60)

            if response.status_code == 200:
                logger.info("Scraping successful!")
                return response.text
            else:
                logger.error(f"Scraping failed: {response.status_code} - {response.text}")
                return ""

        except requests.RequestException as e:
            logger.error(f"Request error: {e}")
            return ""

    def extract_posts(self, html: str):
        """Extract all posts from the scraped HTML."""
        soup = BeautifulSoup(html, 'html.parser')
        posts = []

        try:
            # Updated selectors to target X.com post elements
            post_elements = soup.select('div[data-testid="cellInnerDiv"]')
            
            if not post_elements:
                logger.warning("No posts found. Sending full HTML to Discord for debugging.")
                requests.post(DISCORD_WEBHOOK_URL, json={
                    "content": f"DEBUG: No posts found. HTML length: {len(html)} chars. First 500 chars:\n```\n{html[:500]}\n```"
                })
                return []

            for post in post_elements:
                # Extract text content
                text_element = post.select_one('div[lang]')
                content = text_element.get_text(strip=True) if text_element else "No content"

                # Try to extract engagement metrics (may require manual parsing)
                posts.append({
                    'content': content,
                    'impressions': 0,  # X.com may require additional parsing
                    'engagements': 0,  # X.com may require additional parsing
                })

            logger.info(f"Extracted {len(posts)} posts.")
            return posts

        except Exception as e:
            logger.error(f"Error extracting posts: {e}")
            return []

def send_to_discord(posts):
    """Send all scraped posts to Discord webhook."""
    if not posts:
        logger.warning("No posts to send")
        return

    for post in posts:
        try:
            message = {
                'content': f"📄 Post Content:\n```\n{post['content']}\n```"
            }

            logger.info("Sending post to Discord...")
            response = requests.post(DISCORD_WEBHOOK_URL, json=message)

            if response.status_code == 204:
                logger.info("Successfully sent post to Discord")
            else:
                logger.error(f"Discord webhook failed: {response.status_code} - {response.text}")

        except requests.RequestException as e:
            logger.error(f"Error sending to Discord: {e}")

def metrics_job(scraper):
    """Job to scrape all posts and send them to Discord."""
    logger.info("Starting metrics collection job...")
    html = scraper.scrape_profile()
    if html:
        posts = scraper.extract_posts(html)
        send_to_discord(posts)
    logger.info("Metrics job completed")

def run_scheduler(scraper):
    """Run scheduler to periodically scrape all posts and send metrics."""
    logger.info("Starting scheduler...")
    metrics_job(scraper)  # Execute the job immediately

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