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
        self.base_url = "https://twitter.com/i/api/graphql"
        self.headers = {
            'authorization': 'Bearer AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs=1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA',
            'x-guest-token': self._get_guest_token(),
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }

    def _get_guest_token(self):
        try:
            response = requests.post(
                "https://api.twitter.com/1.1/guest/activate.json",
                headers={"authorization": "Bearer AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs=1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA"}
            )
            return response.json()['guest_token']
        except Exception as e:
            logger.error(f"Failed to get guest token: {e}")
            return None

    def _get_user_id(self):
        variables = {
            "screen_name": self.username,
            "withHighlightedLabel": True
        }
        
        response = requests.get(
            f"{self.base_url}/B7dy9SZKYHvrXDTS2qhXhA/UserByScreenName",
            headers=self.headers,
            params={
                "variables": json.dumps(variables)
            }
        )
        
        data = response.json()
        return data['data']['user']['rest_id']

    def get_tweets(self):
        try:
            user_id = self._get_user_id()
            variables = {
                "userId": user_id,
                "count": 20,
                "includePromotedContent": False,
                "withQuickPromoteEligibilityTweetFields": False,
                "withVoice": True,
                "withV2Timeline": True
            }
            
            response = requests.get(
                f"{self.base_url}/pnYpQBCFJsdySzCZDJETIw/UserTweets",
                headers=self.headers,
                params={
                    "variables": json.dumps(variables)
                }
            )
            
            if response.status_code == 200:
                return self._parse_tweets(response.json())
            else:
                logger.error(f"Failed to fetch tweets: {response.status_code}")
                return []
                
        except Exception as e:
            logger.error(f"Error getting tweets: {e}")
            return []

    def _parse_tweets(self, data):
        tweets = []
        try:
            timeline = data['data']['user']['result']['timeline_v2']['timeline']['instructions'][0]['entries']
            
            for entry in timeline:
                if 'tweet' not in entry['content']['itemContent']['tweet_results']['result']:
                    continue
                    
                tweet = entry['content']['itemContent']['tweet_results']['result']['tweet']
                
                tweets.append({
                    'id': tweet['id'],
                    'text': tweet['text'],
                    'created_at': tweet['created_at'],
                    'metrics': {
                        'retweet_count': tweet['public_metrics']['retweet_count'],
                        'reply_count': tweet['public_metrics']['reply_count'],
                        'like_count': tweet['public_metrics']['like_count'],
                        'quote_count': tweet['public_metrics']['quote_count'],
                        'bookmark_count': tweet['public_metrics']['bookmark_count'],
                        'impression_count': tweet.get('impression_count', 0)
                    }
                })
                
            return tweets
        except Exception as e:
            logger.error(f"Error parsing tweets: {e}")
            return []

def send_to_discord(webhook_url, tweets):
    for tweet in tweets:
        embed = {
            'title': 'Tweet Metrics',
            'description': tweet['text'][:2000],
            'fields': [
                {'name': metric, 'value': str(value), 'inline': True}
                for metric, value in tweet['metrics'].items()
            ],
            'timestamp': tweet['created_at']
        }
        
        try:
            requests.post(webhook_url, json={'embeds': [embed]})
        except Exception as e:
            logger.error(f"Failed to send to Discord: {e}")

def main():
    username = os.getenv('X_USERNAME', 'Meteo_Kingdom')
    webhook_url = os.getenv('DISCORD_WEBHOOK_URL')
    
    scraper = XScraper(username)
    
    def job():
        tweets = scraper.get_tweets()
        send_to_discord(webhook_url, tweets)
    
    schedule.every(1).hour.do(job)
    
    # Start Flask server to keep alive
    app = Flask(__name__)
    
    @app.route('/')
    def home():
        return "X.com Metrics Scraper Running"
    
    threading.Thread(target=lambda: schedule.run_pending()).start()
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', 10000)))

if __name__ == '__main__':
    main()