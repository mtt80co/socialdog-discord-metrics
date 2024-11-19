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
                'asp': True  # Enable anti-scraping protection
            }

            logger.info("Attempting to scrape X.com profile...")
            response = requests.get('https://api.scrapfly.io/scrape', headers=headers, params=params, timeout=60)

            if response.status_code == 200:
                try:
                    json_response = response.json()
                    if 'result' in json_response and 'content' in json_response['result']:
                        logger.info("Successfully extracted HTML from JSON response")
                        return json_response['result']['content']
                    else:
                        logger.error("Missing content in Scrapfly response")
                        return ""
                except json.JSONDecodeError as e:
                    logger.error(f"Failed to parse JSON response: {e}")
                    return ""
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
            # Try different selectors that X.com might use
            article_elements = soup.select('article[data-testid="tweet"]') or \
                             soup.select('[data-testid="cellInnerDiv"]') or \
                             soup.select('[data-testid="tweetText"]').parent.parent.parent

            if not article_elements:
                logger.warning("No posts found. Sending debug info to Discord...")
                soup_text = soup.get_text()[:1000]  # Get first 1000 chars of text content
                requests.post(DISCORD_WEBHOOK_URL, json={
                    "content": f"DEBUG: Parsed content preview:\n```\n{soup_text}\n```"
                })
                return []

            for article in article_elements:
                # Extract post content
                text_element = article.select_one('[data-testid="tweetText"]') or \
                             article.select_one('[lang]') or \
                             article.select_one('div[dir="auto"]')
                             
                content = text_element.get_text(strip=True) if text_element else "No content"

                # Extract metrics with multiple possible selectors
                metrics = {
                    'likes': self._extract_metric(article, ['like', 'unlike']),
                    'retweets': self._extract_metric(article, ['retweet']),
                    'replies': self._extract_metric(article, ['reply']),
                    'views': self._extract_views(article),
                }

                # Extract timestamp
                timestamp = article.select_one('time') or article.select_one('[datetime]')
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

                logger.info(f"Extracted post: {content[:50]}...")

            logger.info(f"Extracted {len(posts)} posts with metrics.")
            return posts

        except Exception as e:
            logger.error(f"Error extracting posts: {e}")
            return []

    def _extract_metric(self, article, metric_types):
        for metric_type in metric_types:
            try:
                # Try different possible selectors for metrics
                metric_element = article.select_one(f'[data-testid="{metric_type}"]') or \
                               article.select_one(f'[aria-label*="{metric_type}"]')
                if metric_element:
                    value = metric_element.get_text(strip=True)
                    return self._parse_metric_value(value)
            except Exception as e:
                logger.debug(f"Failed to extract {metric_type}: {e}")
        return 0

    def _extract_views(self, article):
        try:
            # Try different possible selectors for views
            views_element = article.select_one('a[href*="/analytics"]') or \
                          article.select_one('[aria-label*="view"]')
            if views_element:
                value = views_element.get_text(strip=True)
                return self._parse_metric_value(value)
            return 0
        except Exception:
            return 0

    def _parse_metric_value(self, value):
        try:
            if not value:
                return 0
            value = value.lower().replace(',', '')
            if 'k' in value:
                return int(float(value.replace('k', '')) * 1000)
            elif 'm' in value:
                return int(float(value.replace('m', '')) * 1000000)
            return int(''.join(filter(str.isdigit, value))) if value else 0
        except ValueError:
            return 0

# Rest of the code remains the same...