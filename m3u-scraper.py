import concurrent.futures
import requests
from flask import Flask, request, jsonify
import sys
import json

# --- Flask App Initialization ---
app = Flask(__name__)

# --- Configuration for Direct API Calls ---

# 1. MOCKUP API BASE URL: This is the critical part that may need adjustment
# based on your network inspection. It's the endpoint that returns stream data.
API_BASE_URL = "https://player.vidify.top/api/source" 

# 2. Server Names: We only need the short server name for the API call
SERVER_API_NAMES = {
    "[ALPHA]": "adam",
    "[BRAVO]": "alok",
    "[CHARLIE]": "box", # The server name from the URL template was 'box'
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

# --- Fast Scraper Function (Synchronous, uses requests) ---

def get_m3u8_url_fast(tmdb_id, tag, server_name):
    """
    Attempts to fetch the M3U8 URL from a direct API call for a single server.
    """
    
    # MOCKUP: Construct the API request URL (adjust query parameters as needed)
    # The API might be expecting the TMDb ID and the server name.
    api_url = f"{API_BASE_URL}?id={tmdb_id}&server={server_name}"
    
    # Define headers to emulate a browser request and satisfy security checks
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        # Crucial: Pretend to be coming from the main player domain
        "Referer": "https://player.vidify.top/", 
        "X-Requested-With": "XMLHttpRequest" # Often required for API endpoints
    }
    
    found_urls = set()
    
    try:
        # Use a short timeout since this is a fast API call
        response = requests.get(api_url, headers=headers, timeout=10) 
        response.raise_for_status() # Raise an exception for bad status codes (4xx or 5xx)
        
        # --- Extract the M3U8 URL from the JSON Response ---
        
        # MOCKUP: Assuming the JSON response is structured like a video player source array
        data = response.json()
        
        # The API is assumed to return a JSON array under the key 'sources'
        if data.get('success') and data.get('sources'):
            for source in data['sources']:
                # The final M3U8 link is often stored under the key 'file'
                if source.get('file') and '.m3u8' in source['file']:
                    found_urls.add(source['file'])
            
            if found_urls:
                return {"tag": tag, "status": "success", "urls": sorted(list(found_urls))}
        
        # If the API succeeds but finds no M3U8 link in the response data
        return {"tag": tag, "status": "not_found", "message": "API succeeded, but no M3U8 source found in response."}
        
    except requests.exceptions.RequestException as e:
        # Catch network/connection errors
        return {"tag": tag, "status": "error", "message": f"Request Error: {str(e)}"}
