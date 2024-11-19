import requests
import json
import time

# Scrapfly API Key
SCRAPFLY_API_KEY = 'your_scrapfly_api_key'

# Your X.com profile URL (adjust based on your account's public URL)
X_COM_PROFILE_URL = "https://x.com/your_username"

# Discord Webhook URL
DISCORD_WEBHOOK_URL = 'https://discord.com/api/webhooks/your_discord_webhook_url'

# Function to scrape X.com metrics (Impressions, interactions, etc.)
def scrape_x_com():
    # Set headers for Scrapfly API
    headers = {
        'Authorization': f'Bearer {SCRAPFLY_API_KEY}',
        'Content-Type': 'application/json',
    }

    params = {
        'url': X_COM_PROFILE_URL,
        'render_js': 'true',  # Enables JS rendering if needed
        'country_code': 'US',  # Optional: Set according to your location
    }

    # Make the request to Scrapfly API to scrape the data
    response = requests.get('https://api.scrapfly.io/scrape', headers=headers, params=params)

    if response.status_code == 200:
        # Assuming JSON is returned and contains metrics like impressions, interactions
        data = response.json()

        impressions = data.get('impressions', 0)
        interactions = data.get('interactions', 0)
        followers = data.get('followers', 0)
        profile_clicks = data.get('profile_clicks', 0)
        
        return impressions, interactions, followers, profile_clicks
    else:
        print("Error scraping data:", response.text)
        return None, None, None, None

# Function to send the scraped data to Discord
def send_to_discord(impressions, interactions, followers, profile_clicks):
    # Format the message to be sent to Discord
    message = {
        'content': f"X.com Metrics:\nImpressions: {impressions}\nInteractions: {interactions}\nFollowers: {followers}\nProfile Clicks: {profile_clicks}"
    }
    
    # Send the message to Discord webhook
    response = requests.post(DISCORD_WEBHOOK_URL, json=message)
    if response.status_code == 204:
        print("Successfully sent to Discord")
    else:
        print(f"Failed to send to Discord: {response.status_code} - {response.text}")

# Main function to scrape the data and send it to Discord
def main():
    impressions, interactions, followers, profile_clicks = scrape_x_com()
    if impressions is not None:
        send_to_discord(impressions, interactions, followers, profile_clicks)
    else:
        print("No data available.")

if __name__ == "__main__":
    main()
