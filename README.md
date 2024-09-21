# Podcast Content Optimizer

This project is designed to process podcast audio files, transcribe them, and identify specific segments for potential removal or editing. It uses advanced speech recognition and natural language processing techniques to enhance the listening experience by focusing on the most relevant content.

## Project Structure

## Features

- Download podcast episodes from a given URL
- Transcribe audio using OpenAI's Whisper model
- Analyze transcripts using AI to identify specific content segments
- Support for multiple AI providers (OpenAI GPT and Google Gemini)
- Generate timestamped transcripts and content analysis reports
- Search for podcasts using the Taddy API
- Web interface for podcast selection and processing
- Automatic generation of new magical RSS feeds
- Caching system for improved performance

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

## Taddy API Setup

To use the Taddy API for podcast search functionality, you need to set up the following:

1. Sign up for a Taddy API account at [https://taddy.org](https://taddy.org)

2. Once you have your account, obtain your API key and User ID from the Taddy dashboard.

3. In your `.env` file, add the following lines:
   ```
   TADDY_API_URL=https://api.taddy.org
   TADDY_API_KEY=your_taddy_api_key_here
   TADDY_USER_ID=your_taddy_user_id_here
   ```
   Replace `your_taddy_api_key_here` and `your_taddy_user_id_here` with your Taddy API key and User ID.

## Usage

1. Start the celery worker:
   ```
   celery -A celery_app worker --loglevel=info
   ```

1. Start the Flask application:
   ```
   python -m flask --app wsgi run --host 0.0.0.0
   ```

2. Start the React frontend:
   ```
   npm start
   ```

3. Open a web browser and navigate to `http://localhost:3000`.

3. Use the search functionality to find podcasts, or enter an RSS URL directly.

4. Select an episode to process.

5. The application will:
   - Download the podcast if it's not already present
   - Transcribe the audio
   - Analyze the transcript to identify specific content segments
   - Generate output files in the `output/` directory
   - Create a modified RSS feed with links to the edited content

## Output

- `transcript.txt`: A timestamped transcript of the podcast
- `unwanted_content.json`: A JSON file containing identified content segments
- `edited_audio.mp3`: An edited version of the podcast with unwanted content removed
- Modified RSS feed: An updated RSS feed with links to the edited content

## Customization

You can customize the content identification process by modifying the prompts in the `find_unwanted_content` function within `llm_processor.py`.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the LICENSE file for details.
