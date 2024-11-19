import os
import requests
import logging
import schedule
import threading
import time
from flask import Flask
import json
from bs4 import BeautifulSoup
import urllib3
urllib3.disable_warnings()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class XScraper:
    def __init__(self, username: str):
        self.username = username
        self.base_url = "https://nitter.cz"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1'
        }

    def get_tweets(self):
        try:
            logger.info(f"Fetching tweets from {self.base_url}/{self.username}")
            response = requests.get(
                f"{self.base_url}/{self.username}",
                headers=self.headers,
                timeout=30,
                verify=False
            )
            
            logger.debug(f"Response status: {response.status_code}")
            logger.debug(f"Response content length: {len(response.text)}")

            if response.status_code != 200:
                logger.error(f"Failed to fetch tweets: {response.status_code}")
                logger.error(f"Response: {response.text[:500]}")
                return []

            soup = BeautifulSoup(response.text, 'html.parser')
            timeline = soup.find('div', {'class': 'timeline'})
            
            if not timeline:
                logger.error("No timeline found")
                return []
            
            tweets = []
            tweet_items = timeline.find_all('div', {'class': 'timeline-item'})
            
            for item in tweet_items:
                try:
                    tweet_body = item.find('div', {'class': 'tweet-body'})
                    if not tweet_body:
                        continue

                    content = tweet_body.find('div', {'class': 'tweet-content'})
                    stats = item.find('div', {'class': 'tweet-stats'})
                    link = item.find('a', {'class': 'tweet-link'})
                    date = item.find('span', {'class': 'tweet-date'})

                    metrics = {'retweet_count': 0, 'reply_count': 0, 'like_count': 0, 'quote_count': 0}
                    
                    if stats:
                        for stat in stats.find_all('div', {'class': 'icon-container'}):
                            text = stat.get_text(strip=True).lower()
                            value = int(''.join(filter(str.isdigit, text)) or 0)
                            
                            if 'retweet' in text:
                                metrics['retweet_count'] = value
                            elif 'quote' in text:
                                metrics['quote_count'] = value
                            elif 'like' in text:
                                metrics['like_count'] = value
                            elif 'repl' in text:
                                metrics['reply_count'] = value

                    tweets.append({
                        'id': link['href'].split('/')[-1] if link else '',
                        'text': content.get_text(strip=True) if content else '',
                        'created_at': date['title'] if date and 'title' in date.attrs else '',
                        'metrics': metrics
                    })
                except Exception as e:
                    logger.error(f"Error parsing tweet: {e}")
                    continue

            logger.info(f"Successfully parsed {len(tweets)} tweets")
            return tweets

        except Exception as e:
            logger.error(f"Error getting tweets: {e}")
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

def main():
    port = int(os.getenv('PORT', 10000))
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
    
    # Run immediately on startup
    job()
    
    app = Flask(__name__)
    
    @app.route('/')
    def home():
        return "X.com Metrics Scraper Running"
    
    @app.route('/health')
    def health():
        return "OK", 200
    
    # Run scheduler in background thread
    scheduler_thread = threading.Thread(target=run_scheduler, args=(job,), daemon=True)
    scheduler_thread.start()
    
    # Run Flask app
    app.run(host='0.0.0.0', port=port)

if __name__ == '__main__':
    main()