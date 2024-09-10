from pydub import AudioSegment
import logging
from utils import run_with_animation

def edit_audio(input_file, output_file, unwanted_content):
    logging.info("Starting audio editing process")
    audio = AudioSegment.from_mp3(input_file)

    # Sort unwanted content by start time
    unwanted_content.sort(key=lambda x: float(x['start_time']))

    # Create a new audio file with unwanted content removed
    edited_audio = AudioSegment.empty()
    last_end = 0
    total_segments = len(unwanted_content)

    def process_segments():
        nonlocal last_end, edited_audio
        for i, segment in enumerate(unwanted_content, 1):
            start = float(segment['start_time']) * 1000  # Convert to milliseconds
            end = float(segment['end_time']) * 1000

            # Add the audio before the unwanted content
            edited_audio += audio[last_end:start]

            # Update the last_end to the end of this unwanted segment
            last_end = end

            logging.info(f"Processed segment {i}/{total_segments}: {segment['description']}")

        # Add any remaining audio after the last unwanted segment
        edited_audio += audio[last_end:]

    # Run the segment processing with animation
    run_with_animation(process_segments)

    logging.info("Exporting edited audio...")
    # Export the edited audio with animation
    run_with_animation(edited_audio.export, output_file, format="mp3")
    logging.info(f"Edited audio saved to {output_file}")
