# ---------- Add at top of file if not already imported ----------
import time
from typing import Optional, Tuple
from requests.exceptions import HTTPError, RequestException
# ---------------------------------------------------------------



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



def _extract_playable_format_info(url: str, format_id: Optional[str] = None, cookies: Optional[str] = None, ydl_opts_extra: dict = None) -> dict:
    """
    Use yt_dlp to extract info and pick a playable format dict.
    Returns a format dict (contains 'url', 'ext', 'format_id', etc).
    Raises RuntimeError on failure.
    """
    opts = {
        "quiet": True,
        "skip_download": True,
        "noplaylist": True,
        # keep full metadata so we can pick formats
        "forcejson": True,
    }
    if ydl_opts_extra:
        opts.update(ydl_opts_extra)
    if cookies:
        opts["cookiefile"] = cookies

    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=False)

    formats = info.get("formats", []) or []
    if not formats:
        raise RuntimeError("No formats found by yt-dlp")

    # If a specific format_id requested, try to find exact match first
    if format_id:
        for f in formats:
            if str(f.get("format_id")) == str(format_id) or str(f.get("itag")) == str(format_id):
                if f.get("url"):
                    return f
        # fallback if requested not found - we continue to choose best available

    # Prefer combined (video+audio) formats with direct 'url'
    # Otherwise prefer highest resolution video-only with a direct url
    # iterate formats in descending 'quality' order: yt-dlp usually orders by quality,
    # so try reversed list to find a good candidate with url
    for f in reversed(formats):
        if f.get("url") and f.get("ext"):
            # filter out formats where the url looks like a manifest (optional)
            # but usually yt-dlp provides direct googlevideo links in 'url'
            return f

    # If nothing returned:
    raise RuntimeError("Unable to select a playable format")


def stream_youtube_video(url: str, format_id: str = None, cookies: Optional[str] = None, max_retries: int = 3, user_agent: Optional[str] = None, chunk_size: int = 1024*1024):
    """
    Streams a YouTube video by repeatedly extracting a fresh signed URL using yt-dlp,
    then opening a streaming request to that URL. On 403 (or transient errors) it will
    re-extract and retry up to `max_retries`.
    Returns (StreamingResponse generator, mime_ext, sanitized_title) when called from download_video.
    """
    logger.info(f"🎬 [STREAM INIT] Request received | URL: {url} | format_id: {format_id}")

    # common http headers
    base_headers = {
        "Accept-Encoding": "identity;q=1, *;q=0",  # avoid compressed responses for streaming
        "Connection": "keep-alive",
    }
    if user_agent:
        base_headers["User-Agent"] = user_agent
    else:
        base_headers["User-Agent"] = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/115.0.0.0 Safari/537.36"
        )

    # We'll try several times: re-extract a fresh URL each attempt
    attempt = 0
    last_exc = None

    # We also extract some metadata once so we can name the file
    try:
        with yt_dlp.YoutubeDL({"quiet": True, "skip_download": True, "noplaylist": True}) as ydl:
            info = ydl.extract_info(url, download=False)
        title = info.get("title", "video")
    except Exception as e:
        logger.exception(f"❌ [STREAM ERROR] metadata extraction failed: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to extract metadata: {e}")

    sanitized_title = sanitize_filename(title)

    def generator():
        nonlocal attempt, last_exc
        while attempt < max_retries:
            attempt += 1
            try:
                fmt = _extract_playable_format_info(url, format_id=format_id, cookies=cookies)
                stream_url = fmt.get("url")
                ext = fmt.get("ext", "mp4")
                logger.info(f"🔗 [PLAYBACK URL] attempt={attempt} | chosen format_id={fmt.get('format_id')} | ext={ext} | url_preview={ (stream_url[:120] + '...') if stream_url else 'NONE' }")

                # Stream with requests
                headers = base_headers.copy()

                # Some formats provide http_headers inside format dict; merge them if present
                fmt_http_headers = fmt.get("http_headers") or fmt.get("headers")
                if isinstance(fmt_http_headers, dict):
                    headers.update(fmt_http_headers)

                # Use stream=True and iterate
                with requests.get(stream_url, headers=headers, stream=True, timeout=20) as r:
                    try:
                        r.raise_for_status()
                    except HTTPError as he:
                        status = getattr(he.response, "status_code", None)
                        logger.warning(f"[HTTP] status={status} on attempt {attempt} for stream_url")
                        # if 403 -> try re-extract (maybe signature expired)
                        if status == 403:
                            last_exc = he
                            # tiny backoff and retry
                            time.sleep(0.5 * attempt)
                            continue
                        # other 4xx/5xx -> raise out (non-recoverable)
                        raise

                    for chunk in r.iter_content(chunk_size=chunk_size):
                        if chunk:
                            yield chunk

                    # If we finished streaming without exception - done.
                    logger.info("✅ [STREAM] completed successfully")
                    return

            except HTTPError as he:
                last_exc = he
                logger.warning(f"[STREAM] HTTPError on attempt {attempt}: {he}")
                time.sleep(0.5 * attempt)
                continue
            except RequestException as rexc:
                last_exc = rexc
                logger.warning(f"[STREAM] RequestException on attempt {attempt}: {rexc}")
                time.sleep(0.5 * attempt)
                continue
            except Exception as exc:
                last_exc = exc
                logger.exception(f"[STREAM] Unexpected error on attempt {attempt}: {exc}")
                time.sleep(0.5 * attempt)
                continue

        logger.error("❌ [STREAM] exhausted retries, failing")
        # Raise so FastAPI returns 500
        raise RuntimeError("Failed to stream after retries") from last_exc

    # we return the generator and metadata (mime ext, sanitized title)
    # the caller uses generator() inside StreamingResponse
    # Note: ext is taken from last extracted format only when generator runs successfully,
    # so caller should assume mp4 unless generator provides otherwise.
    return generator, sanitized_title


