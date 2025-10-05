import React, { useState } from "react";
import Home from "./pages/Home";
import Downloader from "./components/Downloader";
import Trimmer from "./components/Trimmer";

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
        <h1 className="text-2xl font-bold">🎬 Toolkit</h1>

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
