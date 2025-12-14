import asyncio
import json
import os

from flask import Flask, request, jsonify

# IMPORTANT: We use playwright_aws_lambda to get the path
from playwright.async_api import async_playwright
# The lambda package provides the necessary path for the executable
import playwright_aws_lambda

app = Flask(__name__)

# --- Configuration for Scraping ---
TAGS = [
    '[ALPHA]', '[BRAVO]', '[CHARLIE]', '[DELTA]', 
    '[ECHO]', '[FOXTROT]', '[GOLF]', '[HOTEL]', 
    '[INDIA]', '[JULIET]', '[KILO]', '[LIMA]', '[MIKE]'
]

def generate_embed_url(tmdb_id, tag):
    return f"https://example.com/embed/{tag}/{tmdb_id}" 

# --- Core Async Scraper Function (Modified for Lambda Binary) ---
# This function will now accept the browser instance from the handler.
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

# --- Asynchronous Handler Function ---
async def async_handler(tmdb_id):
    playwright_instance = await async_playwright().start()
    browser = None
    try:
        # --- CRITICAL CHANGE: Use the Lambda-compatible executable path ---
        browser = await playwright_instance.chromium.launch(
            executable_path=playwright_aws_lambda.get_browser_executable_path(), # Gets the correct pre-compiled path
            headless=True,
            args=playwright_aws_lambda.chromium_args # Uses the minimal required args for Lambda
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

# --- Flask Endpoint (Unchanged) ---
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
        return jsonify({
            'error': 'An internal server error occurred during scraping.',
            'details': str(e)
        }), 500

if __name__ == '__main__':
    app.run(debug=True)
