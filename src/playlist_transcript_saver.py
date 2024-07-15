import os
import re
import json
import subprocess
from urllib.parse import parse_qs, urlparse
from googleapiclient.discovery import build
from youtube_transcript_api import YouTubeTranscriptApi
import sys
import requests
import markdown
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import hashlib
import argparse
import boto3

# Configuration variables
YOUTUBE_API_KEY = ''
CLAUDE_API_KEY = ''
EMAIL_ADDRESS = ''
EMAIL_PASSWORD = ''
PROMPT_FILE_PATH = ''
SMTP_SERVER = ''
SMTP_PORT = 587
SMTP_USE_TLS = True
AWS_REGION = ''
AWS_ACCESS_KEY_ID = ''
AWS_SECRET_ACCESS_KEY = ''

def load_config():
    global YOUTUBE_API_KEY, CLAUDE_API_KEY, EMAIL_ADDRESS, EMAIL_PASSWORD, PROMPT_FILE_PATH
    global SMTP_SERVER, SMTP_PORT, SMTP_USE_TLS, AWS_REGION, AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY
   
    # Try to find the config file in multiple locations
    possible_config_paths = [
        os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config', 'config.env'),
        os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'config', 'config.env'),
        os.path.join(os.getcwd(), 'config', 'config.env'),
    ]
    
    config_path = None
    for path in possible_config_paths:
        if os.path.exists(path):
            config_path = path
            break
    
    if not config_path:
        print("Error: config.env file not found. Please ensure it exists in one of the following locations:")
        for path in possible_config_paths:
            print(f"- {path}")
        print("\nThe config.env file should contain the following keys:")
        print("YOUTUBE_API_KEY=your_youtube_api_key")
        print("CLAUDE_API_KEY=your_claude_api_key")
        print("EMAIL_ADDRESS=your_email_address")
        print("EMAIL_PASSWORD=your_email_password")
        print("RECIPIENT_EMAIL=recipient_email_address")
        print("PROMPT_FILE_PATH=path_to_your_prompt_file")
        sys.exit(1)
    
    try:
        with open(config_path, 'r') as f:
            for line in f:
                if '=' in line:
                    key, value = line.strip().split('=', 1)
                    if key == 'YOUTUBE_API_KEY':
                        YOUTUBE_API_KEY = value
                    elif key == 'CLAUDE_API_KEY':
                        CLAUDE_API_KEY = value
                    elif key == 'EMAIL_ADDRESS':
                        EMAIL_ADDRESS = value
                    elif key == 'EMAIL_PASSWORD':
                        EMAIL_PASSWORD = value
                    elif key == 'PROMPT_FILE_PATH':
                        PROMPT_FILE_PATH = value
                    elif key == 'SMTP_SERVER':
                        SMTP_SERVER = value
                    elif key == 'SMTP_PORT':
                        SMTP_PORT = int(value)
                    elif key == 'SMTP_USE_TLS':
                        SMTP_USE_TLS = value.lower() == 'true'

    except IOError as e:
        print(f"Error reading config file: {e}")
        sys.exit(1)
    
    # Validate that all required config values are set
    required_configs = ['YOUTUBE_API_KEY', 'CLAUDE_API_KEY', 'EMAIL_ADDRESS', 'EMAIL_PASSWORD', 'PROMPT_FILE_PATH']
    missing_configs = [config for config in required_configs if not globals().get(config)]
    
    if missing_configs:
        print("Error: The following required configurations are missing or empty in the config file:")
        for config in missing_configs:
            print(f"- {config}")
        sys.exit(1)
    
    # Validate that the PROMPT_FILE_PATH exists
    if not os.path.exists(PROMPT_FILE_PATH):
        print(f"Error: The specified PROMPT_FILE_PATH does not exist: {PROMPT_FILE_PATH}")
        sys.exit(1)

    print("Configuration loaded successfully.")

def send_output(output_method, recipient_email, subject, output_file, channel_folder, api):
    markdown_content = get_or_update_claude_cache(
        channel_folder, 
        subject,
        output_file,
        api
    )

    # if not api and no markdown_content, return
    if not api and not markdown_content:
        return

    if output_method == 'mail' or output_method == 'ses':
        html_content = markdown.markdown(markdown_content)
        if output_method == 'mail':
            send_email_smtp(recipient_email, subject, html_content)
        else:  # ses
            send_email_ses(recipient_email, subject, html_content)
    elif output_method == 'console':
        print_console(markdown_content)
    else:
        print(f"Unsupported output method: {output_method}")

