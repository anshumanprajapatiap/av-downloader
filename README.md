# Audio and Video Downloader Utility



# Docker compose run
```sh
  docker-compose up --build
```




# Running on System:

⚙️ 1️⃣ Create and activate virtual environment
macOS / Linux:
    ```
        python3 -m venv venv
        source venv/bin/activate
    ```

Windows (PowerShell):
python -m venv venv
.\venv\Scripts\activate


You’ll see (venv) prefix in your terminal → means the virtual environment is active.

⚙️ 2️⃣ Install dependencies
pip install -r requirements.txt

⚙️ 3️⃣ Install ffmpeg (system dependency)
macOS (Homebrew)
brew install ffmpeg

Ubuntu/Debian
sudo apt update && sudo apt install -y ffmpeg

Windows

Download ffmpeg from https://ffmpeg.org/download.html

Extract it and add its bin folder to your system PATH.
(Example: C:\ffmpeg\bin)

You can verify installation with:

ffmpeg -version

⚙️ 4️⃣ Run FastAPI in development mode

From project root:

uvicorn app.main:app --reload --host 0.0.0.0 --port 8000


--reload auto-reloads the server when you edit code.

Open http://localhost:8000
 in your browser.


# 1️⃣ Build image
docker build -t youtube-downloader .

# 2️⃣ Run container (mount downloads)
docker run -d \
  -p 8000:8000 \
  -v $(pwd)/downloads:/app/downloads \
  --name yt-dl youtube-downloader


Then open 👉 http://localhost:8000

⚙️ CLI usage inside container

You can also use it directly via CLI:

docker exec -it yt-dl python -m app.downloader "https://www.youtube.com/watch?v=YOUR_ID"


docker exec -it yt-dl bash






🌍 If you want anyone to access it globally

Here are your options — from easiest to most production-ready:

brew install ngrok
ngrok http 5173


Forwarding → https://fussily-subfractionary-irmgard.ngrok-free.dev -> http://localhost:5173

ngrok http 8000
