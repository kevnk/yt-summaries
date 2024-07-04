import os
import re
import json
import subprocess
from urllib.parse import parse_qs, urlparse
from googleapiclient.discovery import build
from youtube_transcript_api import YouTubeTranscriptApi

# YouTube API key will be loaded from config file
YOUTUBE_API_KEY = ''

def load_config():
    global YOUTUBE_API_KEY
    with open('config/config.env', 'r') as f:
        for line in f:
            if line.startswith('YOUTUBE_API_KEY'):
                YOUTUBE_API_KEY = line.split('=')[1].strip()
                break

def slugify(text):
    text = text.lower()
    text = re.sub(r'\s+', '-', text)
    text = re.sub(r'[^\w\-]', '', text)
    text = re.sub(r'-+', '-', text)
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

def load_cache(cache_file):
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

def process_video(video_id, cache, channel_folder):
    video_info = get_video_info(video_id)
    if not video_info:
        print(f"Could not fetch information for video {video_id}")
        return

    video_data = get_or_update_cache(cache, video_id, video_info)
    video_slug = slugify(video_info['title'])
    output_file = os.path.join(channel_folder, f"{video_slug}.txt")
    save_transcript_to_text(output_file, video_data)

def process_playlist(playlist_id, cache, channel_folder):
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

def extract_video_id(url):
    # Handle standard YouTube URLs
    parsed_url = urlparse(url)
    if parsed_url.netloc in ['www.youtube.com', 'youtube.com']:
        query_params = parse_qs(parsed_url.query)
        if 'v' in query_params:
            return query_params['v'][0]
    
    # Handle shortened YouTube URLs
    if parsed_url.netloc == 'youtu.be':
        return parsed_url.path.lstrip('/')
    
    return None

def main(url):
    load_config()
    video_id = extract_video_id(url)
    
    if video_id:
        # Single video
        video_info = get_video_info(video_id)
        if not video_info:
            print(f"Could not fetch information for video {video_id}")
            return
        channel_info = get_channel_info(video_info['channelId'])
    else:
        parsed_url = urlparse(url)
        query_params = parse_qs(parsed_url.query)
        if 'list' in query_params:
            # Playlist
            playlist_id = query_params['list'][0]
            playlist_info = get_playlist_info(playlist_id)
            if not playlist_info:
                print(f"Could not fetch information for playlist {playlist_id}")
                return
            channel_info = get_channel_info(playlist_info['channelId'])
        else:
            print("Invalid URL. Please provide a valid YouTube video or playlist URL.")
            return
    
    if not channel_info:
        print(f"Could not fetch information for channel")
        return

    channel_slug = slugify(channel_info['title'])
    channel_folder = os.path.join('data', channel_slug)
    os.makedirs(channel_folder, exist_ok=True)
    
    cache_file = os.path.join(channel_folder, 'cache.json')
    cache = load_cache(cache_file)
    
    if video_id:
        process_video(video_id, cache, channel_folder)
    else:
        process_playlist(playlist_id, cache, channel_folder)
    
    save_cache(cache_file, cache)

if __name__ == "__main__":
    url = input("Enter the YouTube video or playlist URL: ")
    main(url)