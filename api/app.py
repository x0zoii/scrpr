import concurrent.futures
import json
import re
import asyncio
from flask import Flask, request, jsonify
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError

# --- Flask App Initialization ---
app = Flask(__name__)

# --- Configuration: Full Embed URL Templates ---
# (Kept the same for consistency)
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

# Regex pattern for cleaning the URLs, if needed (Playwright provides the full URL)
M3U8_PATTERN = re.compile(r'(https?:\/\/[^\s]*?\.m3u8[^\s\'"]*)')

# --- Scraper Function (ASYNC, uses Playwright) ---

# Note: Playwright uses async/await, so the function must be async
async def scrape_embed_url_async(tmdb_id, tag):
    """
    Launches a headless browser, navigates to the embed URL, and monitors
    network requests for any URL containing '.m3u8'.
    """
    
    embed_url = SERVER_TEMPLATES[tag].format(id=tmdb_id)
    found_urls = set()
    
    # We use a browser session within this function.
    # The 'p' object is the Playwright instance, 'browser' is the Chrome instance.
    try:
        async with async_playwright() as p:
            # Launch the browser (headless=True is the default)
            browser = await p.chromium.launch()
            page = await browser.new_page()

            # --- Network Request Monitoring ---
            # Set up a listener to capture network requests as they happen
            def check_request(request):
                url = request.url
                # Filter for the manifest file
                if ".m3u8" in url.lower() or ".mpd" in url.lower():
                    # Check if the URL matches the general M3U8 pattern (optional, for safety)
                    if M3U8_PATTERN.search(url):
                        found_urls.add(url.strip())
            
            page.on("request", check_request)

            # Navigate to the embed page and wait until all network activity subsides ('networkidle')
            await page.goto(embed_url, wait_until="networkidle", timeout=20000)
            
            # Allow a brief moment for any final dynamic requests to finish
            await page.wait_for_timeout(1000) 

            # Close the browser
            await browser.close()
            
            if found_urls:
                return {"tag": tag, "status": "success", "urls": sorted(list(found_urls))}
            
            # If no M3U8/MPD was found in the network traffic
            return {"tag": tag, "status": "not_found", "message": "Embed page loaded, but no M3U8/MPD link found in network traffic."}

    except PlaywrightTimeoutError:
        # Catch if the page takes too long to load
        return {"tag": tag, "status": "error", "message": "Playwright Timeout: Page took too long to load or stabilize."}
    except Exception as e:
        # Catch any other unexpected Playwright errors
        return {"tag": tag, "status": "error", "message": f"Playwright Error: {type(e).__name__}: {str(e)}"}


# --- Helper Function to Run Async Code in ThreadPoolExecutor ---

def run_async_scrape(tmdb_id, tag):
    """A wrapper to run the async scraping function synchronously."""
    # This is necessary because Flask's default environment is synchronous,
    # but Playwright is fundamentally an asynchronous library.
    return asyncio.run(scrape_embed_url_async(tmdb_id, tag))


# --- Flask Web Endpoint (Modified to call the sync wrapper) ---

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
    
    # Execution logic remains the same, but calls the sync wrapper
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        
        # Call run_async_scrape which wraps the Playwright logic
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

# --- Main block to run the Flask app ---
if __name__ == '__main__':
    # Flask app will run on port 5000 by default
    app.run(debug=True, host='0.0.0.0', port=5000, use_reloader=False)
