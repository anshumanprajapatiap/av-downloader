import React, { useState, useRef, useEffect } from "react";
import axios from "axios";

const BACKEND_URL = "http://localhost:8000";

export default function PlaylistDownloader() {
  const [url, setUrl] = useState("");
  const [playlistTitle, setPlaylistTitle] = useState("");
  const [playlist, setPlaylist] = useState([]);
  const [loading, setLoading] = useState(false);
  const [selectedVideos, setSelectedVideos] = useState([]);
  const [downloadPath, setDownloadPath] = useState("Downloads");
  const [downloadLogs, setDownloadLogs] = useState([]);
  const [isDownloading, setIsDownloading] = useState(false);
  const [progressMap, setProgressMap] = useState({});
  const logContainerRef = useRef(null);

  // 🧭 Fetch playlist metadata
  const fetchPlaylist = async () => {
    if (!url.trim()) return alert("Paste a valid YouTube playlist link!");
    setLoading(true);
    try {
      const res = await axios.get(`${BACKEND_URL}/preview`, {
        params: { url, type: "playlist" },
      });
      const videos = res.data.videos || [];
      setPlaylist(videos);
      setSelectedVideos(videos.map((v) => v.id)); // Select all
      setPlaylistTitle(res.data.playlist_title || "");
      if (videos.length === 0) alert("No videos found in playlist!");
    } catch (err) {
      console.error(err);
      alert("❌ Failed to fetch playlist!");
    } finally {
      setLoading(false);
    }
  };

  // ✅ Toggle video selection
  const toggleSelect = (id) => {
    setSelectedVideos((prev) =>
      prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]
    );
  };

  const selectAll = () => setSelectedVideos(playlist.map((v) => v.id));
  const deselectAll = () => setSelectedVideos([]);

  // 🚀 Stream-based Playlist Download
  const handleDownload = async () => {
    if (selectedVideos.length === 0)
      return alert("Select at least one video!");

    setIsDownloading(true);
    setDownloadLogs(["🚀 Starting playlist download..."]);

    try {
      const response = await fetch(`${BACKEND_URL}/downloadplaylist`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          url,
          download_path: downloadPath,
          mode: "playlist",
          video_ids: selectedVideos,
          playlist_title: playlistTitle,
        }),
      });

      if (!response.ok || !response.body) {
        setDownloadLogs((prev) => [...prev, "❌ Failed to start download"]);
        setIsDownloading(false);
        return;
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder("utf-8");
      let buffer = "";

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const parts = buffer.split("\n\n");
        buffer = parts.pop();

        for (const part of parts) {
          if (!part.startsWith("data:")) continue;

          try {
            const json = JSON.parse(part.replace("data: ", ""));
            let logEntry = "";

            switch (json.event) {
              case "status":
                logEntry = `ℹ️ ${json.message}`;
                break;

              case "progress": {
                logEntry = `⬇️ ${json.filename} | ${json.percent} @ ${json.speed} (ETA ${json.eta})`;
                const match = json.filename.match(/^(\d+)\s*-/);
                if (match) {
                  const index = parseInt(match[1]) - 1;
                  const video = playlist[index];
                  if (video?.id) {
                    setProgressMap((prev) => ({
                      ...prev,
                      [video.id]: json.percent,
                    }));
                  }
                }
                break;
              }

              case "video_finished":
                logEntry = `✅ Finished: ${json.filename}`;
                break;

              case "log":
                logEntry = `${json.message}`;
                break;

              case "completed":
                logEntry = `✅ ${json.message}`;
                // ✅ FIXED: use zip_url instead of zip_filename
                if (json.zip_url) {
                  const link = document.createElement("a");
                  link.href = `${BACKEND_URL}${json.zip_url}`;
                  link.setAttribute("download", "");
                  document.body.appendChild(link);
                  link.click();
                  document.body.removeChild(link);
                }
                setIsDownloading(false);
                break;

              case "error":
                logEntry = `❌ ${json.message}`;
                setIsDownloading(false);
                break;

              default:
                logEntry = JSON.stringify(json);
            }

            setDownloadLogs((prev) => [...prev, logEntry]);
          } catch (err) {
            console.error("SSE parse error:", err);
          }
        }
      }
    } catch (err) {
      console.error("Stream error:", err);
      setDownloadLogs((prev) => [...prev, "❌ Stream error occurred."]);
      setIsDownloading(false);
    }
  };


  // 🧹 Auto-scroll logs
  useEffect(() => {
    if (logContainerRef.current) {
      logContainerRef.current.scrollTop =
        logContainerRef.current.scrollHeight;
    }
  }, [downloadLogs]);

  const formatTime = (seconds) => {
    if (!seconds || isNaN(seconds)) return "00:00";
    const h = Math.floor(seconds / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    const s = Math.floor(seconds % 60);
    return [h, m, s]
      .map((v) => String(v).padStart(2, "0"))
      .filter((v, i) => v !== "00" || i > 0)
      .join(":");
  };

  const totalDuration = playlist.reduce(
    (acc, v) => acc + (v.duration || 0),
    0
  );

  return (
    <div className="p-4 rounded bg-blue-50 shadow-md max-w-4xl mx-auto">
      {/* URL Input */}
      <div className="flex gap-3 mb-4">
        <input
          className="flex-grow border p-2 rounded"
          placeholder="Paste YouTube playlist link"
          value={url}
          onChange={(e) => setUrl(e.target.value)}
        />
        <button
          onClick={fetchPlaylist}
          disabled={loading}
          className={`px-4 py-2 rounded text-white ${
            loading ? "bg-gray-400" : "bg-blue-600 hover:bg-blue-700"
          }`}
        >
          {loading ? "⏳ Loading..." : "Preview"}
        </button>
      </div>

      {/* Playlist Info */}
      {playlist.length > 0 && (
        <>
          <div className="flex justify-between items-center mb-4 border-b pb-2">
            <div>
              <h3 className="font-semibold text-lg text-gray-800">
                🎵 Playlist Details
              </h3>
              <p className="text-sm text-gray-600">
                Title: <b>{playlistTitle}</b>
              </p>
              <p className="text-sm text-gray-600">
                Total Videos: <b>{playlist.length}</b> | Duration:{" "}
                <b>{formatTime(totalDuration)}</b>
              </p>
            </div>
            <div className="flex items-center">
              <label
                htmlFor="folderInput"
                className="px-3 py-2 bg-gray-200 rounded cursor-pointer hover:bg-gray-300"
              >
                📂 Select Folder
              </label>
              <span className="ml-2 text-sm text-gray-700">
                Selected: <b>{downloadPath}</b>
              </span>
            </div>
          </div>

          {/* Video List */}
          <div className="flex flex-col gap-3 max-h-[70vh] overflow-y-auto">
            {playlist.map((video, idx) => (
              <div
                key={video.id || idx}
                className={`p-3 border rounded-lg flex gap-3 items-center ${
                  selectedVideos.includes(video.id)
                    ? "bg-blue-100 border-blue-500"
                    : "bg-white"
                }`}
              >
                <input
                  type="checkbox"
                  checked={selectedVideos.includes(video.id)}
                  onChange={() => toggleSelect(video.id)}
                  className="w-5 h-5"
                />
                <img
                  src={video.thumbnail}
                  alt={video.title}
                  className="w-28 h-18 object-cover rounded"
                />
                <div className="flex flex-col w-full">
                  <p className="font-medium text-gray-800">{video.title}</p>
                  <p className="text-xs text-gray-600">
                    Duration: {formatTime(video.duration)}
                  </p>
                  {progressMap[video.id] && (
                    <div className="flex items-center gap-2 mt-1">
                      <div className="w-32 bg-gray-200 rounded-full h-2 overflow-hidden">
                        <div
                          className="bg-blue-500 h-2 transition-all"
                          style={{ width: progressMap[video.id] }}
                        />
                      </div>
                      <span className="text-xs text-gray-700">
                        {progressMap[video.id]}
                      </span>
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>

          {/* Download Button */}
          <div className="flex justify-end mt-4">
            <button
              onClick={handleDownload}
              disabled={isDownloading}
              className={`px-4 py-2 rounded text-white ${
                isDownloading
                  ? "bg-gray-400 cursor-not-allowed"
                  : "bg-blue-600 hover:bg-blue-700"
              }`}
            >
              {isDownloading ? "⬇️ Downloading..." : "Download Selected 🎧"}
            </button>
          </div>
        </>
      )}

      {/* Logs */}
      {downloadLogs.length > 0 && (
        <div
          ref={logContainerRef}
          className="mt-4 bg-black text-green-400 p-3 rounded h-56 overflow-y-auto font-mono text-sm"
        >
          {downloadLogs.map((log, idx) => {
            const color = log.includes("⚠️")
              ? "text-yellow-400"
              : log.includes("❌")
              ? "text-red-400"
              : "text-green-400";
            return (
              <div key={idx} className={color}>
                {log}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
