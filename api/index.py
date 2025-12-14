import os
import asyncio
import json

from flask import Flask, request, jsonify
# We import the classes directly to launch and close manually
from playwright.async_api import ChromiumBrowser, async_playwright 

# --- Vercel/Playwright Final Environment Fix ---
# Keep the most robust LD_LIBRARY_PATH fix
os.environ['LD_LIBRARY_PATH'] = os.path.join(os.getcwd(), '.playwright', 'chromium') + ':' + os.environ.get('LD_LIBRARY_PATH', '')
# --- END Fix ---

app = Flask(__name__)

# --- Configuration for Scraping ---
TAGS = [
    # Define your server tags and URLs here
    '[ALPHA]', '[BRAVO]', '[CHARLIE]', '[DELTA]', 
    '[ECHO]', '[FOXTROT]', '[GOLF]', '[HOTEL]', 
    '[INDIA]', '[JULIET]', '[KILO]', '[LIMA]', '[MIKE]'
]

def generate_embed_url(tmdb_id, tag):
    return f"https://example.com/embed/{tag}/{tmdb_id}" 

# --- Core Async Scraper Function (Simplified Launch) ---
# This function will now accept the browser instance from the handler.
async def scrape_embed_url_async(browser: ChromiumBrowser, tmdb_id, tag):
    result = {'tag': tag, 'status': 'not_found', 'urls': []}
    
    embed_url = generate_embed_url(tmdb_id, tag)
    
    try:
        # Use a new context and page for isolation, but reuse the same browser
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
        
        # Cleanup the context/page, but keep the main browser open
        await context.close()

    except Exception as e:
        result['status'] = 'error'
        result['message'] = f"Playwright Error on {tag}: {e}"
        
    return result

# --- Asynchronous Handler Function ---
async def async_handler(tmdb_id):
    playwright_instance = await async_playwright().start()
    browser = None
    try:
        # 1. Launch the browser ONCE for the entire function execution
        browser = await playwright_instance.chromium.launch(
            headless=True,
            args=['--no-sandbox', '--disable-setuid-sandbox', '--single-process']
        )
        
        # 2. Create the tasks, passing the shared browser instance
        tasks = [
            scrape_embed_url_async(browser, tmdb_id, tag)
            for tag in TAGS
        ]

        # 3. Run all tasks concurrently
        return await asyncio.gather(*tasks)
    
    finally:
        # 4. Ensure the browser and Playwright instance are closed cleanly
        if browser:
            await browser.close()
        await playwright_instance.stop()

# --- Flask Endpoint (MODIFIED) ---
@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
@app.route('/api', defaults={'path': ''})
@app.route('/api/<path:path>')
def handler(path):
    tmdb_id = request.args.get('id')
    
    if not tmdb_id:
        # This will now correctly return the base HTML due to vercel.json routes
        return "<h1>TMDB Scraper is running.</h1><p>Please use /api?id=[TMDB_ID_HERE] to start scraping.</p>"

    try:
        # Execute the entire concurrent process
        raw_results = asyncio.run(async_handler(tmdb_id))
        
        # ... (result aggregation remains the same) ...
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
        # Handle general errors gracefully
        return jsonify({
            'error': 'An internal server error occurred during scraping.',
            'details': str(e)
        }), 500

if __name__ == '__main__':
    app.run(debug=True)
