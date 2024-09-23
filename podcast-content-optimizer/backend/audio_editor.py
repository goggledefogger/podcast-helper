import logging
from pydub import AudioSegment
from utils import parse_duration  # Changed from time_utils import parse_duration

def edit_audio(input_file, output_file, unwanted_content):
    logging.info(f"Editing audio file: {input_file}")
    try:
        if not unwanted_content:
            logging.info("No unwanted content to remove. Copying original file.")
            AudioSegment.from_mp3(input_file).export(output_file, format="mp3")
            return

        audio = AudioSegment.from_mp3(input_file)
        edited_audio = audio

        # Sort unwanted content by start time
        unwanted_content.sort(key=lambda x: parse_duration(x['start_time']))

        # Remove unwanted segments
        for segment in reversed(unwanted_content):
            start_time = parse_duration(segment['start_time']) * 1000  # Convert to milliseconds
            end_time = parse_duration(segment['end_time']) * 1000  # Convert to milliseconds
            edited_audio = edited_audio[:start_time] + edited_audio[end_time:]

        # Export the edited audio
        edited_audio.export(output_file, format="mp3")
        logging.info(f"Edited audio saved to: {output_file}")
    except Exception as e:
        logging.error(f"Error editing audio: {str(e)}")
        raise
