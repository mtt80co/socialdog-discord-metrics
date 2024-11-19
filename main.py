import os
import requests
import logging
import schedule
import threading
import time
from flask import Flask
from bs4 import BeautifulSoup
import json

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

SCRAPFLY_API_KEY = os.getenv('SCRAPFLY_API_KEY')
X_COM_PROFILE_URL = os.getenv('X_COM_PROFILE_URL', 'https://x.com/Meteo_Kingdom')
DISCORD_WEBHOOK_URL = os.getenv('DISCORD_WEBHOOK_URL')

if not all([SCRAPFLY_API_KEY, X_COM_PROFILE_URL, DISCORD_WEBHOOK_URL]):
    logger.error("Missing required environment variables")
    exit(1)

class Scraper:
    def __init__(self, api_key: str, profile_url: str):
        self.api_key = api_key
        self.profile_url = profile_url

    def scrape_profile(self) -> str:
        try:
            headers = {
                'Authorization': f'Bearer {self.api_key}',
                'Content-Type': 'application/json',
            }
            params = {
                'url': self.profile_url,
                'render_js': 'true',
                'wait_for': '15s',
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
        soup = BeautifulSoup(html, 'html.parser')
        posts = []

        try:
            article_elements = soup.select('article[data-testid="tweet"]')
            
            if not article_elements:
                logger.warning("No posts found. Sending full HTML to Discord for debugging.")
                requests.post(DISCORD_WEBHOOK_URL, json={
                    "content": f"DEBUG: No posts found. HTML length: {len(html)} chars. First 500 chars:\n```\n{html[:500]}\n```"
                })
                return []

            for article in article_elements:
                # Extract post content
                text_element = article.select_one('div[data-testid="tweetText"]')
                content = text_element.get_text(strip=True) if text_element else "No content"

                # Extract metrics
                metrics = {
                    'likes': self._extract_metric(article, 'like'),
                    'retweets': self._extract_metric(article, 'retweet'),
                    'replies': self._extract_metric(article, 'reply'),
                    'views': self._extract_views(article),
                }

                # Extract timestamp
                timestamp = article.select_one('time')
                posted_at = timestamp['datetime'] if timestamp else None

                # Extract post URL
                link_element = article.select_one('a[href*="/status/"]')
                post_url = f"https://x.com{link_element['href']}" if link_element else None

                posts.append({
                    'content': content,
                    'metrics': metrics,
                    'posted_at': posted_at,
                    'url': post_url
                })

            logger.info(f"Extracted {len(posts)} posts with metrics.")
            return posts

        except Exception as e:
            logger.error(f"Error extracting posts: {e}")
            return []

    def _extract_metric(self, article, metric_type):
        try:
            metric_element = article.select_one(f'div[data-testid="{metric_type}"]')
            if metric_element:
                value = metric_element.get_text(strip=True)
                return self._parse_metric_value(value)
            return 0
        except Exception:
            return 0

    def _extract_views(self, article):
        try:
            views_element = article.select_one('a[href*="/analytics"]')
            if views_element:
                value = views_element.get_text(strip=True)
                return self._parse_metric_value(value)
            return 0
        except Exception:
            return 0

    def _parse_metric_value(self, value):
        try:
            if 'K' in value:
                return int(float(value.replace('K', '')) * 1000)
            elif 'M' in value:
                return int(float(value.replace('M', '')) * 1000000)
            return int(value) if value else 0
        except ValueError:
            return 0

def send_to_discord(posts):
    if not posts:
        logger.warning("No posts to send")
        return

    for post in posts:
        try:
            message = {
                'embeds': [{
                    'title': 'Post Metrics',
                    'url': post['url'],
                    'description': post['content'],
                    'fields': [
                        {'name': 'Likes', 'value': str(post['metrics']['likes']), 'inline': True},
                        {'name': 'Retweets', 'value': str(post['metrics']['retweets']), 'inline': True},
                        {'name': 'Replies', 'value': str(post['metrics']['replies']), 'inline': True},
                        {'name': 'Views', 'value': str(post['metrics']['views']), 'inline': True},
                    ],
                    'timestamp': post['posted_at']
                }]
            }

            response = requests.post(DISCORD_WEBHOOK_URL, json=message)

            if response.status_code == 204:
                logger.info("Successfully sent post metrics to Discord")
            else:
                logger.error(f"Discord webhook failed: {response.status_code} - {response.text}")

        except requests.RequestException as e:
            logger.error(f"Error sending to Discord: {e}")

def metrics_job(scraper):
    logger.info("Starting metrics collection job...")
    html = scraper.scrape_profile()
    if html:
        posts = scraper.extract_posts(html)
        send_to_discord(posts)
    logger.info("Metrics job completed")

def run_scheduler(scraper):
    logger.info("Starting scheduler...")
    metrics_job(scraper)

    schedule.every(1).hour.do(metrics_job, scraper=scraper)

    while True:
        schedule.run_pending()
        time.sleep(60)

if __name__ == '__main__':
    scraper = Scraper(api_key=SCRAPFLY_API_KEY, profile_url=X_COM_PROFILE_URL)

    scheduler_thread = threading.Thread(target=run_scheduler, args=(scraper,))
    scheduler_thread.daemon = True
    scheduler_thread.start()

    app = Flask(__name__)

    @app.route('/')
    def home():
        return "X.com Metrics Scraper is running"

    app.run(host='0.0.0.0', port=int(os.getenv('PORT', 10000)))