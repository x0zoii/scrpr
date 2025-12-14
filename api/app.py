import concurrent.futures
import requests
from flask import Flask, request, jsonify
import sys
import json

# --- Flask App Initialization ---
app = Flask(__name__) 

# --- Configuration for Direct API Calls ---

# 1. API BASE URL: This is the endpoint that the web player uses to request the stream source.
API_BASE_URL = "https://player.vidify.top/api/source" 

# 2. Server Names: Mapped from your SERVER_TEMPLATES (using the 'server=name' parameter)
SERVER_API_NAMES = {
    "[ALPHA]": "adam",
    "[BRAVO]": "alok",
    "[CHARLIE]": "box",
    "[DELTA]": "cypher",
    "[ECHO]": "haxo",
    "[FOXTROT]": "lux",
    "[GOLF]": "mbox",
    "[HOTEL]": "meta",
    "[INDIA]": "nitro",
    "[JULIET]": "prime",
    "[KILO]": "veasy",
    "[LIMA]": "vplus",
    "[MIKE]": "yoru",
}

# 3. FULL EMBED URL TEMPLATES (NEW): Used to set the correct Referer header
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


# --- Fast Scraper Function (Synchronous, uses requests) ---

def get_m3u8_url_fast(tmdb_id, tag, server_name):
    """
    Attempts to fetch the M3U8 URL from a direct API call for a single server.
    """
    
    # Construct the API request URL
    api_url = f"{API_BASE_URL}?id={tmdb_id}&server={server_name}"
    
    # Construct the DYNAMIC Referer URL from the template
    referer_url = SERVER_TEMPLATES[tag].format(id=tmdb_id)
    
    # Define ENHANCED headers
    headers = {
        # Standard User-Agent for a modern Chrome browser
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        
        # CRUCIAL FIX: Use the full embed URL as the Referer
        "Referer": referer_url, 
        
        # Explicitly request and accept JSON
        "Accept": "application/json, text/plain, */*",
        "Accept-Encoding": "gzip, deflate, br", 
        "Origin": "https://player.vidify.top", 
        "X-Requested-With": "XMLHttpRequest" 
    }
    
    found_urls = set()
    
    try:
        response = requests.get(api_url, headers=headers, timeout=10) 
        response.raise_for_status() 
        
        # --- Extract the M3U8 URL from the JSON Response ---
        data = response.json() 
        
        if data.get('success') and data.get('sources'):
            for source in data['sources']:
                if source.get('file') and '.m3u8' in source['file']:
                    found_urls.add(source['file'])
            
            if found_urls:
                return {"tag": tag, "status": "success", "urls": sorted(list(found_urls))}
        
        return {"tag": tag, "status": "not_found", "message": "API succeeded, but no M3U8 source found in response."}
        
    except requests.exceptions.RequestException as e:
        return {"tag": tag, "status": "error", "message": f"Request Error: {type(e).__name__}: {str(e)}"}
    except json.JSONDecodeError:
        # Include the start of the response text to help debug blocked requests
        return {"tag": tag, "status": "error", "message": f"API response was not valid JSON. Response Text Start: {response.text[:50]}"}
    except Exception as e:
        return {"tag": tag, "status": "error", "message": f"Unexpected Error: {str(e)}"}

# --- Flask Web Endpoint ---

@app.route('/', methods=['GET']) 
def scrape_endpoint():
    """
    API endpoint that accepts a TMDb ID and executes the concurrent fast scraping.
    """
    tmdb_id = request.args.get('id')
    
    if not tmdb_id or not tmdb_id.isdigit():
        return jsonify({"error": "Invalid or missing 'id' parameter."}), 400

    final_results = {}
    total_urls = 0
    max_workers = len(SERVER_API_NAMES)
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        
        futures = [
            executor.submit(get_m3u8_url_fast, tmdb_id, tag, server_name)
            for tag, server_name in SERVER_API_NAMES.items()
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
        "total_servers_checked": len(SERVER_API_NAMES),
        "total_urls_found": total_urls,
        "results": final_results
    })
