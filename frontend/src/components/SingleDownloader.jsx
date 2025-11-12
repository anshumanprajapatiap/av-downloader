

import React, { useState, useRef, useEffect } from "react";
import axios from "axios";
import Slider from "rc-slider";
import "rc-slider/assets/index.css";

const BACKEND_URL = import.meta.env.VITE_BACKEND_URL;

export default function SingleDownloader() {
  const [url, setUrl] = useState("");
  const [preview, setPreview] = useState(null);
  const [loading, setLoading] = useState(false);
  const [showDownloadModal, setShowDownloadModal] = useState(false);
  const [selectedVideo, setSelectedVideo] = useState("");
  const [selectedAudio, setSelectedAudio] = useState("");
  const [mode, setMode] = useState("merged");
  const [downloading, setDownloading] = useState(false);
  const [progress, setProgress] = useState(0);
  const [fetchType, setFetchType] = useState("single");
  const [startTime, setStartTime] = useState(0);
  const [endTime, setEndTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const videoRef = useRef(null);
  const [range, setRange] = useState([0, duration]);

  // Utility formatters
  const secondsToTime = (secs) => {
    const h = String(Math.floor(secs / 3600)).padStart(2, "0");
    const m = String(Math.floor((secs % 3600) / 60)).padStart(2, "0");
    const s = String(Math.floor(secs % 60)).padStart(2, "0");
    return `${h}:${m}:${s}`;
  };

  const fetchPreview = async () => {
    if (!url.trim()) return alert("Please paste a YouTube link first!");
    setLoading(true);
    setPreview(null);
    try {
      const res = await axios.get(`${BACKEND_URL}/preview`, { 
        params: { url, type: fetchType } ,
        headers: { 
          'Accept': 'application/json',
          'Content-Type': 'application/json',
          'ngrok-skip-browser-warning': '1'
        }
      });
      setPreview(res.data);
      if (res.data.duration) {
        setDuration(res.data.duration);
        setStartTime(0);
        setEndTime(res.data.duration);
        setRange([0, res.data.duration]);
      }
    } catch (err) {
      console.error(err);
      alert("❌ Failed to fetch preview. Check backend logs.");
    } finally {
      setLoading(false);
    }
  };

  const handleLoadedMetadata = () => {
    if (videoRef.current) {
      const dur = videoRef.current.duration;
      setDuration(dur);
      setStartTime(0);
      setEndTime(dur);
    }
  };

  const validateTimes = () => {
    if (startTime >= endTime) {
      alert("⚠️ End time must be greater than start time!");
      return false;
    }
    if (endTime > duration) {
      alert("⚠️ End time exceeds video duration!");
      return false;
    }
    return true;
  };

  const download = async () => {
    if (!mode) return alert("Please select a mode");
    if (!validateTimes()) return;

    setDownloading(true);
    setProgress(0);

    try {
      const response = await axios.post(
        `${BACKEND_URL}/download`,
        {
          type: preview.type,
          url,
          mode,
          video_id: selectedVideo,
          audio_id: selectedAudio,
          start_time: secondsToTime(startTime),
          end_time: secondsToTime(endTime),
        },
        {
        headers: { 
          'Accept': 'application/json',
          'Content-Type': 'application/json',
          'ngrok-skip-browser-warning': '1'
        },
        responseType: "blob",
        onDownloadProgress: (e) => e.total && setProgress(Math.round((e.loaded * 100) / e.total)),
        }
      );

      const blob = new Blob([response.data]);
      const downloadUrl = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = downloadUrl;
      a.download = `${preview.title || "video"}_${secondsToTime(startTime)}_to_${secondsToTime(endTime)}.mp4`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(downloadUrl);

      alert("✅ Download completed!");
      setShowDownloadModal(false);
    } catch (err) {
      console.error(err);
      alert("❌ Download failed. Check backend logs.");
    } finally {
      setDownloading(false);
      setProgress(0);
    }
  };

  // Keep video playback inside trim range
  useEffect(() => {
    const video = videoRef.current;
    if (!video) return;

    const handleTimeUpdate = () => {
      if (video.currentTime < startTime) video.currentTime = startTime;
      if (video.currentTime > endTime) video.pause();
    };

    video.addEventListener("timeupdate", handleTimeUpdate);
    return () => video.removeEventListener("timeupdate", handleTimeUpdate);
  }, [startTime, endTime]);

  return (
    <div className="p-4 rounded bg-blue-50 shadow-md max-w-4xl mx-auto">

      {/* URL Input */}
      <div className="flex gap-3 mb-4">
        <input
          className="flex-grow border p-2 rounded"
          placeholder="Paste YouTube Video link"
          value={url}
          onChange={(e) => setUrl(e.target.value)}
        />
        <button
          onClick={fetchPreview}
          disabled={loading}
          className={`px-4 py-2 rounded text-white ${
            loading ? "bg-gray-400" : "bg-blue-600 hover:bg-blue-700"
          }`}
        >
          {loading ? "⏳ Loading..." : "Preview"}
        </button>
      </div>

      {preview && (
        <div className="p-4 rounded shadow bg-blue-50">
          <div className="flex flex-col items-center">
            <video
              ref={videoRef}
              controls
              onLoadedMetadata={handleLoadedMetadata}
              className="w-full max-w-2xl rounded-lg"
              poster={preview.thumbnail}
              src={preview.combined_formats?.[0]?.url || preview.video_formats?.[0]?.url}
            ></video>

            <h2 className="text-lg font-semibold mt-3">{preview.title}</h2>

            <button
              onClick={() => setShowDownloadModal(true)}
              className="bg-blue-400 text-white px-4 py-2 rounded mt-4 hover:bg-blue-700"
            >
              Download Options 🎧📽️
            </button>
          </div>

          {showDownloadModal && (
            <div className="fixed inset-0 flex items-center justify-center bg-black/50 z-50">
              <div className="bg-white p-6 rounded-lg shadow-xl w-96">
                <h3 className="text-xl font-semibold mb-4 text-center">
                  Select Download Options
                </h3>

                {/* Mode Selector */}
                <div className="mb-4">
                  <label className="font-medium">Mode:</label>
                  <select
                    value={mode}
                    onChange={(e) => setMode(e.target.value)}
                    className="border p-2 rounded mt-2 w-full"
                  >
                    <option value="merged">🎬 Merged (Audio + Video)</option>
                    <option value="video">🎞️ Video Only</option>
                    <option value="audio">🎧 Audio Only</option>
                  </select>
                </div>

                {(mode === "video" || mode === "merged") && (
                  <div className="mb-3">
                    <label className="font-medium">Video Quality:</label>
                    <select
                      value={selectedVideo}
                      onChange={(e) => setSelectedVideo(e.target.value)}
                      className="border p-2 rounded mt-2 w-full"
                    >
                      <option value="">-- Select Video Format --</option>
                      {preview.video_formats.map((f) => (
                        <option key={f.format_id} value={f.format_id}>
                          {f.resolution || "?"}p ({f.ext})
                        </option>
                      ))}
                    </select>
                  </div>
                )}

                {(mode === "audio" || mode === "merged") && (
                  <div className="mb-3">
                    <label className="font-medium">Audio Quality:</label>
                    <select
                      value={selectedAudio}
                      onChange={(e) => setSelectedAudio(e.target.value)}
                      className="border p-2 rounded mt-2 w-full"
                    >
                      <option value="">-- Select Audio Format --</option>
                      {preview.audio_formats.map((f) => (
                        <option key={f.format_id} value={f.format_id}>
                          {f.ext} ({f.abr ? `${f.abr} kbps` : "unknown"})
                        </option>
                      ))}
                    </select>
                  </div>
                )}

                {/* Trimming Slider */}
                {duration > 0 && (
                  <div className="w-full mt-6 border-t pt-4">
                    <label className="block text-sm font-medium mb-3 text-center">
                      ✂️ Select Trim Range
                    </label>

                    <div className="flex justify-between items-center mb-2">
                      <div className="flex flex-col items-center">
                        <label className="text-xs text-gray-600">Start</label>
                        <input
                          type="text"
                          className="w-24 border text-center rounded p-1"
                          value={secondsToTime(range[0])}
                          onChange={(e) => {
                            const parts = e.target.value.split(":").map(Number);
                            const sec = parts.reduce((acc, val) => acc * 60 + val, 0);
                            if (!isNaN(sec) && sec >= 0 && sec < range[1])
                              setRange([sec, range[1]]);
                          }}
                        />
                      </div>

                      <div className="flex flex-col items-center">
                        <label className="text-xs text-gray-600">End</label>
                        <input
                          type="text"
                          className="w-24 border text-center rounded p-1"
                          value={secondsToTime(range[1])}
                          onChange={(e) => {
                            const parts = e.target.value.split(":").map(Number);
                            const sec = parts.reduce((acc, val) => acc * 60 + val, 0);
                            if (!isNaN(sec) && sec > range[0] && sec <= duration)
                              setRange([range[0], sec]);
                          }}
                        />
                      </div>
                    </div>

                    {/* Dual Range Slider using rc-slider */}
                    <div className="px-2 mt-3">
                      <Slider
                        range
                        min={0}
                        max={Math.floor(duration)}
                        value={range}
                        onChange={(val) => setRange(val)}
                        trackStyle={[{ backgroundColor: "#3b82f6", height: 6 }]}
                        handleStyle={[
                          {
                            borderColor: "#3b82f6",
                            backgroundColor: "#fff",
                            height: 16,
                            width: 16,
                            marginTop: -6,
                          },
                          {
                            borderColor: "#3b82f6",
                            backgroundColor: "#fff",
                            height: 16,
                            width: 16,
                            marginTop: -6,
                          },
                        ]}
                        railStyle={{ backgroundColor: "#e5e7eb", height: 6 }}
                      />
                    </div>
                   

                    <p className="text-center text-sm mt-2 text-gray-700">
                      Selected Range: <b>{secondsToTime(range[0])}</b> →{" "}
                      <b>{secondsToTime(range[1])}</b>
                    </p>
                  </div>
                )}



                {downloading && (
                  <div className="w-full bg-gray-200 rounded-full h-3 mt-4">
                    <div
                      className="bg-green-600 h-3 rounded-full transition-all"
                      style={{ width: `${progress}%` }}
                    ></div>
                    <p className="text-sm text-center mt-1">{progress}%</p>
                  </div>
                )}

                <div className="flex justify-between mt-5">
                  <button
                    onClick={() => setShowDownloadModal(false)}
                    className="px-4 py-2 bg-gray-300 rounded hover:bg-gray-400"
                  >
                    Cancel
                  </button>
                  <button
                    onClick={download}
                    disabled={downloading}
                    className={`px-4 py-2 rounded text-white ${
                      downloading
                        ? "bg-gray-400"
                        : "bg-blue-600 hover:bg-blue-700"
                    }`}
                  >
                    {downloading ? "Downloading..." : "Download"}
                  </button>
                </div>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
