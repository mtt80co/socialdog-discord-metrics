import os
import requests
import json
import logging
import threading
import time
from typing import List, Dict, Optional
import schedule
from flask import Flask

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

    def scrape_profile(self) -> Optional[Dict]:
        """Scrape the X.com profile page to extract post data."""
        try:
            headers = {
                'Authorization': f'Bearer {self.api_key}',
                'Content-Type': 'application/json',
            }
            params = {
                'url': self.profile_url,
                'render_js': 'true',
                'country_code': 'US',
            }

            logger.info("Attempting to scrape X.com profile...")
            response = requests.get('https://api.scrapfly.io/scrape', headers=headers, params=params)

            if response.status_code == 200:
                logger.info("Scraping successful!")
                logger.debug(f"Scraper raw response: {response.text}")
                return response.json()
            else:
                logger.error(f"Scraping failed: {response.status_code} - {response.text}")
                return None

        except requests.RequestException as e:
            logger.error(f"Request error: {e}")
            return None
        except json.JSONDecodeError as e:
            logger.error(f"JSON parsing error: {e}")
            return None

    def extract_posts(self, data: Dict) -> List[Dict]:
        """Extract individual posts from the scraped data."""
        try:
            # Adjust based on actual response structure
            posts = data.get('posts', [])
            parsed_posts = []
            for post in posts:
                parsed_posts.append({
                    'content': post.get('content', 'No content'),
                    'impressions': post.get('impressions', 0),
                    'interactions': post.get('interactions', 0),
                    'followers': post.get('followers', 0),
                    'profile_clicks': post.get('profile_clicks', 0),
                })
            logger.info(f"Extracted {len(parsed_posts)} posts.")
            return parsed_posts
        except KeyError as e:
            logger.error(f"Error extracting posts: {e}")
            return []

def send_to_discord(posts: List[Dict]):
    """Send scraped posts to Discord webhook."""
    if not posts:
        logger.warning("No posts to send")
        return

    for post in posts:
        try:
            message = {
                'content': f"📄 New Post:\n"
                           f"• Content: {post['content']}\n"
                           f"• Impressions: {post['impressions']}\n"
                           f"• Interactions: {post['interactions']}\n"
                           f"• Followers: {post['followers']}\n"
                           f"• Profile Clicks: {post['profile_clicks']}"
            }

            logger.info("Sending post to Discord...")
            response = requests.post(DISCORD_WEBHOOK_URL, json=message)

            if response.status_code == 204:
                logger.info("Successfully sent post to Discord")
            else:
                logger.error(f"Discord webhook failed: {response.status_code} - {response.text}")

        except requests.RequestException as e:
            logger.error(f"Error sending to Discord: {e}")

def metrics_job(scraper: Scraper):
    """Job to scrape X.com profile and send posts to Discord."""
    logger.info("Starting metrics collection job...")
    data = scraper.scrape_profile()
    if data:
        posts = scraper.extract_posts(data)
        send_to_discord(posts)
    logger.info("Metrics job completed")

def run_scheduler(scraper: Scraper):
    """Run scheduler to periodically collect and send metrics."""
    logger.info("Starting scheduler...")
    metrics_job(scraper)  # Run immediately on startup

    # Schedule job every hour
    schedule.every(1).hour.do(metrics_job, scraper=scraper)

    while True
