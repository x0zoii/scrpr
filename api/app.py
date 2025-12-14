import os
import asyncio
import json
from concurrent.futures import ThreadPoolExecutor

from flask import Flask, request, jsonify, abort
from playwright.async_api import async_playwright

app = Flask(__name__)
executor = ThreadPoolExecutor(max_workers=20)

# --- Configuration for Scraping ---
TAGS = [
    # Define your server tags and URLs here
    '[ALPHA]', '[BRAVO]', '[CHARLIE]', '[DELTA]', 
    '[ECHO]', '[FOXTROT]', '[GOLF]', '[HOTEL]', 
    '[INDIA]', '[JULIET]', '[KILO]', '[LIMA]', '[MIKE]'
]

def generate_embed_url(tmdb_id, tag):
    # This function should contain your actual URL generation logic.
    # Placeholder for demonstration:
    return f"https://example.com/embed/{tag}/{tmdb_id}" 

# --- Core Async Scraper Function ---
async def scrape_embed_url_async(tmdb_id, tag):
    result = {'tag': tag, 'status': 'not_found', 'urls': []}
    
    # 1. Determine the Executable Path
    # The PLAYWRIGHT_BROWSERS_PATH=0 setting in vercel.json forces 
    # installation to the local directory (relative to PWD).
    # The path is typically: PWD/ms-playwright/chromium/chrome
    
    executable = os.path.join(
        os.getcwd(), 'ms-playwright', 'chromium', 'chrome'
    )
    
    # Simple check for immediate feedback if the path is still wrong
    if not os.path.exists(executable):
        result['status'] = 'error'
        result['message'] = f"Playwright Executable not found at expected path: {executable}"
        return result
        
    embed_url = generate_embed_url(tmdb_id, tag)
    
    try:
        async with async_playwright() as p:
            # 2. Launch Browser with the specific executable path
            browser = await p.chromium.launch(
                executable_path=executable, # <--- THIS IS THE FIX
                headless=True,
                # These args are CRITICAL for Vercel/Lambda environments
                args=['--no-sandbox', '--disable-setuid-sandbox', '--single-process']
            )
            page = await browser.new_page()

            # Listen for network requests to find streaming links
            found_urls = set()
            def handle_request(request_obj):
                url = request_obj.url
                if '.m3u8' in url or '.mpd' in url:
                    found_urls.add(url)

            page.on("request", handle_request)

            # Navigate and wait for the page to load or a timeout
            await page.goto(embed_url, wait_until="networkidle", timeout=15000)

            await asyncio.sleep(5) # Give the player time to load resources

            if found_urls:
                result['status'] = 'success'
                result['urls'] = list(found_urls)
            
            await browser.close()

    except Exception as e:
        result['status'] = 'error'
        result['message'] = f"Playwright Error on {tag}: {e}"
        
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
        # Simple HTML response for base URL testing
        return "<h1>TMDB Scraper is running.</h1><p>Please use /?id=[TMDB_ID_HERE] to start scraping.</p>"

    try:
        # Use ThreadPoolExecutor to run the concurrent scrape tasks
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
        # Handle general errors gracefully
        return jsonify({
            'error': 'An internal server error occurred during scraping.',
            'details': str(e)
        }), 500

if __name__ == '__main__':
    # This block is for local testing only
    app.run(debug=True)
