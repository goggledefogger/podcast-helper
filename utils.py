import feedparser
import requests
from tqdm import tqdm
import sys
import threading
import time

def get_podcast_episodes(rss_url):
    feed = feedparser.parse(rss_url)
    episodes = []
    for entry in feed.entries:
        for link in entry.links:
            if link.type == 'audio/mpeg':
                episodes.append({
                    'title': entry.title,
                    'url': link.href,
                    'published': entry.published
                })
                break
    return episodes

def download_episode(url, filename):
    response = requests.get(url, stream=True)
    total_size = int(response.headers.get('content-length', 0))
    block_size = 1024  # 1 KB

    with open(filename, 'wb') as file, tqdm(
        desc=filename,
        total=total_size,
        unit='iB',
        unit_scale=True,
        unit_divisor=1024,
    ) as progress_bar:
        for data in response.iter_content(block_size):
            size = file.write(data)
            progress_bar.update(size)

def choose_episode(episodes):
    total_episodes = len(episodes)
    current_page = 0
    episodes_per_page = 10

    while True:
        start_index = current_page * episodes_per_page
        end_index = min(start_index + episodes_per_page, total_episodes)

        print(f"\nShowing episodes {start_index + 1} to {end_index} of {total_episodes}:")
        for i, episode in enumerate(episodes[start_index:end_index], start_index + 1):
            print(f"{i}. {episode['title']} - {episode['published']}")

        print("\nOptions:")
        print("Enter a number to select an episode")
        if current_page > 0:
            print("P: Previous page")
        if end_index < total_episodes:
            print("N: Next page")
        print("Q: Quit")

        choice = input("Enter your choice: ").strip().lower()

        if choice == 'q':
            print("Exiting...")
            sys.exit(0)
        elif choice == 'p' and current_page > 0:
            current_page -= 1
        elif choice == 'n' and end_index < total_episodes:
            current_page += 1
        elif choice.isdigit():
            episode_num = int(choice)
            if 1 <= episode_num <= total_episodes:
                return episodes[episode_num - 1]
            else:
                print("Invalid episode number. Please try again.")
        else:
            print("Invalid input. Please try again.")

def animate(stop_event):
    chars = "|/-\\"
    i = 0
    while not stop_event.is_set():
        sys.stdout.write('\r' + 'Processing ' + chars[i % len(chars)])
        sys.stdout.flush()
        time.sleep(0.1)
        i += 1

def run_with_animation(task, *args, message="Processing", **kwargs):
    stop_event = threading.Event()

    def animate():
        chars = "|/-\\"
        i = 0
        while not stop_event.is_set():
            sys.stdout.write(f'\r{message} ' + chars[i % len(chars)])
            sys.stdout.flush()
            time.sleep(0.1)
            i += 1

    animation_thread = threading.Thread(target=animate)
    animation_thread.start()

    try:
        result = task(*args, **kwargs)
    finally:
        stop_event.set()
        animation_thread.join()
        sys.stdout.write('\r' + ' ' * (len(message) + 20) + '\r')  # Clear the animation line
        sys.stdout.flush()

    return result
