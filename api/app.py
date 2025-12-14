import concurrent.futures
import json
import re
import asyncio
import os
from flask import Flask, request, jsonify
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError

# --- Flask App Initialization ---
app = Flask(__name__)

# --- Configuration: Full Embed URL Templates ---
SERVER_TEMPLATES = {
    "[ALPHA]": "https://player.vidify.top/embed/movie/{id}?autoplay=false&poster=false&chromecast=false&servericon=false&setting=false&pip=false&font=Roboto&fontcolor=6f63ff&fontsize=20&opacity=0.5&primarycolor=3b82f6&secondarycolor=1f2937&iconcolor=ffffff&server=adam",
    "[BRAVO]": "https://player.vidify.top/embed/movie/{id}?autoplay=false&poster=false&chromecast=false&servericon=false&setting=false&pip=false&font=Roboto&fontcolor=6f63ff&fontsize=20&opacity=0.5&primarycolor=3b82f6&secondarycolor=1f2937&iconcolor=ffffff&server=alok",
    "[CHARLIE]": "https://player.vidify.top/embed/movie/{id}?autoplay=false&poster=false&chromecast=false&servericon=false&setting=false&pip=false&font=Roboto&fontcolor=6f63ff&fontsize=20&opacity=0.5&primarycolor=3b82f6&secondarycolor=1f2937&iconcolor=ffffff&server=box",
    "[DELTA]": "https://player.vidify.top/embed/movie/{id}?autoplay=false&poster=false&chromecast=false&servericon=false&setting=false&pip=false&font=Roboto&fontcolor=6f63ff&fontsize=20&opacity=0.5&primarycolor=3b82f6&secondarycolor=1f2937&iconcolor=ffffff&server=cypher",
    "[ECHO]": "https://player.vidify.top/embed/movie/{id}?autoplay=false&poster=false&chromecast=false&servericon=false&setting=false&pip=false&font=Roboto&fontcolor=6f63ff&fontsize=20&opacity=0.5&primarycolor=3b82f6&secondarycolor=1f2937&iconcolor=ffffff&server=haxo",
    "[FOXTROT]": "https://player.vidify.top/embed/movie/{id}?autoplay=false&poster=false&chromecast=false&servericon=false&setting=false&pip=false&font=Roboto&fontcolor=6f63ff&fontsize=20&opacity=0.5&primarycolor=3b82f6&secondarycolor=1f2937&iconcolor=ffffff&server=lux",
    "[GOLF]": "https://player.vidify.top/embed/movie/{id}?autoplay=false&poster=false&chromecast=false&servericon=false&setting=false&pip=false&font=Roboto&fontcolor=6f63ff&fontsize=20&opacity=0.5&primarycolor=3b82f6&secondarycolor=1f2937&iconcolor=ffffff&server=mbox",
    "[HOTEL]": "https://player.vidify.top/embed/movie/{id}?autoplay=false&poster=false&chromecast=false&servericon=false&setting=false&pip=false&font=Roboto&fontcolor=6f63ff&fontsize=20&opacity=0.5&primarycolor=3b82f6&secondarycolor=1f2937&iconcolor=ffffff&server=meta",
    "[INDIA]": "https://player.vidify.top/embed/movie/{id}?autoplay=false&poster=false&chromecast=false&servericon=false&setting=false&pip=false&font=Roboto&fontcolor=6f63ff&fontsize=20&opacity=0.5&primarycolor=3b82f6&secondarycolor=1f2937&iconcolor=ffffff&server=nitro",
    "[JULIET]": "https://player.vidify.top/embed/movie/{id}?autoplay=false&poster=false&chromecast=false&servericon=false&setting=false&pip=false&font=Roboto&fontcolor=6f63ff&fontsize=20&opacity=0.5&primarycolor=3b82f6&secondarycolor=1f2937&iconcolor=ffffff&server=prime",
    "[KILO]": "https://player.vidify.top/embed/movie/{id}?autoplay=false&poster=false&chromecast=false&servericon=false&setting=false&pip=false&font=Roboto&fontcolor=6f63ff&fontsize=20&opacity=0.5&primarycolor=3b82f6&secondarycolor=1f2937&iconcolor=ffffff&server=veasy",
    "[LIMA]": "https://player.vidify.top/embed/movie/{id}?autoplay=false&poster=false&chromecast=false&servericon=false&setting=false&pip=false&font=Roboto&fontcolor=6f63ff&fontsize=20&opacity=0.5&primarycolor=3b82f6&secondarycolor=1f2937&iconcolor=ffffff&server=vplus",
    "[MIKE]": "https://player.vidify.top/embed/movie/{id}?autoplay=false&poster=false&chromecast=false&servericon=false&setting=false&pip=false&font=Roboto&fontcolor=6f63ff&fontsize=20&opacity=0.5&primarycolor=3b82f6&secondarycolor=1f2937&iconcolor=ffffff&server=yoru",
}

