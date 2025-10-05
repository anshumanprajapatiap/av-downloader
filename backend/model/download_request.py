from pydantic import BaseModel
from typing import Optional, List  


class DownloadRequest(BaseModel):
    url: str
    type: str  # "single" or "playlist"
    format_id: str | None = None
    audio_id: str | None = None
    video_id: str | None = None
    mode: str  # "video", "audio", "merged"
    download_path: str | None = None  # If None, use default path

    # 🕒 Optional trimming parameters
    start_time: Optional[str] = None  # e.g. "00:01:23" (1 min 23 sec)
    end_time: Optional[str] = None    # e.g. "00:02:45" (2 min 45 sec)



class PlaylistDownloadRequest(BaseModel):
    url: str
    video_ids: List[str]
    download_path: str | None = None
    mode: str = "playlist"
    playlist_title: str | None = None  # Optional title for naming the ZIP file