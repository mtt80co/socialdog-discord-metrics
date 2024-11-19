import os
import requests
import logging
import schedule
import threading
import time
from flask import Flask
import json
from playwright.sync_api import sync_playwright

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class XScraper:
    def __init__(self, username: str):
        self.username = username
        
    def get_tweets(self):
        try:
            with sync_playwright() as p:
                # Launch browser with required arguments
                browser = p.chromium.launch(
                    headless=True,
                    args=['--no-sandbox', '--disable-dev-shm-usage']
                )
                
                # Create new context and page
                context = browser.new_context(viewport={'width': 1920, 'height': 1080})
                page = context.new_page()
                
                # Navigate to Twitter profile
                page.goto(f'https://twitter.com/{self.username}', wait_until='networkidle')
                
                # Wait for tweets to load
                page.wait_for_selector('article[data-testid="tweet"]', timeout=30000)
                tweets = page.query_selector_all('article[data-testid="tweet"]')
                parsed_tweets = []
                
                # Parse each tweet
                for tweet in tweets[:20]:
                    try:
                        text_element = tweet.query_selector('[data-testid="tweetText"]')
                        text = text_element.inner_text() if text_element else ""
                        
                        metrics = {'retweet_count': 0, 'reply_count': 0, 'like_count': 0, 'quote_count': 0}
                        
                        # Get metrics
                        for metric in ['retweet', 'reply', 'like']:
                            try:
                                count = tweet.query_selector(f'[data-testid="{metric}-count"]')
                                if count:
                                    metrics[f'{metric}_count'] = int(count.inner_text() or 0)
                            except Exception as e:
                                logger.debug(f"Error getting {metric} count: {e}")
                                
                        # Get tweet metadata
                        time_element = tweet.query_selector('time')
                        link = time_element.evaluate('el => el.parentElement.href')
                        tweet_id = link.split('/')[-1]
                        timestamp = time_element.get_attribute('datetime')
                        
                        parsed_tweets.append({
                            'id': tweet_id,
                            'text': text,
                            'created_at': timestamp,
                            'metrics': metrics
                        })
                        logger.info(f"Successfully parsed tweet {tweet_id}")
                    except Exception as e:
                        logger.error(f"Error parsing tweet: {e}")
                        continue
                
                browser.close()
                return parsed_tweets

        except Exception as e:
            logger.error(f"Error getting tweets: {e}")
            if 'browser' in locals():
                browser.close()
            return []

def send_to_discord(webhook_url: str, tweets: list):
    if not tweets:
        logger.warning("No tweets to send")
        return

    for tweet in tweets:
        embed = {
            'title': 'Tweet Metrics',
            'description': tweet['text'][:2000],
            'fields': [
                {'name': 'Retweets', 'value': str(tweet['metrics']['retweet_count']), 'inline': True},
                {'name': 'Replies', 'value': str(tweet['metrics']['reply_count']), 'inline': True},
                {'name': 'Likes', 'value': str(tweet['metrics']['like_count']), 'inline': True},
                {'name': 'Quotes', 'value': str(tweet['metrics']['quote_count']), 'inline': True}
            ],
            'timestamp': tweet['created_at']
        }
        
        try:
            response = requests.post(webhook_url, json={'embeds': [embed]})
            if response.status_code == 204:
                logger.info(f"Successfully sent metrics for tweet {tweet['id']}")
            else:
                logger.error(f"Failed to send to Discord. Status: {response.status_code}")
        except Exception as e:
            logger.error(f"Failed to send to Discord: {e}")

def run_scheduler(job):
    schedule.every(15).minutes.do(job)
    while True:
        schedule.run_pending()
        time.sleep(1)

app = Flask(__name__)
scheduler_started = False

@app.route('/')
def home():
    return "X.com Metrics Scraper Running"

@app.route('/health')
def health():
    return "OK", 200

def create_app():
    global scheduler_started
    if not scheduler_started:
        username = os.getenv('X_USERNAME', 'Meteo_Kingdom')
        webhook_url = os.getenv('DISCORD_WEBHOOK_URL')
        
        if not webhook_url:
            logger.error("DISCORD_WEBHOOK_URL environment variable is required")
            exit(1)
        
        scraper = XScraper(username)
        
        def job():
            logger.info("Running scheduled metrics collection...")
            tweets = scraper.get_tweets()
            send_to_discord(webhook_url, tweets)
            logger.info("Metrics collection completed")
        
        # Run job immediately
        job()
        
        # Start scheduler in background thread
        scheduler_thread = threading.Thread(target=run_scheduler, args=(job,))
        scheduler_thread.daemon = True
        scheduler_thread.start()
        
        scheduler_started = True
    
    return app

if __name__ == '__main__':
    app = create_app()
    port = int(os.getenv('PORT', 10000))
    app.run(host='0.0.0.0', port=port)