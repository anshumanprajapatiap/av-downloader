from fastapi import FastAPI, Query, HTTPException
from fastapi.responses import StreamingResponse, FileResponse
import uuid
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import yt_dlp
import os
import subprocess
import logging
from datetime import datetime
from model.download_request import DownloadRequest, PlaylistDownloadRequest
import tempfile
from utils import sanitize_filename
from typing import Generator
import json
import threading, queue
from utils import sanitize_filename, sanitize_playlist_filename
import requests
import concurrent.futures
import shutil



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

logger = logging.getLogger(__name__)



# Base download directory (e.g., /app/downloads inside container)
BASE_DOWNLOAD_DIR = os.path.join(os.getcwd(), "downloads")
os.makedirs(BASE_DOWNLOAD_DIR, exist_ok=True)


def get_download_path(path: str = None) -> str:
    """
    Resolve and return a safe, absolute download path.
    Defaults to BASE_DOWNLOAD_DIR if not specified or invalid.
    """
    if not path or path == "Downloads":
        return BASE_DOWNLOAD_DIR
    if not os.path.isabs(path):
        return os.path.join(BASE_DOWNLOAD_DIR, path)
    return os.path.abspath(path)


def stream_youtube_video(url: str, format_id: str = None):
    """
    Use yt-dlp to get a direct media URL and stream it to client without saving to disk.
    """
    logger.info(f"🎬 [STREAM INIT] Request received | URL: {url} | format_id: {format_id}")

    ydl_opts = {
        "quiet": True,
        "skip_download": True,
        "noplaylist": True,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)

        title = info.get("title", "Unknown Title")
        total_formats = len(info.get("formats", []))
        logger.info(f"📄 [STREAM INFO] Extracted metadata | Title: '{title}' | Formats: {total_formats}")

        fmt = None
        if format_id:
            fmt = next((f for f in info["formats"] if f.get("format_id") == format_id), None)
            if fmt:
                logger.info(f"🎯 [FORMAT SELECTED] Found format_id: {format_id} | "
                            f"Resolution: {fmt.get('height')}p | Codec: {fmt.get('vcodec')}/{fmt.get('acodec')}")
            else:
                logger.warning(f"⚠️ [FORMAT MISSING] Requested format_id '{format_id}' not found — falling back to best available format.")
        else:
            logger.info("ℹ️ [FORMAT SELECTED] No format_id provided — using best available format.")

        if not fmt:
            fmt = info["formats"][-1]  # fallback
            logger.info(f"🎬 [FORMAT FALLBACK] Using format_id: {fmt.get('format_id')} | "
                        f"Resolution: {fmt.get('height')}p | Codec: {fmt.get('vcodec')}/{fmt.get('acodec')}")

        stream_url = fmt["url"]
        mime_type = fmt.get("ext", "mp4")
        sanitized_title = sanitize_filename(title)

        logger.info(f"✅ [STREAM READY] {sanitized_title}.{mime_type} | Direct stream URL prepared")

        return stream_url, mime_type, sanitized_title

    except Exception as e:
        logger.exception(f"❌ [STREAM ERROR] Failed to prepare stream for URL: {url} | {type(e).__name__}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to prepare stream: {str(e)}")



def preview_playlist(url: str):
    logger.info(f"📋 [PLAYLIST PREVIEW] Request received | URL: {url}")

    ydl_opts = {
        "quiet": True,
        "skip_download": True,
        "dump_single_json": True,
        "extract_flat": True,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)

        if "entries" not in info:
            raise HTTPException(status_code=400, detail="URL is not a playlist")

        playlist_title = info.get("title")
        entries = info.get("entries", [])

        videos = []
        for i, entry in enumerate(entries):
            thumbnails = entry.get("thumbnails", [])
            
            # Pick a safe thumbnail index
            thumb_url = None
            if thumbnails:
                if len(thumbnails) > i + 1:
                    thumb_url = thumbnails[i + 1]["url"]
                else:
                    thumb_url = thumbnails[-1]["url"]  # fallback to last available thumbnail

            entry["thumbnail"] = thumb_url

            videos.append({
                "id": entry.get("id"),
                "title": entry.get("title"),
                "url": entry.get("url"),
                "duration": entry.get("duration"),
                "webpage_url": entry.get("webpage_url"),
                "thumbnail": entry.get("thumbnail"),
            })

        logger.info(f"✅ [PLAYLIST PREVIEW] Found {len(videos)} videos in playlist '{playlist_title}'")

        return {
            "type": "playlist",
            "playlist_title": playlist_title,
            "thumbnail": info.get("thumbnails")[0]["url"] if info.get("thumbnails") else None,
            "videos": videos,
        }

    except Exception as e:
        logger.error(f"❌ [PLAYLIST PREVIEW] Error processing {url} | {type(e).__name__}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch playlist info: {str(e)}")


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
            "type": "single",
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
#     logger.info(f"🎬 Streaming directly | mode={req.mode} | url={req.url}")

