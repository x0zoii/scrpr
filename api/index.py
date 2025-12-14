import os
import asyncio
import json

from flask import Flask, request, jsonify
from playwright.async_api import async_playwright

# --- Vercel/Playwright Final Environment Fix ---
# We keep this line as a safeguard, pointing to the known Lambda-compatible path
os.environ['LD_LIBRARY_PATH'] = os.path.join(os.getcwd(), '.playwright', 'chromium') + ':' + os.environ.get('LD_LIBRARY_PATH', '')
# --- END Fix ---

app = Flask(__name__)
# REMOVED: executor = ThreadPoolExecutor(max_workers=20)

# --- Configuration for Scraping ---
TAGS = [
    # Define your server tags and URLs here
    '[ALPHA]', '[BRAVO]', '[CHARLIE]', '[DELTA]', 
    '[ECHO]', '[FOXTROT]', '[GOLF]', '[HOTEL]', 
    '[INDIA]', '[JULIET]', '[KILO]', '[LIMA]', '[MIKE]'
]

def generate_embed_url(tmdb_id, tag):
    # This function should contain your actual URL generation logic.
    return f"https://example.com/embed/{tag}/{tmdb_id}" 

# --- Core Async Scraper Function (UNCHANGED) ---
async def scrape_embed_url_async(tmdb_id, tag):
    result = {'tag': tag, 'status': 'not_found', 'urls': []}
    
    embed_url = generate_embed_url(tmdb_id, tag)
    
    try:
        # Use a single playwright instance launch for all concurrent tasks
        async with async_playwright() as p:
            # We are reverting to the simple launch, as the environment fixes should work
            # If this fails, we can re-add executable_path=CHROMIUM_EXECUTABLE_PATH
            browser = await p.chromium.launch(
                headless=True,
                args=['--no-sandbox', '--disable-setuid-sandbox', '--single-process']
            )
            page = await browser.new_page()

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
            
            await browser.close()

    except Exception as e:
        result['status'] = 'error'
        result['message'] = f"Playwright Error on {tag}: {e}"
        
    return result

# --- NEW: Asynchronous Handler Function ---
async def async_handler(tmdb_id):
    # Create a list of all scraping tasks
    tasks = [
        scrape_embed_url_async(tmdb_id, tag)
        for tag in TAGS
    ]

    # Run all tasks concurrently using one efficient event loop
    return await asyncio.gather(*tasks)

# --- Flask Endpoint (MODIFIED) ---
@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
@app.route('/api', defaults={'path': ''})
@app.route('/api/<path:path>')
def handler(path):
    tmdb_id = request.args.get('id')
    
    if not tmdb_id:
        return "<h1>TMDB Scraper is running.</h1><p>Please use /api?id=[TMDB_ID_HERE] to start scraping.</p>"

    try:
        # We now run the entire concurrent scraping process synchronously using asyncio.run
        # This is efficient because it uses a single thread/loop.
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
        return jsonify({
            'error': 'An internal server error occurred during scraping.',
            'details': str(e)
        }), 500

if __name__ == '__main__':
    app.run(debug=True)
