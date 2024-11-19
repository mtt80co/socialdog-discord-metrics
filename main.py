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
        self.base_url = "https://api.twitter.com/graphql"
        self.query_id = "8IS8MaO-2EN6GZZZb8jF0g"  # Updated query ID
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
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'accept': '*/*',
            'accept-language': 'en-US,en;q=0.9',
            'content-type': 'application/json',
            'referer': f'https://twitter.com/{self.username}',
            'origin': 'https://twitter.com'
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
            variables = {
                "screen_name": self.username,
                "count": 40,
                "withHighlightedLabel": True,
                "withTweetQuoteCount": True,
                "includePromotedContent": False,
                "withQuickPromoteEligibilityTweetFields": True,
                "withBirdwatchNotes": False,
                "withVoice": True,
                "withV2Timeline": True
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
                "longform_notetweets_consumption_enabled": True,
                "tweet_awards_web_tipping_enabled": False,
                "freedom_of_speech_not_reach_fetch_enabled": True,
                "standardized_nudges_misinfo": True,
                "tweet_with_visibility_results_prefer_gql_limited_actions_policy_enabled": False,
                "responsive_web_twitter_article_notes_tab_enabled": True,
                "interactive_text_enabled": True,
                "responsive_web_text_conversations_enabled": False,
                "responsive_web_enhance_cards_enabled": False,
                "responsive_web_media_download_video_enabled": False,
                "highlights_tweets_tab_ui_enabled": True,
                "creator_subscriptions_tweet_preview_api_enabled": True,
                "responsive_web_graphql_skip_user_profile_image_extensions_webp_enabled": False,
                "hidden_profile_likes_enabled": True, 
                "hidden_profile_subscriptions_enabled": True,
                "subscriptions_verification_info_verified_since_enabled": True,
                "subscriptions_verification_info_is_identity_verified_enabled": True
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
            timeline = data['data']['user']['result']['timeline_v2']['timeline']
            entries = timeline['instructions'][0]['entries']
            
            for entry in entries:
                if not entry['entryId'].startswith('tweet-'):
                    continue
                    
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
                            'quote_count': legacy.get('quote_count', 0),
                            'view_count': result.get('views', {}).get('count', 0)
                        }
                    })
                except Exception as e:
                    logger.error(f"Error parsing tweet: {e}")
                    continue
                
            return tweets
        except Exception as e:
            logger.error(f"Error parsing tweets: {e}")
            return []

[Rest of the code remains the same...]