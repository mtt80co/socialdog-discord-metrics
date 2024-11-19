import os
import requests
import logging
import schedule
import threading
import time
from flask import Flask
import json
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class XScraper:
    def __init__(self, username: str):
        self.username = username
        self.chrome_options = Options()
        self.chrome_options.add_argument('--headless')
        self.chrome_options.add_argument('--no-sandbox')
        self.chrome_options.add_argument('--disable-dev-shm-usage')
        self.chrome_options.add_argument('--disable-gpu')
        self.chrome_options.add_argument('--window-size=1920,1080')
        self.chrome_options.add_argument('--disable-notifications')
        self.chrome_options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36')

    def get_tweets(self):
        try:
            driver = webdriver.Chrome(options=self.chrome_options)
            driver.get(f'https://twitter.com/{self.username}')
            
            wait = WebDriverWait(driver, 20)
            tweets = wait.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, 'article[data-testid="tweet"]')))
            
            parsed_tweets = []
            for tweet in tweets[:20]:  # Get last 20 tweets
                try:
                    text = tweet.find_element(By.CSS_SELECTOR, '[data-testid="tweetText"]').text
                    stats = tweet.find_elements(By.CSS_SELECTOR, '[data-testid$="-count"]')
                    metrics = {'retweet_count': 0, 'reply_count': 0, 'like_count': 0, 'quote_count': 0}
                    
                    for stat in stats:
                        stat_id = stat.get_attribute('data-testid')
                        if 'retweet' in stat_id:
                            metrics['retweet_count'] = int(stat.text or 0)
                        elif 'reply' in stat_id:
                            metrics['reply_count'] = int(stat.text or 0)
                        elif 'like' in stat_id:
                            metrics['like_count'] = int(stat.text or 0)
                    
                    link = tweet.find_element(By.CSS_SELECTOR, 'time').find_element(By.XPATH, '..').get_attribute('href')
                    tweet_id = link.split('/')[-1]
                    timestamp = tweet.find_element(By.CSS_SELECTOR, 'time').get_attribute('datetime')
                    
                    parsed_tweets.append({
                        'id': tweet_id,
                        'text': text,
                        'created_at': timestamp,
                        'metrics': metrics
                    })
                except Exception as e:
                    logger.error(f"Error parsing tweet: {e}")
                    continue
                    
            driver.quit()
            return parsed_tweets

        except Exception as e:
            logger.error(f"Error getting tweets: {e}")
            if 'driver' in locals():
                driver.quit()
            return []

# Rest of the code remains the same...

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
    app = Flask(__name__)
    
    def job():
        logger.info("Running scheduled metrics collection...")
        tweets = scraper.get_tweets()
        send_to_discord(webhook_url, tweets)
        logger.info("Metrics collection completed")
    
    @app.route('/')
    def home():
        return "X.com Metrics Scraper Running"
    
    @app.route('/health')
    def health():
        return "OK", 200
    
    # Run job immediately
    job()
    
    # Run scheduler in background thread
    scheduler_thread = threading.Thread(target=run_scheduler, args=(job,))
    scheduler_thread.daemon = True
    scheduler_thread.start()
    
    # Run Flask app with specific host and port
    app.run(host='0.0.0.0', port=port, debug=False)

if __name__ == '__main__':
    main()