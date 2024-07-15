#!/bin/bash

cd ~/Sites/llm/youtube-summaries/

# Activate virtual environment
source venv/bin/activate

# Run the Python script with all passed arguments
python src/playlist_transcript_saver.py "$@"

# Deactivate virtual environment (optional)
deactivate