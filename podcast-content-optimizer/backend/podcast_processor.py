import os
import json
import logging
from utils import download_episode, get_podcast_episodes
from llm_processor import find_unwanted_content
from audio_editor import edit_audio
from transcriber import transcribe_audio  # New import

def process_podcast_episode(rss_url, episode_index=0):
    logging.info(f"Processing podcast from RSS: {rss_url}, episode index: {episode_index}")

    episodes = get_podcast_episodes(rss_url)
    if not episodes or episode_index >= len(episodes):
        logging.error("Invalid episode index or no episodes found")
        return {"error": "Invalid episode index or no episodes found"}

    episode = episodes[episode_index]
    podcast_title = episode['podcast_title']
    episode_title = episode['title']

    output_dir = os.path.join('output', podcast_title, episode_title)
    os.makedirs(output_dir, exist_ok=True)

    audio_file = os.path.join(output_dir, 'original.mp3')
    transcript_file = os.path.join(output_dir, 'transcript.txt')
    unwanted_content_file = os.path.join(output_dir, 'unwanted_content.json')
    edited_audio_file = os.path.join(output_dir, 'edited.mp3')

    download_episode(episode['url'], audio_file)
    transcribe_audio(audio_file, transcript_file)
    unwanted_content = find_unwanted_content(transcript_file)

    with open(unwanted_content_file, 'w') as f:
        json.dump(unwanted_content, f, indent=2)

    edit_audio(audio_file, edited_audio_file, unwanted_content)

    return {
        "podcast_title": podcast_title,
        "episode_title": episode_title,
        "transcript_file": transcript_file,
        "unwanted_content_file": unwanted_content_file,
        "edited_audio_file": edited_audio_file
    }
