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
        self.base_url = "https://twitter.com/i/api/2/timeline"
        self.query_id = "tweet-detail"
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
            'sec-ch-ua': '"Google Chrome";v="119", "Chromium";v="119", "Not?A_Brand";v="24"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
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
                'include_profile_interstitial_type': '1',
                'include_blocking': '1',
                'include_blocked_by': '1',
                'include_followed_by': '1',
                'include_want_retweets': '1',
                'include_mute_edge': '1',
                'include_can_dm': '1',
                'include_can_media_tag': '1',
                'include_ext_has_nft_avatar': '1',
                'include_ext_is_blue_verified': '1',
                'include_ext_verified_type': '1',
                'skip_status': '1',
                'cards_platform': 'Web-12',
                'include_cards': '1',
                'include_ext_alt_text': 'true',
                'include_ext_limited_action_results': 'false',
                'include_quote_count': 'true',
                'include_reply_count': '1',
                'tweet_mode': 'extended',
                'include_ext_views': 'true',
                'include_entities': 'true',
                'include_user_entities': 'true',
                'include_ext_media_color': 'true',
                'include_ext_media_availability': 'true',
                'include_ext_sensitive_media_warning': 'true',
                'include_ext_trusted_friends_metadata': 'true',
                'send_error_codes': 'true',
                'simple_quoted_tweet': 'true',
                'count': 40,
                'userId': '1837456870333992964',
                'ext': 'mediaStats,highlightedLabel,hasNftAvatar,voiceInfo,birdwatchPivot,enrichments,superFollowMetadata,unmentionInfo,editControl,collab_control,vibe'
            }

            response = requests.get(
                f"{self.base_url}/user/{params['userId']}/tweets",
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
                        'text': tweet['full_text'],
                        'created_at': tweet['created_at'],
                        'metrics': {
                            'retweet_count': tweet['retweet_count'],
                            'reply_count': tweet['reply_count'],
                            'like_count': tweet['favorite_count'],
                            'quote_count': tweet.get('quote_count', 0),
                            'view_count': tweet.get('ext', {}).get('views', {}).get('r', {}).get('ok', {}).get('count', 0)
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