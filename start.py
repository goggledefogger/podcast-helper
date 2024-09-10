import os
import whisper
import subprocess
from dotenv import load_dotenv
import json
import google.generativeai as genai
from openai import OpenAI

# Load environment variables
load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "openai")

PODCAST_URL = "https://stitcher.simplecastaudio.com/9aa1e238-cbed-4305-9808-c9228fc6dd4f/episodes/ef4721f6-39a1-4075-b21b-b05dfc26f086/audio/128/default.mp3/default.mp3_ywr3ahjkcgo_a1a6d42bd0297a26ad62f222dd52ac1c_80334171.mp3?aid=rss_feed&awCollectionId=9aa1e238-cbed-4305-9808-c9228fc6dd4f&awEpisodeId=ef4721f6-39a1-4075-b21b-b05dfc26f086&feed=dxZsm5kX&hash_redirect=1&x-total-bytes=80334171&x-ais-classified=streaming&listeningSessionID=0CD_382_252__ad5dd98195acb6cf22b0681921726486f94a4815"

def find_advertisement_breaks(transcript_file_path):
    # Read the transcript from the file
    with open(transcript_file_path, "r") as file:
        transcript = file.read()

    if LLM_PROVIDER == "openai":
        client = OpenAI(api_key=OPENAI_API_KEY)
        response = client.chat.completions.create(
            model="gpt-3.5-turbo-16k",
            messages=[
                {
                    "role": "system",
                    "content": "You are a helpful assistant that helps find advertisement breaks in transcripts."
                },
                {
                    "role": "user",
                    "content": (
                        "Here is a transcript, please identify the start and end times of sections that contain advertisement breaks.\n" +
                        "Provide the output as a JSON array where each object has 'start_time', 'end_time', and 'description' keys.\n" +
                        "Example format: [{'start_time': '00:10:15', 'end_time': '00:12:45', 'description': 'Advertisement break 1'}].\n" +
                        "Here is the transcript:\n\n" +
                        f"{transcript}"
                    )
                }
            ],
            max_tokens=16000
        )
        return response.choices[0].message.content

    elif LLM_PROVIDER == "gemini":
        genai.configure(api_key=GOOGLE_API_KEY)
        model = genai.GenerativeModel('gemini-pro')
        response = model.generate_content(
            "You are a helpful assistant that helps find advertisement breaks in transcripts.\n\n" +
            "Here is a transcript, please identify the start and end times of sections that contain advertisement breaks.\n" +
            "Provide the output as a JSON array where each object has 'start_time', 'end_time', and 'description' keys.\n" +
            "Example format: [{'start_time': '00:10:15', 'end_time': '00:12:45', 'description': 'Advertisement break 1'}].\n" +
            "Here is the transcript:\n\n" +
            f"{transcript}"
        )
        return response.text

    else:
        raise ValueError(f"Unsupported LLM provider: {LLM_PROVIDER}")

# If the file podcast_uncut.mp3 doesn't yet exist, download the podcast and rename it to podcast_uncut.mp3
if not os.path.exists("podcast_uncut.mp3"):
    print("Downloading podcast...")
    podcast_url = PODCAST_URL
    subprocess.run(["wget", podcast_url, "-O", "podcast_uncut.mp3"])
    print("Downloaded podcast")

print("Running Whisper...")

# Run Whisper to transcribe
model = whisper.load_model("base")
result = model.transcribe("podcast_uncut.mp3")

print("Whisper complete")

# Output the transcription to a file that includes timestamps
with open("output/transcript.txt", "w") as f:
    for i, item in enumerate(result["segments"]):
        f.write(f"{item['start']} - {item['end']}: {item['text']}\n")

print("Transcription complete")

# Send the transcription to the selected LLM to identify timestamps of ads
ad_breaks = find_advertisement_breaks("output/transcript.txt")

print("LLM processing complete")

# Parse the ad_breaks JSON
try:
    ad_breaks_data = json.loads(ad_breaks)
except json.JSONDecodeError as e:
    print(f"Error parsing JSON: {e}")
    exit(1)

# write the ad_breaks_data to a file
with open("output/ad_breaks.json", "w") as f:
    json.dump(ad_breaks_data, f)

# TODO: take the ad_breaks_data and remove the segments at those specified times from the uncut audio
# and save the output to a new file that has the original audio but with the ads removed
