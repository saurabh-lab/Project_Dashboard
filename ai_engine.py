import os
import json
import time
from urllib.request import urlopen, Request
import numpy as np

# --- Configuration ---
# NOTE: Removed global API_KEY definition. It must be passed in the function calls.
MODEL_NAME = "gemini-2.5-flash-preview-05-20"
MAX_RETRIES = 5

def fetch_gemini_content(api_key, payload, retries=0):
    """
    Handles the synchronous API call with exponential backoff.
    Requires the api_key to be passed as an argument.
    """
    if not api_key:
        return "⚠️ Gemini API Key not provided. Cannot run AI analysis."
    
    API_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL_NAME}:generateContent?key={api_key}"
    
    headers = {'Content-Type': 'application/json'}
    data = json.dumps(payload).encode('utf-s8')
    
    try:
        req = Request(API_URL, data=data, headers=headers, method='POST')
        
        with urlopen(req, timeout=30) as response:
            result = json.loads(response.read().decode())
            text = result.get('candidates', [{}])[0].get('content', {}).get('parts', [{}])[0].get('text', 
                                                                                                  "AI summary failed to load.")
            return text
            
    except Exception as e:
        if retries < MAX_RETRIES:
            delay = 2 ** retries + np.random.uniform(0, 1) # Exponential backoff + jitter
            time.sleep(delay)
            # Recursive call, passing the key
            return fetch_gemini_content(api_key, payload, retries + 1)
        else:
            # Provide error context suitable for the UI
            return f"❌ AI call failed after {MAX_RETRIES} retries. Check API key validity and console for error details: {e}"

def get_ai_summary(api_key, metric_name, data_summary):
    """Generates a concise AI summary for a single metric, requiring the api_key."""
    if not api_key:
        return "Awaiting API Key..."
    
    system_prompt = (
        f"You are a technical Program Analyst expert. Your task is to analyze the provided data for the '{metric_name}' metric. "
        "Provide a concise, professional summary of exactly 3-4 sentences. "
        "Highlight the key trend, potential cause, and primary recommendation."
    )
    user_query = f"Analyze the following programmatic data for {metric_name}:\n\n{data_summary}"
    
    payload = {
        "contents": [{"parts": [{"text": user_query}]}],
        "systemInstruction": {"parts": [{"text": system_prompt}]},
    }
    
    # Pass the key to the fetch function
    return fetch_gemini_content(api_key, payload)

def get_executive_summary(api_key, all_metrics_data):
    """Generates the holistic Executive Summary, requiring the api_key."""
    if not api_key:
        return "Awaiting API Key..."

    system_prompt = (
        "You are a C-level Executive Program Director. Your task is to synthesize all provided data into a single, high-impact Executive Summary (max 100 words). "
        "Start with a high-level assessment using a single primary emoji (✅ for green, ⚠️ for yellow/caution, or ❌ for red/critical). "
        "Focus on the biggest risk and the most positive trend. This summary must be suitable for a leadership PPT slide."
    )
    
    # Prepare a human-readable summary of the data for the LLM
    # Use .get with a default message in case data is incomplete
    data_for_llm = f"""
    --- VELOCITY & COMPLETION ---
    {all_metrics_data.get('completion', 'Data not available.')}

    --- CAPACITY (Recent) ---
    {all_metrics_data.get('capacity', 'Data not available.')}

    --- DEFECT DENSITY & OPEN STAGE ---
    Open Defects by Stage: {all_metrics_data.get('stage', 'Data not available.')}
    Density Data: {all_metrics_data.get('density', 'Data not available.')}

    --- RAID STATUS (OPEN ITEMS) ---
    {all_metrics_data.get('raid', 'Data not available.')}

    --- RAW DEFECTS CONTEXT ---
    {all_metrics_data.get('raw_defects_summary', 'Data not available.')}
    """
    
    user_query = f"Synthesize a leadership brief from this combined program health data:\n\n{data_for_llm}"
    
    payload = {
        "contents": [{"parts": [{"text": user_query}]}],
        "systemInstruction": {"parts": [{"text": system_prompt}]},
    }
    
    # Pass the key to the fetch function
    return fetch_gemini_content(api_key, payload)
