from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, FileResponse
from pydantic import BaseModel
import yt_dlp
import os
import subprocess
import logging
from datetime import datetime
from downloader import get_download_path
from downloader import preview_video, preview_playlist
from downloader import download_video, download_playlist
from model.download_request import DownloadRequest, PlaylistDownloadRequest
from utils import sanitize_filename, sanitize_playlist_filename
import shutil
import logging
import time
import threading

# ────────────────────────────────────────────────
# 🚀 App Setup
# ────────────────────────────────────────────────
app = FastAPI(title="YouTube Downloader API")



# ────────────────────────────────────────────────
# 🧾 Logging Configuration
# ────────────────────────────────────────────────
LOG_DIR = "logs"
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, f"app_{datetime.now().strftime('%Y%m%d')}.log")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] — %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()  # prints to console too
    ],
)

logger = logging.getLogger("Utility")




# Base download directory (e.g., /app/downloads inside container)
BASE_DOWNLOAD_DIR = os.path.join(os.getcwd(), "downloads")
os.makedirs(BASE_DOWNLOAD_DIR, exist_ok=True)



def cleanup_temp_dirs(base_dir: str = BASE_DOWNLOAD_DIR, max_age_minutes: int = 2):
    """
    Periodically removes old temp directories under download folder.
    Keeps only active or recent ones.
    """
    logger.info(f"🧹 Starting temp folder cleanup task...")

    while True:
        try:
            now = time.time()
            deleted_count = 0

            for root, dirs, _ in os.walk(base_dir):
                for d in dirs:
                    dir_path = os.path.join(root, d)
                    # Only target temp directories created via tempfile
                    if not os.path.basename(dir_path).startswith("tmp"):
                        continue

                    age_minutes = (now - os.path.getmtime(dir_path)) / 60
                    if age_minutes > max_age_minutes:
                        try:
                            shutil.rmtree(dir_path)
                            deleted_count += 1
                        except Exception as e:
                            logger.warning(f"⚠️ Failed to remove {dir_path}: {e}")

            if deleted_count > 0:
                logger.info(f"🧹 Removed {deleted_count} old temp dirs (> {max_age_minutes} mins old)")

        except Exception as e:
            logger.error(f"❌ Cleanup task error: {e}")

        # Sleep before next cleanup cycle
        time.sleep(600)  # every 10 minutes




cleanup_thread = threading.Thread(target=cleanup_temp_dirs, daemon=True)
cleanup_thread.start()
logger.info("🧼 Background cleanup thread started successfully.")

# Enable CORS for frontend connection
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)





# ────────────────────────────────────────────────
# 🧠 Routes
# ────────────────────────────────────────────────
@app.get("/")
def root():
    logger.info("Root endpoint hit.")
    return {"message": "YouTube Downloader API is running 🚀"}


# 🎥 Preview available formats (for UI)
@app.get("/preview")
def yt_preview_video(url: str, type: str = "single"):
    logger.info(f"Preview request for URL: {url} as type: {type}")
    if type == "playlist":
        return preview_playlist(url)
    else:
        return preview_video(url)

@app.post("/download")
def yt_download_video(req: DownloadRequest):
    logger.info(f"Download request: {req}")
    try:
        return download_video(req)
    except Exception as e:
        logger.error(f"❌ Download failed for {req.url} — {type(e).__name__}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# @app.get("/downloadplaylist")
# def yt_download_playlist(req: PlaylistDownloadRequest):
#     logger.info(f"🎧 Playlist download request received: {req.url} | {len(req.video_ids)} videos")
#     try:
#         return download_playlist(req)
#     except Exception as e:
#         logger.error(f"❌ Download failed for {req.url} — {type(e).__name__}: {e}")
#         raise HTTPException(status_code=500, detail=str(e))



# ✅ Updated API endpoint using your request model
@app.post("/downloadplaylist")
async def yt_download_playlist(req: PlaylistDownloadRequest):
    """
    POST endpoint for streaming playlist downloads via SSE.
    """
    logger.info(f"🎧 Received playlist download: {req.url} ({len(req.video_ids)} videos)")

    return download_playlist(req)


# 📦 Serve ZIP file
@app.get("/download/{filename}")
async def download_file(filename: str):
    """
    Serve a downloaded ZIP file to the client.
    """
    file_path = os.path.join(get_download_path(), filename)

    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail=f"File not found: {filename}")

    logger.info(f"📤 Serving file: {file_path}")

    return FileResponse(
        file_path,
        media_type="application/zip",
        filename=filename
    )