# Regex pattern is mainly for network request filtering now
M3U8_PATTERN = re.compile(r'(https?:\/\/[^\s]*?\.m3u8[^\s\'"]*)')

# --- Scraper Function (ASYNC, uses Playwright) ---
async def scrape_embed_url_async(tmdb_id, tag):
    """
    Launches a headless browser, navigates to the embed URL, and monitors
    network requests for any URL containing '.m3u8' or '.mpd'.
    """
    
    embed_url = SERVER_TEMPLATES[tag].format(id=tmdb_id)
    found_urls = set()
    
    # --- Playwright Configuration for Vercel/Lambda ---
    # Attempt to find the Chromium executable installed by the vercel.json command.
    # The default location is relative to the execution environment.
    CHROMIUM_EXECUTABLE_PATH = os.path.join(
        os.getcwd(), 'node_modules', 'playwright', '.local-browsers', 'chromium-115', 'chrome-linux', 'chrome'
    )
    # Fallback/Safety Check - Playwright is good at finding it, but this explicitly guides it.
    if not os.path.exists(CHROMIUM_EXECUTABLE_PATH):
         CHROMIUM_EXECUTABLE_PATH = None
    
    try:
        async with async_playwright() as p:
            # Launch the browser with necessary serverless arguments
            browser = await p.chromium.launch(
                executable_path=CHROMIUM_EXECUTABLE_PATH,
                headless=True,
                args=['--no-sandbox', '--disable-setuid-sandbox', '--single-process']
            )
            page = await browser.new_page()

            # --- Network Request Monitoring ---
            def check_request(request):
                url = request.url
                # Filter for the manifest file (case-insensitive)
                if ".m3u8" in url.lower() or ".mpd" in url.lower():
                    if M3U8_PATTERN.search(url):
                        found_urls.add(url.strip())
            
            page.on("request", check_request)

            # Navigate to the embed page and wait for network stability
            await page.goto(embed_url, wait_until="networkidle", timeout=30000)
            
            # Allow a brief moment for final dynamic requests to complete
            await page.wait_for_timeout(2000) 

            await browser.close()
            
            if found_urls:
                return {"tag": tag, "status": "success", "urls": sorted(list(found_urls))}
            
            return {"tag": tag, "status": "not_found", "message": "Embed page loaded, but no M3U8/MPD link found in network traffic."}

    except PlaywrightTimeoutError:
        return {"tag": tag, "status": "error", "message": "Playwright Timeout: Page took too long to load or stabilize."}
    except Exception as e:
        return {"tag": tag, "status": "error", "message": f"Playwright Error on {tag}: {type(e).__name__}: {str(e)}"}

# --- Helper Function to Run Async Code in ThreadPoolExecutor ---
def run_async_scrape(tmdb_id, tag):
    """A wrapper to run the async scraping function synchronously."""
    # asyncio.run() runs the async function and manages the event loop
    return asyncio.run(scrape_embed_url_async(tmdb_id, tag))


# --- Flask Web Endpoint ---
@app.route('/', methods=['GET'])
@app.route('/api', methods=['GET'])
def scrape_endpoint():
    """
    API endpoint that accepts a TMDb ID and executes the concurrent scraping of embed pages.
    """
    tmdb_id = request.args.get('id')
    
    if not tmdb_id or not tmdb_id.isdigit():
        return jsonify({"error": "Invalid or missing 'id' parameter."}), 400

    final_results = {}
    total_urls = 0
    max_workers = len(SERVER_TEMPLATES)
    
    # Use ThreadPoolExecutor to run multiple synchronous wrappers concurrently
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        
        futures = [
            executor.submit(run_async_scrape, tmdb_id, tag)
            for tag in SERVER_TEMPLATES.keys()
        ]

        for future in concurrent.futures.as_completed(futures):
            result = future.result()
            tag = result['tag']
            
            if result['status'] == 'success':
                urls_list = result['urls']
                final_results[tag] = {"status": "success", "urls": urls_list}
                total_urls += len(urls_list)
            else:
                final_results[tag] = result
    
    return jsonify({
        "tmdb_id": tmdb_id,
        "total_servers_checked": len(SERVER_TEMPLATES),
        "total_urls_found": total_urls,
        "results": final_results
    })

# Note: The standard Flask run block is removed for Vercel deployment.
# Vercel automatically detects and runs the 'app' object.
