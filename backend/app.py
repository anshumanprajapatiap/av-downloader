from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import yt_dlp
import os
import subprocess
import logging
from datetime import datetime
from downloader import preview_video
from downloader import download_video
from model.download_request import DownloadRequest
from utils import sanitize_filename

# ────────────────────────────────────────────────
# 🚀 App Setup
# ────────────────────────────────────────────────
app = FastAPI(title="YouTube Downloader API")

# Enable CORS for frontend connection
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)



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



# ────────────────────────────────────────────────
# 🧠 Routes
# ────────────────────────────────────────────────
@app.get("/")
def root():
    logger.info("Root endpoint hit.")
    return {"message": "YouTube Downloader API is running 🚀"}


# 🎥 Preview available formats (for UI)
@app.get("/preview")
def yt_preview_video(url: str):
    try:
        result = preview_video(url)
        return result
    except Exception as e:
        logger.error(f"❌ [PREVIEW] Error processing {url} | {type(e).__name__}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch video info: {str(e)}")


@app.post("/download")
def yt_download_video(req: DownloadRequest):
    try:
        return download_video(req)
    except Exception as e:
        logger.error(f"❌ Download failed for {req.url} — {type(e).__name__}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
