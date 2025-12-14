import concurrent.futures
import requests
from flask import Flask, request, jsonify
import sys
import json
import re # We need the regex module to search the response text

# --- Flask App Initialization ---
app = Flask(__name__) 

# --- Configuration: Full Embed URL Templates ---

# These are now the PRIMARY URLs we will request (not just Referers).
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

# Regex pattern to find .m3u8 links in the HTML or JavaScript source code
# This is a generic pattern that looks for any URL ending in .m3u8
M3U8_PATTERN = re.compile(r'(https?:\/\/[^\s]*?\.m3u8[^\s\'"]*)')


# --- Scraper Function (Synchronous, uses requests) ---

def scrape_embed_url(tmdb_id, tag):
    """
    Fetches the full embed URL and searches the response body (HTML/JS) 
    for the M3U8 link using regex.
    """
    
    # Construct the FULL embed URL
    embed_url = SERVER_TEMPLATES[tag].format(id=tmdb_id)
    
    # Define basic browser headers (Referer is now handled implicitly by requests following redirects)
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "DNT": "1" # Do Not Track header
    }
    
    found_urls = set()
    
    try:
        # We must use ALLOW_REDIRECTS=True to follow the chain of redirects that 
        # often occur when loading an embed URL (e.g., security checks, CDN hops).
        response = requests.get(embed_url, headers=headers, timeout=15, allow_redirects=True) 
        response.raise_for_status() 
        
        # --- Search the Final Response Text ---
        # The M3U8 URL might be embedded directly in the HTML or in a linked JavaScript file.
        # Since we cannot execute the JS, we rely on the link being visible in the source text.
        
        matches = M3U8_PATTERN.findall(response.text)
        
        if matches:
            for url in matches:
                # Basic cleanup, stripping quotes or trailing characters
                url = url.strip('"\'') 
                found_urls.add(url)
            
            if found_urls:
                return {"tag": tag, "status": "success", "urls": sorted(list(found_urls))}
        
        # If the page loads successfully but the link is not in the source code
        return {"tag": tag, "status": "not_found", "message": "Embed page loaded, but no M3U8 link found in source code."}
        
    except requests.exceptions.RequestException as e:
        # Catch network/connection errors
        return {"tag": tag, "status": "error", "message": f"Request Error: {type(e).__name__}: {str(e)}"}
    except Exception as e:
        # Catch any other unexpected errors
        return {"tag": tag, "status": "error", "message": f"Unexpected Error: {str(e)}"}

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
    
    # Execution logic remains the same
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        
        # We now use the scrape_embed_url function
        futures = [
            executor.submit(scrape_embed_url, tmdb_id, tag)
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
