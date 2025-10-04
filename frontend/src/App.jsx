import React, { useState } from "react";
import Home from "./pages/Home";
import Downloader from "./components/Downloader";
import Trimmer from "./components/Trimmer";


// export default function App() {
//   const [url, setUrl] = useState("");
//   const [preview, setPreview] = useState(null);
//   const [loading, setLoading] = useState(false);
//   const [showDownloadModal, setShowDownloadModal] = useState(false);
//   const [selectedVideo, setSelectedVideo] = useState("");
//   const [selectedAudio, setSelectedAudio] = useState("");
//   const [mode, setMode] = useState("merged");
//   const [downloading, setDownloading] = useState(false);
//   const [progress, setProgress] = useState(0);

//   const fetchPreview = async () => {
//     if (!url.trim()) return alert("Please paste a YouTube link first!");
//     setLoading(true);
//     setPreview(null);
//     try {
//       const res = await axios.get("http://localhost:8000/preview", { params: { url } });
//       setPreview(res.data);
//     } catch (err) {
//       console.error(err);
//       alert("❌ Failed to fetch preview. Check backend logs.");
//     } finally {
//       setLoading(false);
//     }
//   };

//   const download = async () => {
//     if (!mode) return alert("Please select a mode");
//     setDownloading(true);
//     setProgress(0);
//     try {
//       const response = await axios.post(
//         "http://localhost:8000/download",
//         {
//           url,
//           mode,
//           video_id: selectedVideo,
//           audio_id: selectedAudio,
//         },
//         {
//           responseType: "blob",
//           onDownloadProgress: (event) => {
//             if (event.total) {
//               const percent = Math.round((event.loaded * 100) / event.total);
//               setProgress(percent);
//             }
//           },
//         }
//       );

//       const blob = new Blob([response.data]);
//       const downloadUrl = window.URL.createObjectURL(blob);
//       const a = document.createElement("a");
//       a.href = downloadUrl;
//       a.download = `${preview.title || "video"}.mp4`;
//       document.body.appendChild(a);
//       a.click();
//       a.remove();
//       window.URL.revokeObjectURL(downloadUrl);

//       alert("✅ Download completed!");
//       setShowDownloadModal(false);
//     } catch (err) {
//       console.error(err);
//       alert("❌ Download failed. Check backend logs.");
//     } finally {
//       setDownloading(false);
//       setProgress(0);
//     }
//   };

//   const extractVideoId = (url) => {
//     const match = url.match(/(?:youtu\.be\/|youtube\.com\/(?:watch\?v=|embed\/|shorts\/))([^&?/]+)/);
//     return match ? match[1] : "";
//   };

//   return (
//     <div className="p-8 max-w-3xl mx-auto">
//       <h1 className="text-3xl font-bold mb-6 text-center">🎬 YouTube Downloader</h1>

//       <div className="flex gap-3 mb-6">
//         <input
//           className="flex-grow border p-2 rounded"
//           placeholder="Paste YouTube link..."
//           value={url}
//           onChange={(e) => setUrl(e.target.value)}
//         />
//         <button
//           onClick={fetchPreview}
//           disabled={loading}
//           className={`px-4 py-2 rounded text-white ${
//             loading ? "bg-gray-400" : "bg-blue-600 hover:bg-blue-700"
//           }`}
//         >
//           {loading ? "⏳ Loading..." : "Preview"}
//         </button>
//       </div>

//       {loading && (
//         <div className="flex justify-center mt-10">
//           <div className="animate-spin rounded-full h-10 w-10 border-t-4 border-blue-500"></div>
//         </div>
//       )}

//       {preview && (
//         <div className="border p-4 rounded shadow bg-white">
//           <div className="flex flex-col items-center">
//             <video
//               controls
//               className="w-full max-w-2xl rounded-lg"
//               poster={preview.thumbnail}
//               src={preview.combined_formats?.[0]?.url || preview.video_formats?.[0]?.url}
//             ></video>

//             <h2 className="text-lg font-semibold mt-3">{preview.title}</h2>

//             <button
//               onClick={() => setShowDownloadModal(true)}
//               className="bg-green-600 text-white px-4 py-2 rounded mt-4 hover:bg-green-700"
//             >
//               Download Options 🎧📽️
//             </button>
//           </div>

