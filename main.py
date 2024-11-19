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
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'content-type': 'application/json',
            'accept': '*/*',
            'accept-language': 'en-US,en;q=0.9',
            'x-twitter-active-user': 'yes',
            'x-twitter-client-language': 'en'
        }

    def _get_guest_token(self):
        try:
            response = requests.post(
                "https://api.twitter.com/1.1/guest/activate.json",
                headers={
                    "authorization": "Bearer AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs=1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA"
                }
            )
            return response.json()['guest_token']
        except Exception as e:
            logger.error(f"Failed to get guest token: {e}")
            return None

    def refresh_guest_token(self):
        self.headers['x-guest-token'] = self._get_guest_token()

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
        
        if response.status_code == 401:
            self.refresh_guest_token()
            return self._get_user_id()
            
        data = response.json()
        try:
            return data['data']['user']['rest_id']
        except (KeyError, TypeError):
            logger.error(f"Failed to get user ID. Response: {data}")
            return None

    def get_tweets(self):
        try:
            user_id = self._get_user_id()
            if not user_id:
                logger.error("Could not get user ID")
                return []

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
            
            if response.status_code == 401:
                self.refresh_guest_token()
                return self.get_tweets()
                
            if response.status_code == 200:
                return self._parse_tweets(response.json())
            else:
                logger.error(f"Failed to fetch tweets: {response.status_code}")
                logger.error(f"Response: {response.text}")
                return []
                
        except Exception as e:
            logger.error(f"Error getting tweets: {e}")
            return []

    def _parse_tweets(self, data):
        tweets = []
        try:
            instructions = data['data']['user']['result']['timeline_v2']['timeline']['instructions']
            timeline = next((inst for inst in instructions if inst['type'] == 'TimelineAddEntries'), None)
            
            if not timeline:
                logger.error("No timeline entries found")
                return []

            for entry in timeline['entries']:
                try:
                    if 'tweet' not in entry['content']['itemContent'].get('tweet_results', {}).get('result', {}):
                        continue
                        
                    tweet = entry['content']['itemContent']['tweet_results']['result']['tweet']
                    legacy = tweet.get('legacy', {})
                    
                    tweets.append({
                        'id': tweet.get('rest_id'),
                        'text': legacy.get('full_text', tweet.get('text', '')),
                        'created_at': legacy.get('created_at'),
                        'metrics': {
                            'retweet_count': legacy.get('retweet_count', 0),
                            'reply_count': legacy.get('reply_count', 0),
                            'like_count': legacy.get('favorite_count', 0),
                            'quote_count': legacy.get('quote_count', 0),
                            'view_count': tweet.get('views', {}).get('count', 0),
                            'bookmark_count': legacy.get('bookmark_count', 0)
                        }
                    })
                except Exception as e:
                    logger.error(f"Error parsing tweet: {e}")
                    continue
                
            return tweets
        except Exception as e:
            logger.error(f"Error parsing tweets: {e}")
            return []

def send_to_discord(webhook_url, tweets):
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
                {'name': 'Quotes', 'value': str(tweet['metrics']['quote_count']), 'inline': True},
                {'name': 'Bookmarks', 'value': str(tweet['metrics']['bookmark_count']), 'inline': True},
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

def main():
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
    
    # Schedule every 15 minutes
    schedule.every(15).minutes.do(job)
    
    app = Flask(__name__)
    
    @app.route('/')
    def home():
        return "X.com Metrics Scraper Running"
    
    # Run scheduler in background thread
    def run_scheduler():
        while True:
            schedule.run_pending()
            time.sleep(1)
            
    scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
    scheduler_thread.start()
    
    # Run Flask app
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', 10000)))

if __name__ == '__main__':
    main()