def send_email_smtp(recipient_email, subject, body):
    msg = MIMEMultipart()
    msg['From'] = EMAIL_ADDRESS
    msg['To'] = recipient_email
    msg['Subject'] = subject

    msg.attach(MIMEText(body, 'html'))

    try:
        if SMTP_USE_TLS:
            server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
            server.starttls()
        else:
            server = smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT)
        
        server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
        server.send_message(msg)
        server.quit()
        print("Email sent successfully via SMTP")
    except Exception as e:
        print(f"Error sending email via SMTP: {e}")

def send_email_ses(recipient_email, subject, body):
    try:
        ses_client = boto3.client('ses', 
                                  region_name=AWS_REGION,
                                  aws_access_key_id=AWS_ACCESS_KEY_ID,
                                  aws_secret_access_key=AWS_SECRET_ACCESS_KEY)
        
        response = ses_client.send_email(
            Source=EMAIL_ADDRESS,
            Destination={
                'ToAddresses': [recipient_email],
            },
            Message={
                'Subject': {
                    'Data': subject,
                },
                'Body': {
                    'Html': {
                        'Data': body,
                    },
                },
            },
        )
        print("Email sent successfully via Amazon SES")
    except Exception as e:
        print(f"Error sending email via Amazon SES: {e}")

def print_console(body):
    print("\n--- Output ---\n")
    print(body)
    print("\n--- End of Output ---\n")

def slugify(text):
    # Convert to lowercase
    text = text.lower()
    # Remove non-word characters (everything except numbers and letters)
    text = re.sub(r'[^\w\s-]', '', text)
    # Replace all runs of whitespace with a single dash
    text = re.sub(r'\s+', '-', text)
    return text


def get_video_info(video_id):
    youtube = build('youtube', 'v3', developerKey=YOUTUBE_API_KEY)
    request = youtube.videos().list(
        part="snippet",
        id=video_id
    )
    response = request.execute()
    if 'items' in response and len(response['items']) > 0:
        snippet = response['items'][0]['snippet']
        return {
            'id': video_id,
            'title': snippet['title'],
            'description': snippet['description'],
            'publishedAt': snippet['publishedAt'],
            'channelTitle': snippet['channelTitle'],
            'channelId': snippet['channelId']
        }
    return None

def get_playlist_info(playlist_id):
    youtube = build('youtube', 'v3', developerKey=YOUTUBE_API_KEY)
    request = youtube.playlists().list(
        part="snippet",
        id=playlist_id
    )
    response = request.execute()
    if 'items' in response and len(response['items']) > 0:
        return response['items'][0]['snippet']
    return None

def get_channel_info(channel_id):
    youtube = build('youtube', 'v3', developerKey=YOUTUBE_API_KEY)
    request = youtube.channels().list(
        part="snippet",
        id=channel_id
    )
    response = request.execute()
    if 'items' in response and len(response['items']) > 0:
        return response['items'][0]['snippet']
    return None

def get_video_ids_from_playlist(playlist_id):
    youtube = build('youtube', 'v3', developerKey=YOUTUBE_API_KEY)
    
    video_ids = []
    next_page_token = None
    
    while True:
        pl_request = youtube.playlistItems().list(
            part='contentDetails',
            playlistId=playlist_id,
            maxResults=50,
            pageToken=next_page_token
        )
        
        pl_response = pl_request.execute()
        
        for item in pl_response['items']:
            video_ids.append(item['contentDetails']['videoId'])
        
        next_page_token = pl_response.get('nextPageToken')
        
        if not next_page_token:
            break
    
    return video_ids

def get_transcript(video_id):
    try:
        transcript = YouTubeTranscriptApi.get_transcript(video_id)
        return transcript
    except Exception as e:
        print(f"Error fetching transcript for video {video_id} using YouTube Transcript API: {str(e)}")
        print("Attempting to fetch transcript using 'yt' command...")
        
        try:
            video_url = f"https://www.youtube.com/watch?v={video_id}"
            result = subprocess.run(['yt', '--transcript', video_url], capture_output=True, text=True, check=True)
            lines = result.stdout.strip().split('\n')
            transcript = [{'text': line, 'start': i * 5, 'duration': 5} for i, line in enumerate(lines)]
            print(f"Successfully fetched transcript for video {video_id} using 'yt' command.")
            return transcript
        except subprocess.CalledProcessError as e:
            print(f"Error fetching transcript for video {video_id} using 'yt' command: {str(e)}")
            
    print(f"Unable to fetch transcript for video {video_id}. Returning placeholder.")
    return [{'text': "Transcript unavailable for this video.", 'start': 0, 'duration': 0}]

def load_or_create_cache(cache_file):
    if os.path.exists(cache_file):
        with open(cache_file, 'r') as f:
            return json.load(f)
    return {}

def save_cache(cache_file, cache):
    with open(cache_file, 'w') as f:
        json.dump(cache, f)

