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

# [Previous XScraper class and functions remain the same]

app = Flask(__name__)
scheduler_started = False

@app.route('/')
def home():
    return "X.com Metrics Scraper Running"

@app.route('/health')
def health():
    return "OK", 200

def create_app():
    global scheduler_started
    if not scheduler_started:
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
        
        # Run job immediately
        job()
        
        # Start scheduler in background thread
        scheduler_thread = threading.Thread(target=run_scheduler, args=(job,))
        scheduler_thread.daemon = True
        scheduler_thread.start()
        
        scheduler_started = True
    
    return app

if __name__ == '__main__':
    port = int(os.getenv('PORT', 10000))
    app = create_app()
    app.run(host='0.0.0.0', port=port)