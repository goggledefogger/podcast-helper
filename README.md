# Podcast Content Optimizer

This project is designed to process podcast audio files, transcribe them, and identify specific segments for potential removal or editing. It uses advanced speech recognition and natural language processing techniques to enhance the listening experience by focusing on the most relevant content.

## Features

- Download podcast episodes from a given URL
- Transcribe audio using OpenAI's Whisper model
- Analyze transcripts using AI to identify specific content segments
- Support for multiple AI providers (OpenAI GPT and Google Gemini)
- Generate timestamped transcripts and content analysis reports

## Requirements

- Python 3.7+
- FFmpeg (for audio processing)

## Installation

1. Clone this repository:
   ```
   git clone https://github.com/yourusername/podcast-content-optimizer.git
   cd podcast-content-optimizer
   ```

2. Install the required Python packages:
   ```
   pip install -r requirements.txt
   ```

3. Copy the `sample.env` file to `.env` and fill in your API keys:
   ```
   cp sample.env .env
   ```
   Then edit the `.env` file with your preferred text editor and add your API keys.

## Usage

1. Set the `PODCAST_URL` variable in `start.py` to the URL of the podcast episode you want to process.

2. Run the script:
   ```
   python start.py
   ```

3. The script will:
   - Download the podcast if it's not already present
   - Transcribe the audio
   - Analyze the transcript to identify specific content segments
   - Generate output files in the `output/` directory

## Output

- `transcript.txt`: A timestamped transcript of the podcast
- `content_segments.json`: A JSON file containing identified content segments

## Customization

You can customize the content identification process by modifying the prompts in the `find_content_segments` function within `start.py`.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the LICENSE file for details.
