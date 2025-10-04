from pydantic import BaseModel

class DownloadRequest(BaseModel):
    url: str
    format_id: str | None = None
    audio_id: str | None = None
    video_id: str | None = None
    mode: str  # "video", "audio", "merged"