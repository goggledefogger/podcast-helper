from firebase_admin import storage
import json
import logging

PROCESSED_PODCASTS_FILE = 'db.json'

def load_prompt(model):
    try:
        blob = storage.bucket().blob(PROCESSED_PODCASTS_FILE)
        if blob.exists():
            json_data = blob.download_as_text()
            data = json.loads(json_data)
            prompts = data.get('prompts', {})
            return prompts.get(model, "")
        else:
            # If the file doesn't exist, return default prompts
            default_prompts = {
                'openai': "Identify unwanted content in the following transcript...",
                'gemini': "Find and list sections of unwanted content in this podcast transcript..."
            }
            return default_prompts.get(model, "")
    except Exception as e:
        logging.error(f"Error loading prompts from Firebase: {str(e)}")
        return ""
