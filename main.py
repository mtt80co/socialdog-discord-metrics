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
        self.query_id = "k5XapwcSikNsEsILW5FvgA"  # Updated query ID
        self._refresh_headers()

    def _refresh_headers(self):
        self.headers = {
            'authorization': 'Bearer AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs=1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA',
            'x-guest-token': self._get_guest_token(),
            'x-twitter-client-language': 'en',
            'x-twitter-active-user': 'yes',
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'accept': '*/*',
            'accept-language': 'en-US,en;q=0.9',
            'content-type': 'application/json',
            'x-csrf-token': 'unavailable'
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

    def get_tweets(self):
        try:
            variables = {
                "screen_name": self.username,
                "count": 20,
                "withHighlightedLabel": True,
                "includePromotedContent": False,
                "withTweetQuoteCount": True,
                "withBirdwatchNotes": True,
                "withReactionsMetadata": True,
                "withReactionsPerspective": True
            }

            features = {
                "responsive_web_twitter_blue_verified_badge_is_enabled": True,
                "responsive_web_graphql_exclude_directive_enabled": True,
                "verified_phone_label_enabled": False,
                "responsive_web_graphql_timeline_navigation_enabled": True,
                "responsive_web_graphql_skip_user_profile_image_extensions_enabled": False,
                "tweetypie_unmention_optimization_enabled": True,
                "vibe_api_enabled": True,
                "responsive_web_edit_tweet_api_enabled": True,
                "graphql_is_translatable_rweb_tweet_is_translatable_enabled": True,
                "view_counts_everywhere_api_enabled": True,
                "freedom_of_speech_not_reach_fetch_enabled": True,
                "standardized_nudges_misinfo": True,
                "tweet_with_visibility_results_prefer_gql_limited_actions_policy_enabled": False,
                "interactive_text_enabled": True,
                "responsive_web_text_conversations_enabled": False,
                "longform_notetweets_consumption_enabled": True,
                "tweet_awards_web_tipping_enabled": False,
                "longform_notetweets_rich_text_read_enabled": True
            }
            
            params = {
                'variables': json.dumps(variables),
                'features': json.dumps(features)
            }
            
            response = requests.get(
                f"{self.base_url}/{self.query_id}/UserTweets",
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
            entries = data['data']['user']['result']['timeline_v2']['timeline']['instructions'][1]['entries']
            
            for entry in entries:
                if entry['entryId'].startswith('tweet-'):
                    try:
                        result = entry['content']['itemContent']['tweet_results']['result']
                        legacy = result['legacy']
                        
                        tweets.append({
                            'id': result['rest_id'],
                            'text': legacy['full_text'],
                            'created_at': legacy['created_at'],
                            'metrics': {
                                'retweet_count': legacy['retweet_count'],
                                'reply_count': legacy['reply_count'],
                                'like_count': legacy['favorite_count'],
                                'quote_count': legacy['quote_count'],
                                'view_count': result.get('views', {}).get('count', 0),
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