import { useRef, useState, useEffect } from "react";
import Slider from "rc-slider";
import "rc-slider/assets/index.css";

export default function Trimmer() {
  const [file, setFile] = useState(null);
  const [url, setUrl] = useState(null);
  const [duration, setDuration] = useState(0);
  const [range, setRange] = useState([0, 30]); // seconds
  const [isPlaying, setIsPlaying] = useState(false);
  const [startText, setStartText] = useState("00:00");
  const [endText, setEndText] = useState("00:30");

  const mediaRef = useRef(null);

  // Create object URL for preview
  useEffect(() => {
    if (!file) {
      setUrl(null);
      setDuration(0);
      setRange([0, 30]);
      setStartText("00:00");
      setEndText("00:30");
      return;
    }
    const objectUrl = URL.createObjectURL(file);
    setUrl(objectUrl);
    return () => URL.revokeObjectURL(objectUrl);
  }, [file]);

  // Helper: parse "MM:SS" or "HH:MM:SS" -> seconds (int)
  const parseTimeToSeconds = (str) => {
    if (!str) return 0;
    const parts = str.trim().split(":").map((p) => Number(p));
    if (parts.some((n) => Number.isNaN(n))) return NaN;
    if (parts.length === 1) return Math.max(0, Math.floor(parts[0]));
    if (parts.length === 2) {
      const [m, s] = parts;
      return Math.max(0, m * 60 + s);
    }
    if (parts.length === 3) {
      const [h, m, s] = parts;
      return Math.max(0, h * 3600 + m * 60 + s);
    }
    return NaN;
  };

  // Helper: format seconds -> "MM:SS" or "HH:MM:SS" (if duration >= 3600)
  const formatSeconds = (secs) => {
    if (!Number.isFinite(secs) || secs < 0) secs = 0;
    const s = Math.floor(secs % 60);
    const m = Math.floor((secs / 60) % 60);
    const h = Math.floor(secs / 3600);
    const needHours = duration >= 3600 || h > 0;
    const hh = String(h).padStart(2, "0");
    const mm = String(m).padStart(2, "0");
    const ss = String(s).padStart(2, "0");
    return needHours ? `${hh}:${mm}:${ss}` : `${mm}:${ss}`;
  };

  // When metadata loads set duration and default range/texts
  const handleLoadedMetadata = () => {
    const dur = Math.floor(mediaRef.current?.duration || 0);
    setDuration(dur);
    // Keep a sensible default end
    const endDefault = Math.min(dur, 30);
    const newRange = [0, endDefault > 0 ? endDefault : dur];
    setRange(newRange);
    setStartText(formatSeconds(newRange[0]));
    setEndText(formatSeconds(newRange[1]));
  };

  // Time update: stop at range end
  const handleTimeUpdate = () => {
    if (!mediaRef.current) return;
    const current = mediaRef.current.currentTime;
    const [, end] = range;
    // If we've reached (or passed) the end of selection
    if (current >= end) {
      mediaRef.current.pause();
      // reset to start so next play begins from selection start
      mediaRef.current.currentTime = Math.max(0, range[0]);
      setIsPlaying(false);
    }
  };

  // Play/pause toggle: start from start of selection
  const togglePlay = () => {
    if (!mediaRef.current) return;
    const [start, end] = range;
    const wasPlaying = isPlaying;
    if (wasPlaying) {
      mediaRef.current.pause();
      setIsPlaying(false);
      return;
    }
    // If currentTime outside selection, seek to start
    const cur = mediaRef.current.currentTime;
    if (cur < start || cur >= end) {
      try {
        mediaRef.current.currentTime = start;
      } catch (err) {
        // some browsers may throw if not ready; ignore
      }
    }
    mediaRef.current.play().then(() => setIsPlaying(true)).catch(() => setIsPlaying(false));
  };

  // Slider change while dragging
  const handleRangeChange = (newRange) => {
    // update slider visuals and text while dragging
    setRange(newRange);
    setStartText(formatSeconds(newRange[0]));
    setEndText(formatSeconds(newRange[1]));
  };

  // After slider change (user finished sliding) -> apply to media position
  const handleRangeAfterChange = (newRange) => {
    setRange(newRange);
    setStartText(formatSeconds(newRange[0]));
    setEndText(formatSeconds(newRange[1]));

    if (!mediaRef.current) return;
    const wasPlaying = !mediaRef.current.paused && !mediaRef.current.ended;
    // Seek to new start and continue if was playing
    mediaRef.current.pause();
    try {
      mediaRef.current.currentTime = Math.max(0, newRange[0]);
    } catch (err) {
      // ignore seek errors
    }
    if (wasPlaying) {
      mediaRef.current.play().then(() => setIsPlaying(true)).catch(() => setIsPlaying(false));
    } else {
      setIsPlaying(false);
    }
  };

  // When text inputs lose focus, parse and apply to slider
  const applyStartText = () => {
    const secs = parseTimeToSeconds(startText);
    if (Number.isNaN(secs)) {
      setStartText(formatSeconds(range[0]));
      return;
    }
    const clamped = Math.min(Math.max(0, Math.floor(secs)), Math.max(0, duration));
    const [, end] = range;
    // Ensure start < end
    const newStart = Math.min(clamped, Math.max(0, end - 1));
    const newRange = [newStart, end];
    setRange(newRange);
    setStartText(formatSeconds(newStart));
    // Seek to start
    if (mediaRef.current) {
      const wasPlaying = !mediaRef.current.paused && !mediaRef.current.ended;
      mediaRef.current.pause();
      mediaRef.current.currentTime = newStart;
      if (wasPlaying) mediaRef.current.play().then(() => setIsPlaying(true)).catch(() => setIsPlaying(false));
      else setIsPlaying(false);
    }
  };

  const applyEndText = () => {
    const secs = parseTimeToSeconds(endText);
    if (Number.isNaN(secs)) {
      setEndText(formatSeconds(range[1]));
      return;
    }
    const clamped = Math.min(Math.max(0, Math.floor(secs)), Math.max(0, duration));
    const [start] = range;
    // Ensure end > start
    const newEnd = Math.max(clamped, start + 1);
    const newRange = [start, newEnd];
    setRange(newRange);
    setEndText(formatSeconds(newEnd));
    // If playing and currentTime beyond new end -> handleTimeUpdate will stop it
    if (mediaRef.current) {
      const wasPlaying = !mediaRef.current.paused && !mediaRef.current.ended;
      if (mediaRef.current.currentTime >= newEnd) {
        mediaRef.current.pause();
        mediaRef.current.currentTime = start;
        setIsPlaying(false);
      }
      if (wasPlaying && mediaRef.current.currentTime < newEnd) {
        // continue playing
        mediaRef.current.play().then(() => setIsPlaying(true)).catch(() => setIsPlaying(false));
      }
    }
  };

  // Trim placeholder (send file + range to backend later)
  const handleTrim = () => {
    alert(`Trim request: ${formatSeconds(range[0])} → ${formatSeconds(range[1])}\n(backend trimming not implemented here)`);
  };

  // Keep UI text inputs in sync when range changes externally
  useEffect(() => {
    setStartText(formatSeconds(range[0]));
    setEndText(formatSeconds(range[1]));
  }, [range[0], range[1]]);

  return (
    <div className="max-w-2xl mx-auto p-6 text-center bg-white rounded-lg shadow-md">
      <h2 className="text-2xl font-bold mb-4">✂️ Audio/Video Trimmer</h2>

      {/* File Picker */}
      <input
        type="file"
        accept="video/*,audio/*"
        onChange={(e) => setFile(e.target.files?.[0] || null)}
        className="border p-2 rounded w-full mb-4"
      />

      {/* Preview + Controls */}
      {url && (
        <div className="mb-6">
          {file.type.startsWith("video") ? (
            <video
              ref={mediaRef}
              controls
              src={url}
              className="w-full rounded-lg mb-3"
              onLoadedMetadata={handleLoadedMetadata}
              onTimeUpdate={handleTimeUpdate}
            />
          ) : (
            <audio
              ref={mediaRef}
              controls
              src={url}
              className="w-full mb-3"
              onLoadedMetadata={handleLoadedMetadata}
              onTimeUpdate={handleTimeUpdate}
            />
          )}

          {/* Slider */}
          <div className="px-4">
            <Slider
              range
              min={0}
              max={Math.max(1, Math.floor(duration))}
              value={range}
              onChange={handleRangeChange}
              onAfterChange={handleRangeAfterChange}
              trackStyle={[{ backgroundColor: "#2563eb" }]}
              handleStyle={[
                { borderColor: "#2563eb" },
                { borderColor: "#2563eb" },
              ]}
            />
            <div className="flex justify-between mt-2 text-gray-700">
              <span>Start: {formatSeconds(range[0])}</span>
              <span>End: {formatSeconds(range[1])}</span>
            </div>
          </div>

          {/* Manual time inputs (text) */}
          <div className="flex justify-center gap-6 mt-4">
            <div>
              <label className="font-medium block">Start (MM:SS or HH:MM:SS):</label>
              <input
                type="text"
                value={startText}
                onChange={(e) => setStartText(e.target.value)}
                onBlur={applyStartText}
                placeholder={duration >= 3600 ? "00:00:00" : "00:00"}
                className="border p-2 rounded ml-2 w-36 text-center"
              />
            </div>

            <div>
              <label className="font-medium block">End (MM:SS or HH:MM:SS):</label>
              <input
                type="text"
                value={endText}
                onChange={(e) => setEndText(e.target.value)}
                onBlur={applyEndText}
                placeholder={duration >= 3600 ? "00:00:00" : "00:00"}
                className="border p-2 rounded ml-2 w-36 text-center"
              />
            </div>
          </div>

          {/* Controls */}
          <div className="mt-6 flex justify-center gap-4">
            <button
              onClick={togglePlay}
              className="bg-green-600 text-white px-4 py-2 rounded hover:bg-green-700"
            >
              {isPlaying ? "⏸ Pause" : "▶️ Play Selection"}
            </button>

            <button
              onClick={() => {
                if (!mediaRef.current) return;
                mediaRef.current.pause();
                mediaRef.current.currentTime = range[0];
                setIsPlaying(false);
              }}
              className="bg-yellow-500 text-white px-4 py-2 rounded hover:bg-yellow-600"
            >
              ↺ Reset to Start
            </button>

            <button
              onClick={handleTrim}
              className="bg-blue-600 text-white px-4 py-2 rounded hover:bg-blue-700"
            >
              Trim File
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
