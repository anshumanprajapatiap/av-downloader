from fastapi import FastAPI, Query, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import yt_dlp
import os
import subprocess
import logging
from datetime import datetime
from model.download_request import DownloadRequest
import tempfile
from utils import sanitize_filename

# Ensure download directory exists
DOWNLOAD_DIR = "downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)



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

logger = logging.getLogger("downloader")




# 🎥 Preview available formats (for UI)
def preview_video(url: str):
    logger.info(f"🎬 [PREVIEW] Request received | URL: {url}")

    ydl_opts = {
        "quiet": True,
        "skip_download": True,
        "dump_single_json": True,
        "noplaylist": True,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)

        title = info.get("title")
        logger.info(f"✅ [PREVIEW] Metadata extracted | Title: {title}")

        video_formats, audio_formats, combined_formats = [], [], []

        for f in info.get("formats", []):
            vcodec = f.get("vcodec")
            acodec = f.get("acodec")
            ext = f.get("ext")

            # Combined video + audio
            if vcodec != "none" and acodec != "none":
                combined_formats.append({
                    "format_id": f.get("format_id"),
                    "ext": ext,
                    "resolution": f.get("resolution") or f"{f.get('height')}p",
                    "fps": f.get("fps"),
                    "filesize": f.get("filesize"),
                    "vcodec": vcodec,
                    "acodec": acodec,
                    "url": f.get("url"),
                })

            # Video-only formats
            elif vcodec != "none" and acodec == "none":
                video_formats.append({
                    "format_id": f.get("format_id"),
                    "ext": ext,
                    "resolution": f.get("resolution") or f"{f.get('height')}p",
                    "fps": f.get("fps"),
                    "filesize": f.get("filesize"),
                    "vcodec": vcodec,
                    "url": f.get("url"),
                })

            # Audio-only formats
            elif vcodec == "none" and acodec != "none":
                audio_formats.append({
                    "format_id": f.get("format_id"),
                    "ext": ext,
                    "abr": f.get("abr"),
                    "filesize": f.get("filesize"),
                    "acodec": acodec,
                    "url": f.get("url"),
                })

        logger.info(
            f"🎞️ [PREVIEW] Found {len(video_formats)} video-only, "
            f"{len(audio_formats)} audio-only, "
            f"{len(combined_formats)} combined formats"
        )

        return {
            "title": title,
            "thumbnail": info.get("thumbnail"),
            "duration": info.get("duration"),
            "video_formats": video_formats,
            "audio_formats": audio_formats,
            "combined_formats": combined_formats,
        }

    except Exception as e:
        logger.error(f"❌ [PREVIEW] Error processing {url} | {type(e).__name__}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch video info: {str(e)}")



# def download_video(req: DownloadRequest):
#     logger.info(f"🎬 Download request: {req.mode} | URL: {req.url}")

#     try:
#         if req.mode == "video":
#             ydl_opts = {
#                 "format": req.video_id or req.format_id,
#                 "outtmpl": f"{DOWNLOAD_DIR}/%(title)s.%(ext)s",
#             }

#         elif req.mode == "audio":
#             ydl_opts = {
#                 "format": req.audio_id or req.format_id,
#                 "outtmpl": f"{DOWNLOAD_DIR}/%(title)s.%(ext)s",
#                 "postprocessors": [
#                     {
#                         "key": "FFmpegExtractAudio",
#                         "preferredcodec": "mp3",
#                         "preferredquality": "192",
#                     }
#                 ],
#             }

#         elif req.mode == "merged":
#             if not (req.video_id and req.audio_id):
#                 raise HTTPException(status_code=400, detail="Missing video_id or audio_id")
#             ydl_opts = {
#                 "format": f"{req.video_id}+{req.audio_id}",
#                 "outtmpl": f"{DOWNLOAD_DIR}/%(title)s.%(ext)s",
#                 "merge_output_format": "mp4",
#             }

#         else:
#             raise HTTPException(status_code=400, detail="Invalid mode. Must be video, audio, or merged.")

#         with yt_dlp.YoutubeDL(ydl_opts) as ydl:
#             ydl.download([req.url])

#         logger.info(f"✅ Download complete: {req.url}")
#         return {"status": "success"}

#     except Exception as e:
#         logger.error(f"❌ Download failed for {req.url} — {type(e).__name__}: {e}")
#         raise HTTPException(status_code=500, detail=str(e))



def download_video(req: DownloadRequest):
    logger.info(f"🎬 Processing mode={req.mode} | URL={req.url}")

    tmp_dir = tempfile.mkdtemp()
    output_path = os.path.join(tmp_dir, "%(title)s.%(ext)s")

    try:
        # 🎯 Prepare yt-dlp options
        if req.mode == "video":
            ydl_opts = {
                "format": req.video_id or req.format_id or "bestvideo",
                "outtmpl": output_path,
                "restrictfilenames": True,
            }

        elif req.mode == "audio":
            ydl_opts = {
                "format": req.audio_id or req.format_id or "bestaudio/best",
                "outtmpl": output_path,
                "restrictfilenames": True,
                "postprocessors": [
                    {
                        "key": "FFmpegExtractAudio",
                        "preferredcodec": "mp3",
                        "preferredquality": "192",
                    }
                ],
                "keepvideo": False,  # 🧹 deletes .webm after conversion
            }

        elif req.mode == "merged":
            if not (req.video_id and req.audio_id):
                raise HTTPException(status_code=400, detail="Missing video_id or audio_id")

            ydl_opts = {
                "format": f"{req.video_id}+{req.audio_id}",
                "outtmpl": output_path,
                "restrictfilenames": True,
                "merge_output_format": "mp4",
            }

        else:
            raise HTTPException(status_code=400, detail="Invalid mode")

        # 🚀 Perform the download
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(req.url, download=True)
            raw_path = ydl.prepare_filename(info)

        # 🧠 Handle audio-only renamed file
        if req.mode == "audio":
            base, _ = os.path.splitext(raw_path)
            audio_path = base + ".mp3"
            final_path = audio_path if os.path.exists(audio_path) else raw_path
        else:
            final_path = raw_path

        if not os.path.exists(final_path):
            raise HTTPException(status_code=500, detail=f"File not found after download: {final_path}")

        logger.info(f"✅ File ready: {final_path}")

        # 🧩 Prepare stream
        def iterfile():
            with open(final_path, "rb") as f:
                while chunk := f.read(1024 * 1024):
                    yield chunk

        filename = os.path.basename(final_path)
        filesize = os.path.getsize(final_path)

        # 🧾 Response
        return StreamingResponse(
            iterfile(),
            media_type="audio/mpeg" if req.mode == "audio" else "video/mp4",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "Content-Length": str(filesize),
            },
        )

    except Exception as e:
        logger.error(f"❌ Download failed for {req.url}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

    finally:
        logger.info(f"🧹 Temp directory: {tmp_dir}")

