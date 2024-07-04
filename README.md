# YouTube Summaries Project

This project contains scripts for processing YouTube playlists and videos.

## Setup

1. Ensure you have Python 3.7+ installed.
2. Run the setup script: `./setup.sh`
3. Add your YouTube API key to `config/config.txt`

## Usage

To run the playlist transcript saver:

1. Activate the virtual environment: `source venv/bin/activate`
2. Run the script: `python src/playlist_transcript_saver.py`
3. Enter the YouTube playlist URL when prompted.

Transcripts will be saved in the `data` directory.
