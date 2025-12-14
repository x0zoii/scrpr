import os
import asyncio
import json
from concurrent.futures import ThreadPoolExecutor

from flask import Flask, request, jsonify
from playwright.async_api import async_playwright

# --- Vercel/Playwright Final Environment Fix ---
# Use the known working path for Lambda-compatible Chromium.
# NOTE: This path is where pre-compiled Chromium for Lambda is often placed.
CHROMIUM_EXECUTABLE_PATH = '/usr/bin/chromium' 
# You may also need to check this path: /opt/bin/chromium (If the Vercel builder uses a layer)
# We will use the Vercel recommended path for now.
# --- END Fix ---

app = Flask(__name__)
executor = ThreadPoolExecutor(max_workers=20)

# --- Configuration for Scraping ---
TAGS = [
    '[ALPHA]', '[BRAVO]', '[CHARLIE]', '[DELTA]', 
    '[ECHO]', '[FOXTROT]', '[GOLF]', '[HOTEL]', 
    '[INDIA]', '[JULIET]', '[KILO]', '[LIMA]', '[MIKE]'
]

def generate_embed_url(tmdb_id, tag):
    return f"https://example.com/embed/{tag}/{tmdb_id}" 

# --- Core Async Scraper Function ---
async def scrape_embed_url_async(tmdb_id, tag):
    result = {'tag': tag, 'status': 'not_found', 'urls': []}
    
    embed_url = generate_embed_url(tmdb_id, tag)
    
    # Try the Lambda-compatible executable path
    try:
        async with async_playwright() as p:
            
            # The executable_path is used here to bypass Playwright's default auto-detection,
            # which leads to the FUNCTION_INVOCATION_FAILED error.
            browser = await p.chromium.launch(
                executable_path=CHROMIUM_EXECUTABLE_PATH,
                headless=True,
                args=['--no-sandbox', '--disable-setuid-sandbox', '--single-process']
            )
            page = await browser.new_page()
            
            # ... (rest of the scraping logic remains the same) ...

            found_urls = set()
            def handle_request(request_obj):
                url = request_obj.url
                if '.m3u8' in url or '.mpd' in url:
                    found_urls.add(url)

            page.on("request", handle_request)

            await page.goto(embed_url, wait_until="networkidle", timeout=15000)

            await asyncio.sleep(5) # Give the player time to load resources

            if found_urls:
                result['status'] = 'success'
                result['urls'] = list(found_urls)
            
            await browser.close()

    except Exception as e:
        # If this fails, we try the cleaner launch without executable_path
        # and rely on the local Playwright install, just in case.
        # However, the previous failures indicate this will likely also fail.
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(
                    headless=True,
                    args=['--no-sandbox', '--disable-setuid-sandbox', '--single-process']
                )
                await browser.close() # Only checking if it launches
                result['status'] = 'error'
                result['message'] = f"Playwright Error on {tag}: {e} - Launch failed, falling back."
        except Exception as fallback_e:
            result['status'] = 'error'
            result['message'] = f"Playwright Error on {tag}: {fallback_e}"
        
    return result

# --- Synchronous Wrapper for Flask ---
def run_async_scrape(tmdb_id, tag):
    return asyncio.run(scrape_embed_url_async(tmdb_id, tag))

# --- Flask Endpoint ---
@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
@app.route('/api', defaults={'path': ''})
@app.route('/api/<path:path>')
def handler(path):
    tmdb_id = request.args.get('id')
    
    if not tmdb_id:
        # Return the expected Flask response for the root, fixing the NOT_FOUND
        return "<h1>TMDB Scraper is running.</h1><p>Please use /api?id=[TMDB_ID_HERE] to start scraping.</p>"

    try:
        futures = [
            executor.submit(run_async_scrape, tmdb_id, tag)
            for tag in TAGS
        ]
        
        results = {}
        total_urls_found = 0
        
        for future in futures:
            result = future.result()
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
        return jsonify({
            'error': 'An internal server error occurred during scraping.',
            'details': str(e)
        }), 500

if __name__ == '__main__':
    app.run(debug=True)
