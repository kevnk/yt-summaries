#!/bin/bash

# Create subdirectories
mkdir -p src scripts data config

# Create virtual environment
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate

# Install required packages
pip install google-api-python-client youtube_transcript_api

# Create main script file
cat > src/playlist_transcript_saver.py << EOL
import os
from urllib.parse import parse_qs, urlparse
from googleapiclient.discovery import build
from youtube_transcript_api import YouTubeTranscriptApi

# YouTube API key will be loaded from config file
YOUTUBE_API_KEY = ''

def load_config():
    global YOUTUBE_API_KEY
    with open('config/config.txt', 'r') as f:
        YOUTUBE_API_KEY = f.read().strip()

def get_video_ids_from_playlist(playlist_url):
    # ... (rest of the function code)

def get_transcript(video_id):
    # ... (rest of the function code)

def save_transcript_to_text(video_id, transcript):
    # ... (rest of the function code)

def main(playlist_url):
    load_config()
    video_ids = get_video_ids_from_playlist(playlist_url)
    for video_id in video_ids:
        transcript = get_transcript(video_id)
        save_transcript_to_text(video_id, transcript)

if __name__ == "__main__":
    playlist_url = input("Enter the YouTube playlist URL: ")
    main(playlist_url)
EOL

# Create config file (you'll need to manually add your API key to this file)
mkdir -p config
touch config/config.txt

# Create a README file
cat > README.md << EOL
# YouTube Summaries Project

This project contains scripts for processing YouTube playlists and videos.

## Setup

1. Ensure you have Python 3.7+ installed.
2. Run the setup script: \`./setup.sh\`
3. Add your YouTube API key to \`config/config.txt\`

## Usage

To run the playlist transcript saver:

1. Activate the virtual environment: \`source venv/bin/activate\`
2. Run the script: \`python src/playlist_transcript_saver.py\`
3. Enter the YouTube playlist URL when prompted.

Transcripts will be saved in the \`data\` directory.
EOL

# Create a .gitignore file
cat > .gitignore << EOL
venv/
__pycache__/
*.pyc
config/config.txt
EOL

# Create config file with a template for the API key
cat > config/config.env << EOL
YOUTUBE_API_KEY=your_api_key_here
EOL

# Update the main script to use the new config format
sed -i '' 's/config\/config.txt/config\/config.env/' src/playlist_transcript_saver.py

# Update the load_config function in the main script
sed -i '' '/def load_config():/,/YOUTUBE_API_KEY = f.read().strip()/c\
def load_config():
    global YOUTUBE_API_KEY
    with open('\''config/config.env'\'', '\''r'\'') as f:
        for line in f:
            if line.startswith('\''YOUTUBE_API_KEY'\''):
                YOUTUBE_API_KEY = line.split('\''='\'')[1].strip()
                break
' src/playlist_transcript_saver.py

# Update .gitignore
sed -i '' 's/config\/config.txt/config\/config.env/' .gitignore

echo "Setup complete. Please add your YouTube API key to config/config.env"
echo "Edit the file and replace 'your_api_key_here' with your actual API key."