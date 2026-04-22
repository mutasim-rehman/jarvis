import httpx
import logging
import os
import sys
import subprocess
import webbrowser
from typing import List, Dict, Any
from shared.schema import ActionCommand, TaskResult
from ..context import HandlerContext

logger = logging.getLogger(__name__)

YOUTUBE_SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"

def handle_watch_video(cmd: ActionCommand, ctx: HandlerContext) -> TaskResult:
    """
    Search for a video on YouTube and open the top result in the browser.
    """
    query = cmd.target
    if not query:
        return TaskResult(
            action="WATCH_VIDEO",
            success=False,
            error_code="MISSING_TARGET",
            message="No video search query provided."
        )

    api_key = ctx.settings.youtube_api_key
    if not api_key:
        return TaskResult(
            action="WATCH_VIDEO",
            success=False,
            error_code="MISSING_API_KEY",
            message="YouTube API key is not configured in .env (Youtube_Data_API_V3)."
        )

    try:
        # 1. Search YouTube
        params = {
            "part": "snippet",
            "q": query,
            "type": "video",
            "maxResults": 5,
            "key": api_key
        }
        
        with httpx.Client(timeout=10.0) as client:
            resp = client.get(YOUTUBE_SEARCH_URL, params=params)
            resp.raise_for_status()
            data = resp.json()
            
        items = data.get("items", [])
        if not items:
            return TaskResult(
                action="WATCH_VIDEO",
                success=False,
                error_code="NO_RESULTS",
                message=f"No YouTube results found for '{query}'."
            )

        # 2. Get top video
        top_video = items[0]
        video_id = top_video["id"]["videoId"]
        video_title = top_video["snippet"]["title"]
        video_url = f"https://www.youtube.com/watch?v={video_id}"
        
        # 3. Open in browser
        try:
            # Try to use Arc if it's the user's preferred browser
            # We fetch path from config/ctx if available
            # For now, let's just use startfile/webbrowser which is more robust for URLs
            if sys.platform == "win32":
                os.startfile(video_url)
            else:
                webbrowser.open(video_url)
                
            # 4. Prepare response message with recommendations
            recommendations = []
            for item in items[1:4]:
                recommendations.append(f"- {item['snippet']['title']}")
            
            rec_text = "\n".join(recommendations)
            message = (
                f"Alright, I've started playing '**{video_title}**' for you.\n\n"
                f"**Other recommendations:**\n{rec_text}"
            )
            
            return TaskResult(
                action="WATCH_VIDEO",
                success=True,
                message=message,
                artifacts={
                    "video_id": video_id,
                    "video_title": video_title,
                    "video_url": video_url,
                    "recommendations": [item["snippet"]["title"] for item in items[1:4]]
                }
            )
            
        except Exception as e:
            logger.exception("Failed to open browser for YouTube")
            return TaskResult(
                action="WATCH_VIDEO",
                success=False,
                error_code="BROWSER_ERROR",
                message=f"Found video but failed to open browser: {str(e)}"
            )

    except httpx.HTTPStatusError as e:
        logger.error(f"YouTube API error: {e.response.status_code} - {e.response.text}")
        return TaskResult(
            action="WATCH_VIDEO",
            success=False,
            error_code="API_ERROR",
            message=f"YouTube API returned an error: {e.response.status_code}"
        )
    except Exception as e:
        logger.exception("Unexpected error in YouTube handler")
        return TaskResult(
            action="WATCH_VIDEO",
            success=False,
            error_code="INTERNAL_ERROR",
            message=f"An unexpected error occurred: {str(e)}"
        )
