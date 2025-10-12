import json
import requests
import time
from typing import Dict, Any, List, Optional
from tools_registry import TOOL_REGISTRY, get_all_tool_specs
import pandas as pd # Needed for type hinting in tool execution


# --- Configuration ---
GEMINI_API_URL_TEMPLATE = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
MODEL_NAME = "gemini-2.5-flash-preview-05-20" # Using the specific model ID for 1.5 Flash (supports function calling)
MAX_RETRIES = 5

# --- Core API Interaction ---
def _fetch_gemini_response(api_key: str, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Handles API request to Gemini with exponential backoff for resilience.
    Returns the full JSON response, or None on critical error.
    """
    if not api_key:
        print("❌ API Key required for AI analysis.")
        return {"error": "API Key required for AI analysis."}

    api_url = GEMINI_API_URL_TEMPLATE.format(model=MODEL_NAME, api_key=api_key)
    
    for attempt in range(MAX_RETRIES):
        try:
            headers = {'Content-Type': 'application/json'}
            data = json.dumps(payload).encode('utf-8') 

            response = requests.post(api_url, headers=headers, data=data)
            response.raise_for_status() # Raises an HTTPError for bad responses (4xx or 5xx)

            return response.json()

        except requests.exceptions.HTTPError as e:
            error_message = f"HTTP Error: {e.response.status_code} - {e.response.text}"
            print(f"Attempt {attempt + 1}: {error_message}")
            if e.response.status_code in [429, 500, 503] and attempt < MAX_RETRIES - 1:
                time.sleep(2 ** attempt) # Exponential backoff
                continue
            return {"error": f"AI API Error: {error_message}"}
        except Exception as e:
            print(f"❌ An unexpected error occurred during the API call: {e}")
            return {"error": f"An unexpected error occurred during the API call: {e}"}

    return {"error": "Failed to connect to Gemini API after multiple retries (Rate Limit or Connection Error)."}

# --- Tool Execution ---
def _execute_tool(tool_name: str, args: Dict[str, Any], preprocessed_dataframes: Dict[str, pd.DataFrame]) -> Any:
    """
    Executes a specific tool function from the TOOL_REGISTRY with the provided arguments.
    It passes the preprocessed DataFrames as required arguments.
    """
    if tool_name not in TOOL_REGISTRY:
        return f"Error: Tool '{tool_name}' not found in registry."

    tool = TOOL_REGISTRY[tool_name]
    
    # Prepare arguments, injecting preprocessed dataframes as needed
    call_args = {}
    for param_name, param_spec in tool.parameters.items():
        if param_name in preprocessed_dataframes:
            # Inject the preprocessed DataFrame directly
            call_args[param_name] = preprocessed_dataframes[param_name]
        elif param_name in args:
            # Use arguments provided by the LLM
            call_args[param_name] = args[param_name]
        elif "default" in param_spec:
            # Use default value if specified in tool schema
            call_args[param_name] = param_spec["default"]
        # If a parameter is required by the tool function but not provided by LLM nor in preprocessed_dataframes,
        # and has no default, it will raise an error later during function call.
        # This is where strict schema validation can be added.
    
    try:
        print(f"📞 Calling tool: {tool_name} with args: {', '.join(call_args.keys())}") # Log which args are passed
        result = tool.func(**call_args)
        # Convert pandas DataFrames within results to list of dicts for JSON serialization if any
        if isinstance(result, pd.DataFrame):
            return result.to_dict('records')
        return result
    except Exception as e:
        import traceback
        traceback.print_exc() # Print full traceback for debugging tool execution
        return f"Error executing tool '{tool_name}': {e}"

# --- Agent Orchestration ---
def chat_with_agent(
    api_key: str, 
    user_query: str, 
    preprocessed_dataframes: Dict[str, pd.DataFrame], 
    history: Optional[List[Dict[str, Any]]] = None
) -> Dict[str, Any]:
    """
    Orchestrates a conversation with the Gemini model, including tool calling.
    Manages the conversational history and processes tool outputs.
    """
    if history is None:
        history = []

    system_instruction_text = (
        "You are an expert AI Program Manager and Data Analyst. "
        "Your goal is to provide comprehensive and actionable insights "
        "based on the provided program health data. "
        "You can use the available tools to fetch specific metrics. "
        "After gathering information, synthesize the results into a clear, "
        "executive-level summary, suitable for leadership. "
        "Always aim to provide numerical evidence and trends where possible. "
        "If a specific metric is requested, provide its data and a summary. "
        "If asked for an overall health assessment, use multiple tools to gather data first."
    )
    
    # Add the user's initial query to the history if it's not already there (prevents duplicates on retry)
    if not history or history[-1].get("parts")[0].get("text") != user_query:
        history.append({"role": "user", "parts": [{"text": user_query}]})

    # Prepare tool specifications for the LLM
    all_tool_specs = get_all_tool_specs()
    
    # Main conversational loop
    for turn_count in range(5): # Limit turns to prevent infinite loops during tool calling
        print(f"--- Agent Turn {turn_count + 1} ---")
        print(f"Current History length: {len(history)}")

        payload = {
            "contents": history,
            "systemInstruction": {"parts": [{"text": system_instruction_text}]},
            "tools": {"function_declarations": all_tool_specs}, # THIS IS THE CRITICAL CHANGE
            "tool_config": {"function_calling_config": {"mode": "AUTO"}} # This remains at top level
        }
        
        gemini_response = _fetch_gemini_response(api_key, payload)

        if "error" in gemini_response:
            print(f"Gemini API Error: {gemini_response['error']}")
            return {"error": gemini_response["error"], "history": history}

        candidate = gemini_response.get('candidates', [{}])[0]
        if not candidate:
            print("Model did not return a candidate response (empty).")
            # If no candidate, it's likely an error or unexpected model behavior
            return {"response": "I couldn't generate a clear response for your query (empty candidate).", "history": history}

        model_content = candidate.get('content', {})
        parts = model_content.get('parts', [])
        
        # Check if the model decided to call a function
        function_calls_found = False
        for part in parts:
            if 'functionCall' in part:
                function_calls_found = True
                function_call = part['functionCall']
                tool_name = function_call['name']
                tool_args = function_call.get('args', {})

                print(f"🤖 Agent requested tool: {tool_name} with args: {tool_args}")
                tool_output = _execute_tool(tool_name, tool_args, preprocessed_dataframes)
                print(f"📊 Tool '{tool_name}' output (first 500 chars): {str(tool_output)[:500]}...")

                # Add tool output to history
                history.append({
                    "role": "function",
                    "parts": [{"functionResponse": {"name": tool_name, "response": {"result": tool_output}}}]
                })
        
        if function_calls_found:
            # If function calls were made, continue the loop for the model to process the tool output
            continue 
        else:
            # If no function calls, check for a text response
            text_parts = [part['text'] for part in parts if 'text' in part]
            if text_parts:
                response_text = " ".join(text_parts)
                history.append({"role": "model", "parts": [{"text": response_text}]})
                return {"response": response_text, "history": history}
            else:
                # This could happen if the model returned nothing or something unexpected
                print("Model returned no function calls and no text.")
                return {"response": "I couldn't generate a clear response for your query (empty content).", "history": history}

    return {"response": "The agent reached its maximum turn limit without providing a final answer.", "history": history}


# --- Deprecated/Legacy AI Analysis Functions (will be replaced by chat_with_agent for general use) ---
# Keeping them for now, but they won't be called directly by the new orchestrator flow.
def get_ai_summary(api_key: str, metric_name: str, metric_data: str) -> str:
    """Generates a concise summary for a single metric in a bulleted format."""
    system_prompt = (
        f"You are a Senior Agile Coach and AI Analyst. Analyze the following data for '{metric_name}'."
        f"Provide a summary consisting of exactly 4 to 5 concise bullet points."
        f"Start the summary with a single emoji (✅ for Healthy, ⚠️ for Warning, or ❌ for Critical) on the first line."
        f"Use simple markdown for the bullets but ensure each bullet is very short and focused."
    )
    
    user_query = f"Data for {metric_name}: \n\n{metric_data}"

    payload = {
        "contents": [{"parts": [{"text": user_query}]}],
        "systemInstruction": {"parts": [{"text": system_prompt}]},
    }
    
    result = _fetch_gemini_response(api_key, payload)
    return result.get('candidates', [{}])[0].get('content', {}).get('parts', [{}])[0].get('text', '') if result and 'error' not in result else result.get('error', 'AI Summary Error')


def get_executive_summary(api_key: str, metrics_data: Dict[str, Any]) -> str:
    """
    Generates an executive-level summary synthesizing all metrics into categorized sections.
    """
    system_prompt = (
        "You are an Executive AI Analyst for a large enterprise. Your task is to generate a highly "
        "synthesized report for senior leadership, organized into three mandatory Markdown headings: "
        "'## Overall Health & Status', '## Key Risks and Impediments', and '## Executive Recommendations'. "
        "For each section, provide 2-4 concise bullet points."
        "Start your response with a single emoji (🔴 for Critical, 🟠 for Warning, or 🟢 for Healthy) "
        "on the first line, followed by the first heading."
        "Focus on synthesizing key trends, high-impact risks (from RAID), and critical quality/velocity issues."
    )
    
    # Filter out raw summary data which is too verbose for the executive prompt
    data_points = "\n".join([f"- {k}: {v}" for k, v in metrics_data.items() if k not in ["raw_jira_summary", "raw_defects_summary"]])
    
    user_query = f"Synthesize the health status based on the following metric data:\n\n{data_points}"

    payload = {
        "contents": [{"parts": [{"text": user_query}]}],
        "systemInstruction": {"parts": [{"text": system_prompt}]},
    }
    
    result = _fetch_gemini_response(api_key, payload)
    return result.get('candidates', [{}])[0].get('content', {}).get('parts', [{}])[0].get('text', '') if result and 'error' not in result else result.get('error', 'AI Summary Error')
