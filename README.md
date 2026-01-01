# Movie-CLI 🎬

A robust, terminal-based movie streamer inspired by `ani-cli`. It scrapes streaming links in parallel using a headless browser and plays them directly in **MPV**.

## Features
- 🚀 **Parallel Scanning:** Checks VidSrc, AutoEmbed, and others simultaneously.
- 🛡️ **Anti-Ban:** Clones browser headers (Referer, Cookies) to pass MPV as a real browser.
- 🔁 **Auto-Retry:** Automatically loops back if sources fail.
- 🍿 **No Ads:** Plays directly in MPV, skipping website ads and popups.

⚠️ Important Note regarding Scans
Movie-CLI is not 100% guaranteed. Streaming sites frequently change their code, anti-bot protections, or server names.

## Requirements
- Python 3.8+
- MPV Player (`sudo apt install mpv` or `brew install mpv`)

## Installation

```bash
# 1. Clone the repo
git clone [https://github.com/BossCrayon/movie-cli.git](https://github.com/BossCrayon/movie-cli.git)
cd movie-cli

# 2. Install dependencies
pip install -r requirements.txt
playwright install chromium

# 3. Run
./main.py
