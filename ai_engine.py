import json
import requests
import time
from typing import Dict, Any

# --- Configuration ---
# API endpoint for the Gemini model
GEMINI_API_URL_TEMPLATE = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
MODEL_NAME = "gemini-2.5-flash-preview-05-20"
MAX_RETRIES = 5

def fetch_gemini_content(api_key: str, payload: Dict[str, Any]) -> str:
    """
    Handles API request to Gemini with exponential backoff for resilience.
    """
    if not api_key:
        return "❌ API Key required for AI analysis."

    api_url = GEMINI_API_URL_TEMPLATE.format(model=MODEL_NAME, api_key=api_key)
    
    for attempt in range(MAX_RETRIES):
        try:
            headers = {'Content-Type': 'application/json'}
            
            # FIX: Changed 'utf-s8' to the correct standard encoding 'utf-8'
            data = json.dumps(payload).encode('utf-8') 

            response = requests.post(api_url, headers=headers, data=data)
            response.raise_for_status() # Raises an HTTPError for bad responses (4xx or 5xx)

            result = response.json()
            candidate = result.get('candidates', [{}])[0]

            if candidate and candidate.get('content') and candidate['content'].get('parts'):
                return candidate['content']['parts'][0]['text']
            
            return f"⚠️ Model response incomplete: {json.dumps(result)}"

        except requests.exceptions.HTTPError as e:
            # Handle specific HTTP errors (e.g., 400 Bad Request, 429 Rate Limit)
            error_message = f"HTTP Error: {e.response.status_code} - {e.response.text}"
            if e.response.status_code == 429 and attempt < MAX_RETRIES - 1:
                # Rate limit, retry with backoff
                time.sleep(2 ** attempt)
                continue
            return f"❌ AI API Error: {error_message}"
        except Exception as e:
            return f"❌ An unexpected error occurred during the API call: {e}"

    return "❌ Failed to connect to Gemini API after multiple retries (Rate Limit or Connection Error)."

def get_ai_summary(api_key: str, metric_name: str, metric_data: str) -> str:
    """Generates a concise summary for a single metric."""
    system_prompt = (
        f"You are a Senior Agile Coach and AI Analyst. Analyze the following data for '{metric_name}'."
        f"Provide a concise, 3-4 sentence summary. Use emoji (✅, ⚠️, or ❌) at the start to indicate overall health. "
        f"Do not use markdown formatting (like bolding or lists)."
    )
    
    user_query = f"Data for {metric_name}: \n\n{metric_data}"

    payload = {
        "contents": [{"parts": [{"text": user_query}]}],
        "systemInstruction": {"parts": [{"text": system_prompt}]},
    }
    
    return fetch_gemini_content(api_key, payload)


def get_executive_summary(api_key: str, metrics_data: Dict[str, Any]) -> str:
    """Generates an executive-level summary synthesizing all metrics."""
    system_prompt = (
        "You are an Executive AI Analyst for a large enterprise. Your task is to generate a single, highly "
        "synthesized paragraph (max 5 sentences) for senior leadership. Evaluate the program's health "
        "across all metrics provided below. Start your summary with a single emoji (🔴 for Critical, "
        "🟠 for Warning, or 🟢 for Healthy). Focus on synthesizing key trends, risks (from RAID), "
        "and overall velocity/quality."
    )
    
    data_points = "\n".join([f"- {k}: {v}" for k, v in metrics_data.items() if k not in ["raw_jira_summary", "raw_defects_summary"]])
    
    user_query = f"Synthesize the health status based on the following metric data:\n\n{data_points}"

    payload = {
        "contents": [{"parts": [{"text": user_query}]}],
        "systemInstruction": {"parts": [{"text": system_prompt}]},
    }
    
    return fetch_gemini_content(api_key, payload)