#     try:
#         # Step 1️⃣ — Get streamable media URL
#         stream_url, mime_type, title = stream_youtube_video(
#             req.url,
#             req.video_id or req.format_id
#         )
#         logger.info(f"🔗 Direct stream URL resolved | {stream_url[:80]}...")

#         # Step 2️⃣ — Prepare stream headers (mimic browser)
#         headers = {
#             "User-Agent": (
#                 "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
#                 "AppleWebKit/537.36 (KHTML, like Gecko) "
#                 "Chrome/115.0.0.0 Safari/537.36"
#             ),
#             "Accept-Encoding": "identity;q=1, *;q=0",
#             "Connection": "keep-alive",
#             "Range": "bytes=0-",
#         }

#         # Step 3️⃣ — Stream content
#         def iter_content():
#             logger.info("📡 [STREAMING] Starting content transfer...")
#             with requests.get(stream_url, headers=headers, stream=True, timeout=30) as r:
#                 r.raise_for_status()
#                 for chunk in r.iter_content(chunk_size=1024 * 1024):
#                     if chunk:
#                         yield chunk
#             logger.info("✅ [STREAMING] Completed sending stream to client.")

#         ext = "mp3" if req.mode == "audio" else "mp4"
#         filename = f"{title}.{ext}"
#         content_type = "audio/mpeg" if req.mode == "audio" else "video/mp4"

#         return StreamingResponse(
#             iter_content(),
#             media_type=content_type,
#             headers={
#                 "Content-Disposition": f'attachment; filename="{filename}"'
#             },
#         )

#     except Exception as e:
#         logger.exception(f"❌ Streaming failed for {req.url}: {e}")
#         raise HTTPException(status_code=500, detail=str(e))




def download_video(req: DownloadRequest):
    return download_video_save_to_server_then_stream_to_client(req)


