{\rtf1\ansi\ansicpg1252\cocoartf2818
\cocoatextscaling0\cocoaplatform0{\fonttbl\f0\fswiss\fcharset0 Helvetica;}
{\colortbl;\red255\green255\blue255;}
{\*\expandedcolortbl;;}
\paperw11900\paperh16840\margl1440\margr1440\vieww11040\viewh12780\viewkind0
\pard\tx720\tx1440\tx2160\tx2880\tx3600\tx4320\tx5040\tx5760\tx6480\tx7200\tx7920\tx8640\pardirnatural\partightenfactor0

\f0\fs24 \cf0 import requests\
import os\
\
# Set up environment variables (replace with your actual environment variables on Render)\
SOCIALDOG_API_KEY = os.getenv('SOCIALDOG_API_KEY')  # Set this in Render\
DISCORD_WEBHOOK_URL = os.getenv('DISCORD_WEBHOOK_URL')  # Set this in Render\
\
# SocialDog API URL for fetching analytics data\
SOCIALDOG_API_URL = 'https://api.social-dog.net/v1/analytics'\
\
def fetch_socialdog_data():\
    """Fetch metrics like impressions and profile visits from SocialDog."""\
    headers = \{\
        'Authorization': f'Bearer \{SOCIALDOG_API_KEY\}',\
        'Content-Type': 'application/json'\
    \}\
    \
    response = requests.get(SOCIALDOG_API_URL, headers=headers)\
\
    if response.status_code == 200:\
        data = response.json()\
        impressions = data.get('impressions', 'Not available')\
        profile_visits = data.get('profile_visits', 'Not available')\
        return impressions, profile_visits\
    else:\
        print(f"Error fetching data: \{response.status_code\}")\
        return None, None\
\
def send_to_discord(impressions, profile_visits):\
    """Send fetched metrics to a Discord channel via webhook."""\
    if impressions is None or profile_visits is None:\
        return\
\
    message = f"\uc0\u55357 \u56522  X Account Metrics:\\nImpressions: \{impressions\}\\nProfile Visits: \{profile_visits\}"\
\
    response = requests.post(DISCORD_WEBHOOK_URL, json=\{'content': message\})\
\
    if response.status_code == 204:\
        print("Message sent to Discord successfully.")\
    else:\
        print(f"Failed to send message to Discord. Status code: \{response.status_code\}")\
\
if __name__ == '__main__':\
    impressions, profile_visits = fetch_socialdog_data()\
    send_to_discord(impressions, profile_visits)\
}