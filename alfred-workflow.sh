#!/bin/bash

# Activate virtual environment
source venv/bin/activate

# Run the Python script and capture its output
output=$(python src/playlist_transcript_saver.py "$1")

# Extract the file path from the output
file_path=$(echo "$output" | grep "FILE_PATH:" | awk -F "FILE_PATH: " '{print $2}')

# Check if the file exists
if [ ! -f "$file_path" ]; then
    echo "{\"items\":[{\"title\":\"Error\",\"subtitle\":\"Transcript file not found\",\"arg\":\"error\"}]}"
    exit 1
fi

# Read the content of the file and copy it to clipboard
content=$(cat "$file_path")
echo "$content" | pbcopy

# Get the filename for Alfred feedback
filename=$(basename "$file_path")

# Create Alfred JSON output
cat << EOF
{"items": [
  {
    "title": "Transcript copied to clipboard",
    "subtitle": "From file: $filename",
    "arg": "$content",
    "text": {
      "copy": "$content",
      "largetype": "$content"
    }
  }
]}
EOF

# Deactivate virtual environment
deactivate