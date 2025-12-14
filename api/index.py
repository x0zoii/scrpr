import asyncio
import json
import os
import glob # Used to find the dynamically named Chromium folder

from flask import Flask, request, jsonify
from playwright.async_api import async_playwright

# --- CRITICAL ENVIRONMENT SETUP ---
# Playwright is instructed via vercel.json to install binaries to /tmp/pw.
# We must find the exact executable path within that dynamic folder structure.
def get_chromium_executable_path():
    """
    Dynamically finds the Chromium executable path within the Vercel /tmp/pw directory.
    
    The structure is usually: /tmp/pw/chromium-[version]/chrome-linux/chrome
    """
    
    # 1. Look inside the known install path defined by PLAYWRIGHT_BROWSERS_PATH
    install_root = os.environ.get('PLAYWRIGHT_BROWSERS_PATH', '/tmp/pw')
    
    # 2. Use glob to search for any folder matching 'chromium*'
    # The pattern finds the executable regardless of the Playwright version number.
    paths = glob.glob(os.path.join(install_root, 'chromium*', 'chrome-linux', 'chrome'))
    
    if paths:
        # Return the first matching path found
        return paths[0]
    
    # Fallback to None, which lets Playwright use its default auto-discovery 
    # (though this is what caused the original error, we must have a path)
    return None

CHROMIUM_EXECUTABLE_PATH = get_chromium_executable_path()

# This is a critical LD_LIBRARY_PATH fix to help Chromium find its dependent libraries
# This path is usually one level above the executable path.
if CHROMIUM_EXECUTABLE_PATH:
    # Example: if executable is /tmp/pw/chromium-X/chrome-linux/chrome, 
    # we need /tmp/pw/chromium-X/chrome-linux
    library_path = os.path.dirname(CHROMIUM_EXECUTABLE_PATH)
    os.environ['LD_LIBRARY_PATH'] = library_path + ':' + os.environ.get('LD_LIBRARY_PATH', '')


app = Flask(__name__)

# --- Configuration for Scraping ---
TAGS = [
    '[ALPHA]', '[BRAVO]', '[CHARLIE]', '[DELTA]', 
    '[ECHO]', '[FOXTROT]', '[GOLF]', '[HOTEL]', 
    '[INDIA]', '[JULIET]', '[KILO]', '[LIMA]', '[MIKE]'
]

def generate_embed_url(tmdb_id, tag):
    return f"https://example.com/embed/{tag}/{tmdb_id}" 

# --- Core Async Scraper Function ---
async def scrape_embed_url_async(browser, tmdb_id, tag):
    result = {'tag': tag, 'status': 'not_found', 'urls': []}
    
    embed_url = generate_embed_url(tmdb_id, tag)
    
    try:
        context = await browser.new_context()
        page = await context.new_page()

        found_urls = set()
        def handle_request(request_obj):
            url = request_obj.url
            if '.m3u8' in url or '.mpd' in url:
                found_urls.add(url)

        page.on("request", handle_request)

        await page.goto(embed_url, wait_until="networkidle", timeout=15000)
        await asyncio.sleep(5)

        if found_urls:
            result['status'] = 'success'
            result['urls'] = list(found_urls)
        
        await context.close()

    except Exception as e:
        result['status'] = 'error'
        result['message'] = f"Playwright Error on {tag}: {e}"
        
    return result

# --- Asynchronous Handler Function (Launches browser once) ---
async def async_handler(tmdb_id):
    playwright_instance = await async_playwright().start()
    browser = None
    
    if not CHROMIUM_EXECUTABLE_PATH:
        # If we failed to find the executable, raise a clear error to the logs
        raise EnvironmentError(
            "CRITICAL: Chromium executable path could not be resolved in the /tmp/pw directory. "
            "The Playwright install step may have failed or the path structure changed."
        )

    try:
        # CRITICAL: Use the dynamically found executable path
        # This is the last and best chance to fix the FUNCTION_INVOCATION_FAILED crash.
        browser = await playwright_instance.chromium.launch(
            executable_path=CHROMIUM_EXECUTABLE_PATH,
            headless=True,
            # These arguments are essential for Lambda/Vercel environments
            args=['--no-sandbox', '--disable-setuid-sandbox', '--single-process']
        )
        
        tasks = [
            scrape_embed_url_async(browser, tmdb_id, tag)
            for tag in TAGS
        ]

        return await asyncio.gather(*tasks)
    
    finally:
        if browser:
            await browser.close()
        await playwright_instance.stop()

# --- Flask Endpoint ---
@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
@app.route('/api', defaults={'path': ''})
@app.route('/api/<path:path>')
def handler(path):
    tmdb_id = request.args.get('id')
    
    if not tmdb_id:
        return "<h1>TMDB Scraper is running.</h1><p>Please use /api?id=[TMDB_ID_HERE] to start scraping.</p>"

    try:
        raw_results = asyncio.run(async_handler(tmdb_id))
        
        results = {}
        total_urls_found = 0
        
        for result in raw_results:
            results[result['tag']] = {
                'status': result['status'],
                'message': result.get('message'),
                'urls': result.get('urls', [])
            }
            if result['status'] == 'success':
                total_urls_found += len(result['urls'])

        response_data = {
            'tmdb_id': tmdb_id,
            'total_servers_checked': len(TAGS),
            'total_urls_found': total_urls_found,
            'results': results
        }
        
        return jsonify(response_data)

    except Exception as e:
        # This catches both the low-level crash and the custom EnvironmentError
        return jsonify({
            'error': 'An internal server error occurred during scraping.',
            'details': str(e)
        }), 500

if __name__ == '__main__':
    app.run(debug=True)
