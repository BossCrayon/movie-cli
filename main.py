#!/usr/bin/env python3
import asyncio
import sys
import shutil
import subprocess
import aiohttp
from playwright.async_api import async_playwright
from rich.console import Console
from rich.prompt import Prompt

console = Console()
USER_DATA_DIR = "./browser_data"

SOURCES = [
    {"url": "https://vidsrc.net/embed/movie/", "name": "VidSrc.net"},
    {"url": "https://vidsrcme.ru/embed/movie/", "name": "VidSrcMe.ru"},
    {"url": "https://vidsrc.xyz/embed/movie/", "name": "VidSrc.xyz"},
    {"url": "https://vidsrc-embed.ru/embed/movie/", "name": "VidSrc-Embed"},
    {"url": "https://autoembed.cc/embed/movie/", "name": "AutoEmbed"},
    {"url": "https://vidsrc.cc/v2/embed/movie/", "name": "VidSrc.cc"},
]

def check_mpv_installed():
    if not shutil.which("mpv"):
        console.print("[bold red]CRITICAL: MPV not installed[/bold red]")
        sys.exit(1)

async def get_movie_id(query):
    q = query.replace(" ", "_")
    url = f"https://v2.sg.media-imdb.com/suggestion/{q[0].lower()}/{q}.json"
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                data = await resp.json()
        
        results = []
        for item in data.get("d", []):
            if item.get("id", "").startswith("tt"):
                title = item.get("l", "Unknown")
                year = item.get("y", "??")
                stars = item.get("s", "")
                results.append((item["id"], f"{title} ({year}) - {stars}"))
        return results
    except Exception:
        return []

async def sniff_stream_from_source(page, imdb_id, source):
    server_url = f"{source['url']}{imdb_id}"
    
    found_data = asyncio.Future()

    async def handle_request(request):
        try:
            url = request.url
            if ".m3u8" in url or ".mp4" in url:
                if "favicon" not in url and ".png" not in url:
                    if not found_data.done():
                        headers = request.headers
                        found_data.set_result({
                            "url": url,
                            "referer": headers.get("referer", page.url),
                            "user_agent": headers.get("user-agent", ""),
                            "cookie": headers.get("cookie", "")
                        })
        except: pass

    async def lock_navigation(frame):
        if frame == page.main_frame and page.url == "about:blank":
            try: await page.goto(server_url, wait_until="commit")
            except: pass

    page.on("request", handle_request)
    page.on("framenavigated", lock_navigation)

    try:
        await page.goto(server_url, timeout=20000, wait_until="commit")
        
        with console.status(f"[bold cyan]Scanning {source['name']}...[/bold cyan]", spinner="dots") as status:
            
            for attempt in range(30):
                if found_data.done(): return await found_data

                try:
                    if ".m3u8" in page.url or ".mp4" in page.url:
                        return {"url": page.url, "referer": server_url, "user_agent": "", "cookie": ""}
                    content = await page.content()
                    if "#EXTM3U" in content:
                        return {"url": page.url, "referer": server_url, "user_agent": "", "cookie": ""}
                except: pass

                try:
                    vp = page.viewport_size
                    await page.mouse.click(vp["width"] / 2, vp["height"] / 2)
                    
                    for frame in page.frames:
                        try:
                            await frame.evaluate("const v = document.querySelector('video'); if(v) v.play();")
                            btn = await frame.query_selector("button, .play, video, .jw-display-icon-display")
                            if btn: await btn.click(force=True, timeout=100) 
                        except: pass
                except: pass
                
                try:
                    await asyncio.wait_for(asyncio.shield(found_data), timeout=0.5) 
                    return await found_data
                except asyncio.TimeoutError:
                    pass

        return None

    except Exception:
        return None
    finally:
        page.remove_listener("request", handle_request)
        page.remove_listener("framenavigated", lock_navigation)

def play_with_mpv(data, title):
    url = data["url"]
    ua = data.get("user_agent") or "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    referer = data.get("referer") or "https://vidsrc.net/"
    cookie = data.get("cookie") or ""

    console.print(f"\n[bold green]Found Stream![/bold green] [dim]{url[:50]}...[/dim]")
    
    header_args = f"Referer: {referer},User-Agent: {ua}"
    if cookie:
        header_args += f",Cookie: {cookie}"

    cmd = [
        shutil.which("mpv"),
        url,
        f"--force-media-title={title}",
        f"--user-agent={ua}",
        f"--referrer={referer}",
        f"--http-header-fields={header_args}",
        "--fs",
        "--msg-level=all=no" 
    ]
    
    subprocess.run(cmd)

async def main():
    check_mpv_installed()
    
    query = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else Prompt.ask("Search Movie")
    
    with console.status("[cyan]Searching IMDb...[/cyan]"):
        movies = await get_movie_id(query)
    
    if not movies:
        console.print("[red]No results found[/red]")
        return

    console.print("\n[bold yellow]Select Movie:[/bold yellow]")
    for i, (_, text) in enumerate(movies[:5]):
        console.print(f"{i+1}. {text}")

    try:
        idx = int(Prompt.ask("Number")) - 1
        imdb_id, display = movies[idx]
        title = display.split("(")[0].strip()
    except: return

    async with async_playwright() as p:
        console.print("[dim]Launching browser...[/dim]")
        
        context = await p.chromium.launch_persistent_context(
            USER_DATA_DIR,
            headless=True,
            viewport={"width": 1280, "height": 720},
            args=["--disable-blink-features=AutomationControlled", "--no-sandbox"],
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = context.pages[0]
        context.on("page", lambda p: asyncio.create_task(p.close()) if p.url == "about:blank" else None)

        stream_data = None
        for source in SOURCES:
            stream_data = await sniff_stream_from_source(page, imdb_id, source)
            
            if stream_data:
                break
            else:
                console.print(f"[dim]  -> {source['name']} failed. Switching...[/dim]")

        await context.close()

        if stream_data:
            play_with_mpv(stream_data, title)
        else:
            console.print("[bold red]All sources failed.[/bold red]")

if __name__ == "__main__":
    asyncio.run(main())