def download_video_save_to_server_then_stream_to_client(req: DownloadRequest):
    logger.info(f"🎬 Downloading video | mode={req.mode} | url={req.url}")

    try:
        # ✅ Step 1️⃣ Resolve download and temp directories
        download_dir = get_download_path(req.download_path)
        os.makedirs(download_dir, exist_ok=True)
        tmp_dir = tempfile.mkdtemp(dir=download_dir)  # ✅ temp folder INSIDE downloads
        output_path = os.path.join(tmp_dir, "%(title)s.%(ext)s")

        # ✅ Step 2️⃣ Prepare yt-dlp options based on mode
        if req.mode == "video":
            ydl_opts = {
                "format": req.video_id or req.format_id or "bestvideo+bestaudio/best",
                "outtmpl": output_path,
                "restrictfilenames": True,
                "merge_output_format": "mp4",
                "noplaylist": True,
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
                "keepvideo": False,
                "noplaylist": True,
            }

        elif req.mode == "merged":
            if not (req.video_id and req.audio_id):
                raise HTTPException(status_code=400, detail="Missing video_id or audio_id")

            ydl_opts = {
                "format": f"{req.video_id}+{req.audio_id}",
                "outtmpl": output_path,
                "restrictfilenames": True,
                "merge_output_format": "mp4",
                "noplaylist": True,
            }

        else:
            raise HTTPException(status_code=400, detail="Invalid mode")

        logger.info(f"🔧 yt-dlp options: {ydl_opts}")

        # ✅ Step 3️⃣ Download file
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(req.url, download=True)
            raw_path = ydl.prepare_filename(info)

        # ✅ Step 4️⃣ Handle renamed audio
        if req.mode == "audio":
            base, _ = os.path.splitext(raw_path)
            audio_path = base + ".mp3"
            final_path = audio_path if os.path.exists(audio_path) else raw_path
        else:
            final_path = raw_path

        if not os.path.exists(final_path):
            raise HTTPException(status_code=500, detail=f"File not found: {final_path}")

        # ✅ Step 5️⃣ Trim only if needed
        if (req.start_time and req.start_time != "00:00:00") or req.end_time:
            logger.info(f"✂️ Trimming from {req.start_time} to {req.end_time}")
            trimmed_path = os.path.join(tmp_dir, f"trimmed_{os.path.basename(final_path)}")

            start_arg = ["-ss", req.start_time] if req.start_time else []
            end_arg = ["-to", req.end_time] if req.end_time else []

            cmd = [
                "ffmpeg",
                *start_arg,
                *end_arg,
                "-i", final_path,
                "-c", "copy",
                "-avoid_negative_ts", "1",
                trimmed_path,
                "-y"
            ]

            subprocess.run(cmd, check=True)
            final_path = trimmed_path
            logger.info(f"✅ Trimmed segment ready: {final_path}")
        else:
            logger.info("📽️ Full video/audio selected — no trimming applied.")

        # ✅ Step 6️⃣ Stream final file to client
        def iterfile():
            with open(final_path, "rb") as f:
                while chunk := f.read(1024 * 1024):
                    yield chunk

        filename = os.path.basename(final_path)
        filesize = os.path.getsize(final_path)

        logger.info(f"✅ Download ready to stream: {filename} ({filesize} bytes)")

        return StreamingResponse(
            iterfile(),
            media_type="audio/mpeg" if req.mode == "audio" else "video/mp4",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "Content-Length": str(filesize),
            },
        )

    except Exception as e:
        logger.exception(f"❌ Download failed for {req.url}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

    finally:
        logger.info(f"🧹 Temp directory used: {tmp_dir}")



def download_playlist(req: PlaylistDownloadRequest):
    """
    Downloads multiple videos in parallel with per-video progress updates via SSE.
    """
    playlist_title = req.playlist_title or "playlist"
    zip_base = sanitize_filename(playlist_title)
    if not zip_base.endswith(".zip"):
        zip_base += ".zip"

    download_dir = get_download_path(req.download_path)
    os.makedirs(download_dir, exist_ok=True)

    tmp_dir = tempfile.mkdtemp(dir=download_dir)
    logger.info(f"📂 Using temp dir: {tmp_dir}")

    q = queue.Queue()

    def emit(event_type: str, **kwargs):
        """Push structured JSON events into the SSE queue."""
        q.put(json.dumps({"event": event_type, **kwargs}))

    def download_single_video(video_url, index):
        """
        Downloads a single video while emitting progress events.
        """
        try:
            video_name = f"video_{index+1}"
            emit("status", message=f"🎬 Starting download for video #{index + 1}")

            def progress_hook(d):
                if d["status"] == "downloading":
                    emit(
                        "progress",
                        video_index=index,
                        filename=os.path.basename(d.get("filename", "")),
                        percent=d.get("_percent_str", "").strip(),
                        speed=d.get("_speed_str", "").strip(),
                        eta=d.get("_eta_str", "").strip(),
                    )
                elif d["status"] == "finished":
                    emit(
                        "video_finished",
                        video_index=index,
                        filename=os.path.basename(d.get("filename", "")),
                        message="✅ Finished downloading this video.",
                    )

            class QueueLogger:
                def debug(self, msg):
                    msg = msg.strip()
                    if any(k in msg for k in ["[download]", "[Merger]", "[ExtractAudio]"]):
                        emit("log", level="info", message=f"[{video_name}] {msg}")

                def warning(self, msg):
                    emit("log", level="warning", message=f"[{video_name}] ⚠️ {msg.strip()}")

                def error(self, msg):
                    emit("log", level="error", message=f"[{video_name}] ❌ {msg.strip()}")

            ydl_opts = {
                "outtmpl": os.path.join(tmp_dir, f"{index+1} - %(title)s.%(ext)s"),
                "format": "bestvideo+bestaudio/best",
                "merge_output_format": "mp4",
                "progress_hooks": [progress_hook],
                "logger": QueueLogger(),
                "noplaylist": True,
                "quiet": True,
                "ignoreerrors": True,
            }

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([video_url])

            return True

        except Exception as e:
            emit("error", message=f"❌ Video #{index + 1} failed: {str(e)}")
            return False

    def run_downloader():
        try:
            total = len(req.video_ids)
            emit("status", message=f"🚀 Starting playlist download ({total} videos)...")

            # 🧵 Parallel download
            with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
                futures = [
                    executor.submit(
                        download_single_video,
                        f"https://www.youtube.com/watch?v={vid_id}",
                        idx,
                    )
                    for idx, vid_id in enumerate(req.video_ids)
                ]

                completed = 0
                for future in concurrent.futures.as_completed(futures):
                    _ = future.result()
                    completed += 1
                    emit("status", message=f"✅ {completed}/{total} videos completed")

            # 📦 Create ZIP archive
            emit("status", message="📦 Creating ZIP archive...")
            zip_path = os.path.join(download_dir, zip_base)
            shutil.make_archive(zip_path[:-4], "zip", tmp_dir)

            emit(
                "completed",
                message="✅ Playlist download finished!",
                zip_url=f"/download/{zip_base}",
            )

        except Exception as e:
            logger.exception("Playlist download failed")
            emit("error", message=f"❌ {e}")
        finally:
            q.put("__done__")

    # 🔄 Start background thread
    threading.Thread(target=run_downloader, daemon=True).start()

    def event_stream():
        """Stream JSON messages to client via SSE."""
        while True:
            msg = q.get()
            if msg == "__done__":
                break
            yield f"data: {msg}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")