import os
import requests
import logging
import schedule
import threading
import time
from flask import Flask
import json

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class XScraper:
    def __init__(self, username: str):
        self.username = username
        self.base_url = "https://api.twitter.com/2/timeline/profile"
        self._refresh_headers()

    def _refresh_headers(self):
        guest_token = self._get_guest_token()
        if not guest_token:
            logger.error("Failed to get guest token")
            return

        self.headers = {
            'authorization': 'Bearer AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs=1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA',
            'x-guest-token': guest_token,
            'x-twitter-client-language': 'en',
            'x-twitter-active-user': 'yes',
            'x-csrf-token': 'missing',
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
            'accept': '*/*',
            'accept-language': 'en-US,en;q=0.9',
            'content-type': 'application/json',
            'referer': f'https://twitter.com/{self.username}',
            'origin': 'https://twitter.com',
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors',
            'sec-fetch-site': 'same-origin'
        }

    def _get_guest_token(self):
        try:
            response = requests.post(
                "https://api.twitter.com/1.1/guest/activate.json",
                headers={
                    "authorization": "Bearer AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs=1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA"
                }
            )
            if response.status_code == 200:
                return response.json()['guest_token']
            logger.error(f"Failed to get guest token: {response.status_code}")
            return None
        except Exception as e:
            logger.error(f"Error getting guest token: {e}")
            return None

    def get_tweets(self):
        try:
            params = {
                'cursor': '-1',
                'includePromotedContent': 'false',
                'count': '20',
                'userId': '1837456870333992964',
                'withTweetQuoteCount': 'true',
                'withBirdwatchNotes': 'false',
                'withVoice': 'true',
                'withV2Timeline': 'true'
            }

            response = requests.get(
                f"{self.base_url}/{params['userId']}.json",
                headers=self.headers,
                params=params
            )

            if response.status_code == 401:
                self._refresh_headers()
                return self.get_tweets()

            if response.status_code != 200:
                logger.error(f"Failed to fetch tweets: {response.status_code}")
                logger.error(f"Response: {response.text[:500]}")
                return []

            return self._parse_tweets(response.json())

        except Exception as e:
            logger.error(f"Error getting tweets: {e}")
            return []

    def _parse_tweets(self, data):
        tweets = []
        try:
            for tweet in data.get('globalObjects', {}).get('tweets', {}).values():
                try:
                    tweets.append({
                        'id': tweet['id_str'],
                        'text': tweet['full_text'] if 'full_text' in tweet else tweet['text'],
                        'created_at': tweet['created_at'],
                        'metrics': {
                            'retweet_count': tweet['retweet_count'],
                            'reply_count': tweet.get('reply_count', 0),
                            'like_count': tweet['favorite_count'],
                            'quote_count': tweet.get('quote_count', 0),
                            'view_count': tweet.get('ext_views', {}).get('count', 0)
                        }
                    })
                except Exception as e:
                    logger.error(f"Error parsing tweet: {e}")
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
                {'name': 'Views', 'value': str(tweet['metrics']['view_count']), 'inline': True},
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