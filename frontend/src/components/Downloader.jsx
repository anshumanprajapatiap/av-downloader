import React, { useState } from "react";
import SingleDownloader from "./SingleDownloader";
import PlaylistDownloader from "./PlaylistDownloader";

export default function Downloader() {
  const [fetchType, setFetchType] = useState("single");

  return (
    <div className="p-8 max-w-4xl mx-auto">
      <h2 className="text-2xl font-bold mb-6 text-center">🎧 YouTube Downloader</h2>

      {/* Type Selector */}
      <div className="flex justify-center gap-6 mb-6">
        <label className="flex items-center gap-2">
          <input
            type="radio"
            name="fetchType"
            value="single"
            checked={fetchType === "single"}
            onChange={(e) => setFetchType(e.target.value)}
          />
          <span>🎬 Single Video</span>
        </label>
        <label className="flex items-center gap-2">
          <input
            type="radio"
            name="fetchType"
            value="playlist"
            checked={fetchType === "playlist"}
            onChange={(e) => setFetchType(e.target.value)}
          />
          <span>📜 Playlist</span>
        </label>
      </div>

      {/* Conditional rendering */}
      {fetchType === "single" ? <SingleDownloader /> : <PlaylistDownloader />}
    </div>
  );
}