def download_video(req: DownloadRequest):
    """
    streaming path (no save-to-disk). Uses stream_youtube_video generator and returns StreamingResponse.
    """
    logger.info(f"🎬 Streaming directly | mode={req.mode} | url={req.url}")

    try:
        # Prepare cookies path if provided in request object (optional)
        cookies = getattr(req, "cookies", None)

        # get generator factory and title (generator is created but will do extraction on first iteration)
        generator_factory, title = stream_youtube_video(req.url, format_id=(req.video_id or req.format_id), cookies=cookies,
                                                       max_retries=5,
                                                       user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36")

        # streaming generator instance
        def iter_content():
            yield from generator_factory()

        ext = "mp3" if req.mode == "audio" else "mp4"
        filename = f"{title}.{ext}"
        content_type = "audio/mpeg" if req.mode == "audio" else "video/mp4"

        logger.info(f"📡 [STREAM PREP] filename={filename} content_type={content_type}")

        return StreamingResponse(
            iter_content(),
            media_type=content_type,
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    except Exception as e:
        logger.exception(f"❌ Streaming failed for {req.url}: {e}")
        raise HTTPException(status_code=500, detail=str(e))



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




# def download_video(req: DownloadRequest):
#     return download_video_save_to_server_then_stream_to_client(req)


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
                "retries": 10,
                "fragment_retries": 10,
                "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36",
                "http_headers": {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
                    "Accept-Language": "en-US,en;q=0.5",
                    "DNT": "1",
                },
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
                "retries": 10,
                "fragment_retries": 10,
                "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36",
                "http_headers": {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
                    "Accept-Language": "en-US,en;q=0.5",
                    "DNT": "1",
                },
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
                "retries": 10,  # Retry up to 10 times
                "fragment_retries": 10,  # Retry fragments up to 10 times
                "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36",
                "http_headers": {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
                    "Accept-Language": "en-US,en;q=0.5",
                    "DNT": "1",
                },
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