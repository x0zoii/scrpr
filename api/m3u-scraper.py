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
    except json.JSONDecodeError:
        # Catch non-JSON responses
        return {"tag": tag, "status": "error", "message": "API response was not valid JSON."}
    except Exception as e:
        # Catch any other unexpected errors
        return {"tag": tag, "status": "error", "message": f"Unexpected Error: {str(e)}"}

# --- Flask Web Endpoint ---

@app.route('/scrape', methods=['GET'])
def scrape_endpoint():
    """
    API endpoint that accepts a TMDb ID and executes the concurrent fast scraping.
    """
    tmdb_id = request.args.get('id')
    
    if not tmdb_id or not tmdb_id.isdigit():
        return jsonify({"error": "Invalid or missing 'id' parameter."}), 400

    # 1. Prepare tasks for concurrency
    tasks_to_run = []
    
    for tag, server_name in SERVER_API_NAMES.items():
        # Prepare the arguments for the get_m3u8_url_fast function
        tasks_to_run.append((tmdb_id, tag, server_name))
        
    # 2. Execute all tasks concurrently using ThreadPoolExecutor
    final_results = {}
    total_urls = 0
    
    # Use a thread pool size equal to the number of servers for maximum concurrency
    max_workers = len(SERVER_API_NAMES)
    
    # 
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Map the function and its arguments, and get the results as they complete
        # executor.map is often cleaner than as_completed for simple iteration
        
        # Create a list of futures to maintain the order of results
        futures = [
            executor.submit(get_m3u8_url_fast, tmdb_id, tag, server_name)
            for tag, server_name in SERVER_API_NAMES.items()
        ]

        # Process results as they complete
        for future in concurrent.futures.as_completed(futures):
            result = future.result()
            tag = result['tag']
            
            if result['status'] == 'success':
                urls_list = result['urls']
                final_results[tag] = {"status": "success", "urls": urls_list}
                total_urls += len(urls_list)
            else:
                final_results[tag] = result
    
    # 3. Return the final JSON response
    return jsonify({
        "tmdb_id": tmdb_id,
        "total_servers_checked": len(SERVER_API_NAMES),
        "total_urls_found": total_urls,
        "results": final_results
    })

# --- Entry Point ---

if __name__ == '__main__':
    # Run the Flask app
    print("\nStarting Fast API web server...")
    # This server is now highly efficient and ready for Vercel/Netlify deployment
    app.run(host='0.0.0.0', port=8080)
