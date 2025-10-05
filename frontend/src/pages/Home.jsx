
export default function Home({ setActiveTab }) {
  return (
    <div className="text-center mt-20">
      <h2 className="text-3xl font-bold mb-4">Welcome to Toolkit 🎥</h2>
      <p className="text-lg text-gray-600 mb-6">
        Download, trim your favorite videos or audios with ease.
      </p>

      <div className="flex justify-center gap-6">
        <button
          onClick={() => setActiveTab("downloader")}
          className="bg-blue-600 text-white px-6 py-3 rounded-lg hover:bg-blue-700"
        >
          Go to Downloader
        </button>

        {/* <button
          onClick={() => setActiveTab("trimmer")}
          className="bg-green-600 text-white px-6 py-3 rounded-lg hover:bg-green-700"
        >
          Go to Trimmer
        </button> */}
      </div>
    </div>
  );
}
