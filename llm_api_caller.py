import requests
import os
import sys
import json
import time

# OpenRouter API Configuration
API_KEY_ENV_VAR = "OPENROUTER_API_KEY"
MODEL_NAME = "openai/gpt-3.5-turbo" # You can change this to any model OpenRouter supports (e.g., 'anthropic/claude-3-haiku')
API_BASE_URL = "https://openrouter.ai/api/v1/chat/completions" # OpenRouter's universal endpoint


def _normalize_key(raw: str) -> str:
    """Remove whitespace, CR/LF so the key is sent exactly as intended."""
    if not raw:
        return ""
    return raw.replace("\r", "").replace("\n", "").strip()


def _load_api_key():
    """Load API key from OPENROUTER_API_KEY environment variable only."""
    return _normalize_key(os.environ.get(API_KEY_ENV_VAR) or "")


def call_llm(log_content):
    """
    Connects to the OpenRouter API to analyze the log content.
    Returns a dictionary with the summary and recommended action.
    """
    api_key = _load_api_key()
    if not api_key:
        print(
            f"Error: No API key found. Set {API_KEY_ENV_VAR} in your environment (e.g. export {API_KEY_ENV_VAR}=\"your-key\").",
            file=sys.stderr,
        )
        return None
    
    # Structured prompt engineering
    system_prompt = (
        "You are a concise, world-class DevOps SRE. Analyze the provided log trace. "
        "Your response MUST be a single JSON object. "
        "Choose an 'action' ONLY from the list: [RESTART_APACHE, CLEAR_TEMP_CACHE, ESCALATE]. "
        "DO NOT include any text outside the JSON object."
    )
    
    user_query = f"""
    Analyze the following critical system log trace. This log shows an anomaly:
    --- LOG TRACE START ---
    {log_content}
    --- LOG TRACE END ---
    
    1. SUMMARY: Provide a single sentence, high-level summary of the root cause.
    2. ACTION: Select the best action for immediate remediation.
    """

    # Request payload
    headers = {
        'Authorization': f'Bearer {api_key}', # OpenRouter uses the Authorization Bearer header
        'Content-Type': 'application/json'
    }
    
    # The JSON structure for the request body
    payload = {
        "model": MODEL_NAME, # Specify the model you want to use
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_query}
        ],
        # Structured output requires specific JSON output directives
        "response_format": {"type": "json_object"},
        "temperature": 0.0 # Use low temperature for reliable action selection
    }

    # API request with error handling
    response = None 
    for attempt in range(3):
        try:
            # We use API_BASE_URL directly here
            response = requests.post(API_BASE_URL, headers=headers, json=payload, timeout=30)
            
            # Check for success
            if response.status_code == 200:
                result = response.json()
                
                # The response structure is different (OpenAI style)
                json_text = result['choices'][0]['message']['content']
                return json.loads(json_text)
            
            # Handle API Errors (400, 401, 403, 429, 500, 503)
            if response.status_code in [400, 401, 403, 429, 500, 503]:
                error_detail = response.json().get('error', {}).get('message', 'No detail provided.')
                print(f"\n[API FAIL] HTTP {response.status_code}: {error_detail}", file=sys.stderr)
                if response.status_code in (401, 403) and "not found" in error_detail.lower():
                    print(f"  -> Get a valid key at https://openrouter.ai/keys and set export {API_KEY_ENV_VAR}=\"your-key\".", file=sys.stderr)

                if response.status_code in [401, 403]:
                    return None # Stop for authentication errors
                
                if attempt < 2:
                    wait_time = 2 ** attempt
                    time.sleep(wait_time)
                else:
                    return None
            
        except requests.exceptions.RequestException as e:
            print(f"\n[CONN FAIL] Cannot reach OpenRouter API server: {e}", file=sys.stderr)
            return None
        except Exception as e:
            # Catch Python exceptions that happen before or after the request
            print(f"\n[PYTHON FAIL] An unexpected error occurred: {e}", file=sys.stderr)
            return None
            
    return None


if __name__ == "__main__":
    if len(sys.argv) > 1:
        log_content = sys.argv[1]
        
        result = call_llm(log_content)
        
        if result:
            print(json.dumps(result))
        else:
            # Fallback for Bash: returns a known structure for Bash to parse cleanly
            print(json.dumps({"summary": "API ERROR: Check terminal for HTTP error.", "action": "ESCALATE"}))

    else:
        print("Error: No log content provided.", file=sys.stderr)
        sys.exit(1)