//           {showDownloadModal && (
//             <div className="fixed inset-0 flex items-center justify-center bg-black/50 z-50">
//               <div className="bg-white p-6 rounded-lg shadow-xl w-96">
//                 <h3 className="text-xl font-semibold mb-4 text-center">
//                   Select Download Options
//                 </h3>

//                 {/* 🧩 Mode Selector */}
//                 <div className="mb-4">
//                   <label className="font-medium">Mode:</label>
//                   <select
//                     value={mode}
//                     onChange={(e) => setMode(e.target.value)}
//                     className="border p-2 rounded mt-2 w-full"
//                   >
//                     <option value="merged">🎬 Merged (Audio + Video)</option>
//                     <option value="video">🎞️ Video Only</option>
//                     <option value="audio">🎧 Audio Only</option>
//                   </select>
//                 </div>

//                 {(mode === "video" || mode === "merged") && (
//                   <div className="mb-3">
//                     <label className="font-medium">Video Quality:</label>
//                     <select
//                       value={selectedVideo}
//                       onChange={(e) => setSelectedVideo(e.target.value)}
//                       className="border p-2 rounded mt-2 w-full"
//                     >
//                       <option value="">-- Select Video Format --</option>
//                       {preview.video_formats.map((f) => (
//                         <option key={f.format_id} value={f.format_id}>
//                           {f.resolution || "?"}p ({f.ext})
//                         </option>
//                       ))}
//                     </select>
//                   </div>
//                 )}

//                 {(mode === "audio" || mode === "merged") && (
//                   <div className="mb-3">
//                     <label className="font-medium">Audio Quality:</label>
//                     <select
//                       value={selectedAudio}
//                       onChange={(e) => setSelectedAudio(e.target.value)}
//                       className="border p-2 rounded mt-2 w-full"
//                     >
//                       <option value="">-- Select Audio Format --</option>
//                       {preview.audio_formats.map((f) => (
//                         <option key={f.format_id} value={f.format_id}>
//                           {f.ext} ({f.abr ? `${f.abr} kbps` : "unknown"})
//                         </option>
//                       ))}
//                     </select>
//                   </div>
//                 )}

//                 {/* 📊 Progress Bar */}
//                 {downloading && (
//                   <div className="w-full bg-gray-200 rounded-full h-3 mt-4">
//                     <div
//                       className="bg-green-600 h-3 rounded-full transition-all"
//                       style={{ width: `${progress}%` }}
//                     ></div>
//                     <p className="text-sm text-center mt-1">{progress}%</p>
//                   </div>
//                 )}

//                 <div className="flex justify-between mt-5">
//                   <button
//                     onClick={() => setShowDownloadModal(false)}
//                     className="px-4 py-2 bg-gray-300 rounded hover:bg-gray-400"
//                   >
//                     Cancel
//                   </button>
//                   <button
//                     onClick={download}
//                     disabled={downloading}
//                     className={`px-4 py-2 rounded text-white ${
//                       downloading ? "bg-gray-400" : "bg-green-600 hover:bg-green-700"
//                     }`}
//                   >
//                     {downloading ? "Downloading..." : "Download"}
//                   </button>
//                 </div>
//               </div>
//             </div>
//           )}
//         </div>
//       )}
//     </div>
//   );
// }


export default function App() {
  const [activeTab, setActiveTab] = useState("home");

  const renderTab = () => {
    switch (activeTab) {
      case "home":
        return <Home setActiveTab={setActiveTab} />;
      case "downloader":
        return <Downloader />;
      case "trimmer":
        return <Trimmer />;
      default:
        return <Home setActiveTab={setActiveTab} />;
    }
  };

  return (
    <div className="min-h-screen bg-gray-50 text-gray-900">
      <header className="flex justify-between items-center px-8 py-4 bg-white shadow">
        <h1 className="text-2xl font-bold">🎬 YouTube Toolkit</h1>

        <nav className="flex gap-4">
          <button
            className={`px-4 py-2 rounded ${
              activeTab === "downloader" ? "bg-blue-600 text-white" : "bg-gray-200"
            }`}
            onClick={() => setActiveTab("downloader")}
          >
            Downloader
          </button>

          <button
            className={`px-4 py-2 rounded ${
              activeTab === "trimmer" ? "bg-blue-600 text-white" : "bg-gray-200"
            }`}
            onClick={() => setActiveTab("trimmer")}
          >
            Trimmer
          </button>
        </nav>
      </header>

      <main className="p-6">{renderTab()}</main>
    </div>
  );
}
