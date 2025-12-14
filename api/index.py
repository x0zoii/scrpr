import asyncio
import json
import os

from flask import Flask, request, jsonify

# IMPORTANT: We use playwright_python_serverless for the compatible binary path
from playwright.async_api import async_playwright
import playwright_python_serverless

# Remove the manual LD_LIBRARY_PATH setting as the new package handles it internally
# os.environ['LD_LIBRARY_PATH'] = os.path.join(os.getcwd(), '.playwright', 'chromium') + ':' + os.environ.get('LD_LIBRARY_PATH', '')

app = Flask(__name__)

# --- Configuration for Scraping ---
TAGS = [
    '[ALPHA]', '[BRAVO]', '[CHARLIE]', '[DELTA]', 
    '[ECHO]', '[FOXTROT]', '[GOLF]', '[HOTEL]', 
    '[INDIA]', '[JULIET]', '[KILO]', '[LIMA]', '[MIKE]'
]

def generate_embed_url(tmdb_id, tag):
    # This is where you will add your actual URL generation logic later
    return f"https://example.com/embed/{tag}/{tmdb_id}" 

# --- Core Async Scraper Function (Optimized for single browser reuse) ---
# This function accepts the shared browser instance.
async def scrape_embed_url_async(browser, tmdb_id, tag):
    result = {'tag': tag, 'status': 'not_found', 'urls': []}
    
    embed_url = generate_embed_url(tmdb_id, tag)
    
    try:
        # Use a new context and page for isolation, reusing the main browser
        context = await browser.new_context()
        page = await context.new_page()

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
        
        await context.close()

    except Exception as e:
        result['status'] = 'error'
        result['message'] = f"Playwright Error on {tag}: {e}"
        
    return result

# --- Asynchronous Handler Function (Launches browser once) ---
async def async_handler(tmdb_id):
    playwright_instance = await async_playwright().start()
    browser = None
    try:
        # CRITICAL: Launch the browser using the Lambda-compatible binary and args
        browser = await playwright_instance.chromium.launch(
            executable_path=playwright_python_serverless.get_executable_path(), # Gets the correct pre-compiled path
            headless=True,
            args=playwright_python_serverless.get_chromium_args() # Uses the minimal required args for Lambda
        )
        
        # Create the tasks, passing the shared browser instance
        tasks = [
            scrape_embed_url_async(browser, tmdb_id, tag)
            for tag in TAGS
        ]

        # Run all tasks concurrently in a single event loop
        return await asyncio.gather(*tasks)
    
    finally:
        # Ensure the browser and Playwright instance are closed cleanly
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
        # This will be returned for requests hitting the root path
        return "<h1>TMDB Scraper is running.</h1><p>Please use /api?id=[TMDB_ID_HERE] to start scraping.</p>"

    try:
        # Execute the entire concurrent process
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
        # Handle general errors gracefully
        return jsonify({
            'error': 'An internal server error occurred during scraping.',
            'details': str(e)
        }), 500

if __name__ == '__main__':
    app.run(debug=True)
