from pydub import AudioSegment
import logging
from utils import run_with_animation
import time
import re

def time_to_seconds(time_str):
    try:
        # First, try to parse as float (assuming it's already in seconds)
        return float(time_str)
    except ValueError:
        # If that fails, try to parse as MM:SS or HH:MM:SS
        time_parts = time_str.split(':')
        if len(time_parts) == 2:
            return int(time_parts[0]) * 60 + float(time_parts[1])
        elif len(time_parts) == 3:
            return int(time_parts[0]) * 3600 + int(time_parts[1]) * 60 + float(time_parts[2])
        else:
            # If the format is unexpected, try to extract numbers and assume they're seconds
            numbers = re.findall(r'\d+\.?\d*', time_str)
            if numbers:
                return float(numbers[0])
            else:
                logging.error(f"Could not parse time: {time_str}")
                return 0

def edit_audio(input_file, output_file, unwanted_content):
    logging.info("Starting audio editing process")
    try:
        audio = AudioSegment.from_mp3(input_file)
    except Exception as e:
        logging.error(f"Error loading audio file: {str(e)}")
        raise

    # Sort unwanted content by start time
    unwanted_content.sort(key=lambda x: time_to_seconds(x['start_time']))

    # Create a new audio file with unwanted content removed
    edited_audio = AudioSegment.empty()
    last_end = 0
    total_segments = len(unwanted_content)

    def process_segments():
        nonlocal last_end, edited_audio
        for i, segment in enumerate(unwanted_content, 1):
            try:
                start = max(0, int(time_to_seconds(segment['start_time']) * 1000))  # Convert to milliseconds, ensure non-negative
                end = max(start, int(time_to_seconds(segment['end_time']) * 1000))  # Ensure end is not before start

                # Add the audio before the unwanted content
                edited_audio += audio[last_end:start]

                # Update the last_end to the end of this unwanted segment
                last_end = end

                logging.info(f"Processed segment {i}/{total_segments}: {segment['description']} (from {start/1000:.2f}s to {end/1000:.2f}s)")
            except Exception as e:
                logging.error(f"Error processing segment {i}: {str(e)}")
                # Continue with the next segment

    # Run the segment processing with animation
    run_with_animation(process_segments)

    # Add any remaining audio after the last unwanted segment
    edited_audio += audio[last_end:]

    logging.info("Exporting edited audio...")
    # Export the edited audio with animation
    try:
        run_with_animation(edited_audio.export, output_file, format="mp3")
        logging.info(f"Edited audio saved to {output_file}")
    except Exception as e:
        logging.error(f"Error exporting edited audio: {str(e)}")
        raise
