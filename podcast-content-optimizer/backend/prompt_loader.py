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
            logging.warning(f"Prompts file not found: {PROCESSED_PODCASTS_FILE}")
            return ""
    except Exception as e:
        logging.error(f"Error loading prompts from Firebase: {str(e)}")
        return ""