def get_or_update_cache(cache, video_id, video_info):
    if video_id not in cache:
        transcript = get_transcript(video_id)
        cache[video_id] = {
            'info': video_info,
            'transcript': transcript
        }
    return cache[video_id]

def get_or_update_claude_cache(cache_dir, subject, file_path, api):
    slug = slugify(subject)
    cache_file = os.path.join(cache_dir, f"{slug}.md")
    if os.path.exists(cache_file):
        print(f"Using cached Claude response for '{subject}'")
        with open(cache_file, 'r', encoding='utf-8') as f:
            return f.read()

    # If --api argument is provided, generate response using Claude API
    if api:
        # If not in cache, generate new response from Claude
        markdown_content = generate_claude_response(subject, file_path)
        
        # Update cache with the markdown content
        with open(cache_file, 'w', encoding='utf-8') as f:
            f.write(markdown_content)
        
        return markdown_content
    else:
        copy_to_clipboard(file_path)

def copy_to_clipboard(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            content = file.read()
        subprocess.run(['pbcopy'], input=content.encode('utf-8'), check=True)
        print(f"Content of {file_path} has been copied to clipboard.")
    except subprocess.CalledProcessError as e:
        print(f"Error copying to clipboard: {e}")
    except IOError as e:
        print(f"Error reading file: {e}")

def generate_claude_response(subject, file_path):
    with open(file_path, 'r', encoding='utf-8') as file:
        content = file.read()
    
    with open(PROMPT_FILE_PATH, 'r', encoding='utf-8') as prompt_file:
        prompt = prompt_file.read()
    
    headers = {
        'Content-Type': 'application/json',
        'x-api-key': CLAUDE_API_KEY,
        'anthropic-version': '2023-06-01'
    }
    
    payload = {
        'model': 'claude-3-sonnet-20240229',
        'messages': [
            {
                'role': 'user',
                'content': [
                    {
                        'type': 'text',
                        'text': prompt
                    },
                    {
                        'type': 'text',
                        'text': f"Subject: {subject}"
                    },
                    {
                        'type': 'text',
                        'text': content
                    }
                ]
            }
        ],
        'max_tokens': 4096
    }
    
    response = requests.post('https://api.anthropic.com/v1/messages', json=payload, headers=headers)
    
    if response.status_code == 401:
        raise Exception("Authentication failed. Please check your API key and ensure it's correctly set in the config file.")
    
    response.raise_for_status()
    
    claude_response = response.json()['content'][0]['text']
    
    print(f"Claude's response generated for subject: '{subject}'")
    
    return claude_response


def save_transcript_to_text(output_file, video_data):
    video_info = video_data['info']
    transcript = video_data['transcript']
    
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(f"VIDEO_ID: {video_info['id']}\n")
        f.write(f"TITLE: {video_info['title']}\n")
        f.write(f"CHANNEL: {video_info['channelTitle']}\n")
        f.write(f"PUBLISHED AT: {video_info['publishedAt']}\n")
        f.write(f"DESCRIPTION: {video_info['description']}\n\n")
        f.write("TRANSCRIPT:\n\n")
        if transcript[0]['text'] == "Transcript unavailable for this video.":
            f.write(transcript[0]['text'] + "\n")
        else:
            for entry in transcript:
                start_time = entry['start']
                text = entry['text'].replace('\n', ' ')
                f.write(f"{start_time:.2f}: {text}\n")
    
    print(f"Saved information for video '{video_info['title']}' to {output_file}")

def process_video(video_id, cache, channel_folder, output_method, recipient_email, subject, api):
    video_info = get_video_info(video_id)
    if not video_info:
        print(f"Could not fetch information for video {video_id}")
        return

    video_data = get_or_update_cache(cache, video_id, video_info)
    video_slug = slugify(video_info['title'])
    output_file = os.path.join(channel_folder, f"{video_slug}.txt")
    save_transcript_to_text(output_file, video_data)

    # Use "LearnThis: [Video Title]" as subject if it's blank
    if not subject.strip():
        subject = f"LearnThis: {video_info['title']}"
    
    send_output(output_method, recipient_email, subject, output_file, channel_folder, api)

def process_playlist(playlist_id, cache, channel_folder, output_method, recipient_email, subject, api):
    playlist_info = get_playlist_info(playlist_id)
    if not playlist_info:
        print(f"Could not fetch information for playlist {playlist_id}")
        return

    playlist_slug = slugify(playlist_info['title'])
    output_file = os.path.join(channel_folder, f"{playlist_slug}.txt")
    
    video_ids = get_video_ids_from_playlist(playlist_id)
    
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(f"PLAYLIST: {playlist_info['title']}\n\n")
        for video_id in video_ids:
            video_info = get_video_info(video_id)
            if not video_info:
                print(f"Could not fetch information for video {video_id}")
                continue

            video_data = get_or_update_cache(cache, video_id, video_info)
            f.write(f"VIDEO_ID: {video_info['id']}\n")
            f.write(f"TITLE: {video_info['title']}\n")
            f.write(f"CHANNEL: {video_info['channelTitle']}\n")
            f.write(f"PUBLISHED AT: {video_info['publishedAt']}\n")
            f.write(f"DESCRIPTION: {video_info['description']}\n\n")
            f.write("TRANSCRIPT:\n\n")
            transcript = video_data['transcript']
            if transcript[0]['text'] == "Transcript unavailable for this video.":
                f.write(transcript[0]['text'] + "\n")
            else:
                for entry in transcript:
                    start_time = entry['start']
                    text = entry['text'].replace('\n', ' ')
                    f.write(f"{start_time:.2f}: {text}\n")
            f.write("\n" + "="*50 + "\n\n")
    
    print(f"Saved information for playlist '{playlist_info['title']}' to {output_file}")

    # Use "LearnThis: [Playlist Title]" as subject if it's blank
    if not subject.strip():
        subject = f"LearnThis: {playlist_info['title']}"
    
    send_output(output_method, recipient_email, subject, output_file, channel_folder, api)

def copy_to_clipboard(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            content = file.read()
        subprocess.run(['pbcopy'], input=content.encode('utf-8'), check=True)
        print(f"Content of {file_path} has been copied to clipboard.")
    except subprocess.CalledProcessError as e:
        print(f"Error copying to clipboard: {e}")
    except IOError as e:
        print(f"Error reading file: {e}")

def extract_video_id(url):
    # Handle various YouTube URL formats
    patterns = [
        r'(?:https?:\/\/)?(?:www\.)?youtube\.com\/watch\?v=([^&]+)',
        r'(?:https?:\/\/)?(?:www\.)?youtube\.com\/embed\/([^?]+)',
        r'(?:https?:\/\/)?(?:www\.)?youtube\.com\/v\/([^?]+)',
        r'(?:https?:\/\/)?(?:www\.)?youtube\.com\/shorts\/([^?]+)',
        r'(?:https?:\/\/)?(?:www\.)?youtube\.com\/live\/([^?]+)',
        r'(?:https?:\/\/)?youtu\.be\/([^?]+)',
        r'(?:https?:\/\/)?(?:www\.)?youtube\.com\/watch\/([^?]+)'
    ]
    
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1), None
    
    # Check for playlist
    playlist_pattern = r'(?:https?:\/\/)?(?:www\.)?youtube\.com\/playlist\?list=([^&]+)'
    playlist_match = re.search(playlist_pattern, url)
    if playlist_match:
        return None, playlist_match.group(1)
    return None, None

def main():
    load_config()
    
    parser = argparse.ArgumentParser(description="Process YouTube video or playlist and generate output.")
    parser.add_argument("--output", choices=['console', 'mail', 'ses'], default='console', help="Output method (default: console)")
    parser.add_argument("--api", action="store_true", default=False, help="Use API mode")
    args = parser.parse_args()

    # Prompt for inputs
    url = input("Enter YouTube video or playlist URL: ")
    subject = input("Enter subject (optional, press Enter to skip): ")
    
    if args.output in ['mail', 'ses']:
        recipient_email = input("Enter recipient email: ")
    else:
        recipient_email = None

    video_id, playlist_id = extract_video_id(url)
    
    if video_id:
        # Single video
        video_info = get_video_info(video_id)
        if not video_info:
            print(f"Could not fetch information for video {video_id}")
            return 1
        channel_info = get_channel_info(video_info['channelId'])
    elif playlist_id:
        # Playlist
        playlist_info = get_playlist_info(playlist_id)
        if not playlist_info:
            print(f"Could not fetch information for playlist {playlist_id}")
            return 1
        channel_info = get_channel_info(playlist_info['channelId'])
    else:
        print("Invalid URL. Please provide a valid YouTube video or playlist URL.")
        return 1
    
    if not channel_info:
        print(f"Could not fetch information for channel")
        return 1

    channel_slug = slugify(channel_info['title'])
    channel_folder = os.path.join('data', channel_slug)
    os.makedirs(channel_folder, exist_ok=True)
    
    cache_file = os.path.join(channel_folder, 'cache.json')
    cache = load_or_create_cache(cache_file)
    
    if playlist_id:
        process_playlist(playlist_id, cache, channel_folder, args.output, recipient_email, subject, args.api)
    else:
        process_video(video_id, cache, channel_folder, args.output, recipient_email, subject, args.api)
   
    save_cache(cache_file, cache)
    return 0

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)