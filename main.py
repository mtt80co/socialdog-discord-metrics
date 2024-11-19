import os
import requests
import logging
import schedule
import threading
import time
from flask import Flask
import json
from bs4 import BeautifulSoup

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class XScraper:
    def __init__(self, username: str):
        self.username = username
        self.base_url = "https://nitter.net"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Connection': 'keep-alive',
        }

    def get_tweets(self):
        try:
            response = requests.get(
                f"{self.base_url}/{self.username}",
                headers=self.headers,
                timeout=10
            )

            if response.status_code != 200:
                logger.error(f"Failed to fetch tweets: {response.status_code}")
                logger.error(f"Response: {response.text[:500]}")
                return []

            return self._parse_tweets(response.text)

        except Exception as e:
            logger.error(f"Error getting tweets: {e}")
            return []

    def _parse_tweets(self, html):
        tweets = []
        try:
            soup = BeautifulSoup(html, 'html.parser')
            timeline = soup.find('div', {'class': 'timeline'})
            
            if not timeline:
                logger.error("No timeline found")
                return []
                
            tweet_items = timeline.find_all('div', {'class': 'timeline-item'})
            
            for item in tweet_items:
                try:
                    tweet_body = item.find('div', {'class': 'tweet-body'})
                    if not tweet_body:
                        continue

                    tweet_content = tweet_body.find('div', {'class': 'tweet-content'})
                    tweet_stats = item.find('div', {'class': 'tweet-stats'})
                    tweet_link = item.find('a', {'class': 'tweet-link'})
                    tweet_date = item.find('span', {'class': 'tweet-date'})

                    stats = {}
                    if tweet_stats:
                        stats_items = tweet_stats.find_all('span', {'class': 'tweet-stat'})
                        for stat in stats_items:
                            stat_text = stat.get_text(strip=True)
                            if 'Retweets' in stat_text:
                                stats['retweet_count'] = int(stat_text.split()[0] or 0)
                            elif 'Quotes' in stat_text:
                                stats['quote_count'] = int(stat_text.split()[0] or 0)
                            elif 'Likes' in stat_text:
                                stats['like_count'] = int(stat_text.split()[0] or 0)
                            elif 'Replies' in stat_text:
                                stats['reply_count'] = int(stat_text.split()[0] or 0)

                    tweets.append({
                        'id': tweet_link['href'].split('/')[-1] if tweet_link else '',
                        'text': tweet_content.get_text(strip=True) if tweet_content else '',
                        'created_at': tweet_date['title'] if tweet_date else '',
                        'metrics': {
                            'retweet_count': stats.get('retweet_count', 0),
                            'reply_count': stats.get('reply_count', 0),
                            'like_count': stats.get('like_count', 0),
                            'quote_count': stats.get('quote_count', 0),
                            'view_count': 0  # Nitter doesn't provide view counts
                        }
                    })
                except Exception as e:
                    logger.error(f"Error parsing tweet item: {e}")
                    continue

            return tweets
        except Exception as e:
            logger.error(f"Error parsing tweets: {e}")
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