import logging
import openai
from pydub import AudioSegment
import os

def transcribe_audio(input_file, output_file):
    logging.info(f"Transcribing audio file: {input_file}")
    try:
        # Convert audio to WAV format (OpenAI API requires WAV)
        audio = AudioSegment.from_mp3(input_file)
        wav_file = input_file.replace('.mp3', '.wav')
        audio.export(wav_file, format="wav")

        # Transcribe using OpenAI's Whisper model
        with open(wav_file, "rb") as audio_file:
            transcript = openai.Audio.transcribe("whisper-1", audio_file)

        # Write transcript to file
        with open(output_file, 'w') as f:
            f.write(transcript['text'])

        logging.info(f"Transcription saved to: {output_file}")

        # Clean up temporary WAV file
        os.remove(wav_file)

    except Exception as e:
        logging.error(f"Error transcribing audio: {str(e)}")
        raise
