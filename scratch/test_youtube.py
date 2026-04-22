import httpx
import os
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.environ.get("Youtube_Data_API_V3")
QUERY = "brooklyn 99 clips"
YOUTUBE_SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"

def test_search():
    if not API_KEY:
        print("API Key not found in .env")
        return

    params = {
        "part": "snippet",
        "q": QUERY,
        "type": "video",
        "maxResults": 5,
        "key": API_KEY
    }
    
    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.get(YOUTUBE_SEARCH_URL, params=params)
            resp.raise_for_status()
            data = resp.json()

        items = data.get("items", [])
        if not items:
            print("No videos found.")
            return

        print(f"Search results for '{QUERY}':")
        for i, item in enumerate(items):
            video_id = item["id"]["videoId"]
            title = item["snippet"]["title"]
            print(f"{i+1}. {title} (https://www.youtube.com/watch?v={video_id})")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_search()
