import json
import re
import httpx
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import time
import asyncio
from duckduckgo_search import DDGS

import os
from dotenv import load_dotenv
from fastapi import HTTPException
from zoneinfo import ZoneInfo
from datetime import datetime

try:
    from backend.llm_client import ChatMessage, ChatRequest, llm_client
except ImportError:
    from llm_client import ChatMessage, ChatRequest, llm_client

load_dotenv()

SYSTEM_PROMPT = """
You are Smartbridge AI Agent, an intelligent research and task management assistant.
Give direct and helpful answers. Do NOT use a THINKING block.
You can execute exactly ONE tool call if you need external information to answer. If a tool fails, give a short, honest answer immediately without retrying.
Do NOT create tasks unless the user says 'create', 'assign', 'make task', or explicitly asks to assign something to someone. If they do not explicitly ask for a task, DO NOT create one, just answer normally.

Available Tools:
- `get_current_time`: Returns the current time and date in IST (Asia/Kolkata). Use this first for ANY query about "time", "date", "today", or "now", OR ANY relative time requirement (e.g. "this month"). Example:
**Action:**
```json
{"tool": "get_current_time"}
```
- `web_search`: Searches the internet for real-time information. Input MUST be a JSON object with a single `query` string parameter. For latest news or current events, use this tool. If it fails, give an honest short answer and suggest checking Google or NDTV. Example:
**Action:**
```json
{"tool": "web_search", "query": "latest AI news in India"}
```

CRITICAL: If the user DOES explicitly ask to 'create' or 'assign' a task, you MUST append a JSON block at the VERY END of your final message in this EXACT format:
```json
{"intent": "create_task", "title": "Task title", "assignee": "Name", "due_date": "YYYY-MM-DD", "status": "Pending"}
```
(due_date must be YYYY-MM-DD or null. status must be Pending, In Progress, or Completed).
This JSON block is REQUIRED for the system to actually create the task!

IMPORTANT FORMATTING RULES:
1. If you NEED external information, use this format:
**Action:** [the tool JSON block]
(Do NOT add any conversational text before or after the Action block. Stop immediately after outputting the JSON).

2. When you provide your final answer to the user, you MUST prefix it with:
**Output:**
(Do NOT output an Action if you are giving the final answer).

*** SPECIAL DIRECTORY STRUCTURE OVERRIDE ***
If the user specifically asks for the "structure", "tree", "directories", or "project structure" of a repository:
1. Confirm the repository name with the user (or use conversational context).
2. DO NOT list all repositories.
3. Use your GitHub API tools to fetch the repository tree (recursive=True if available).
4. Output ONLY a cleanly formatted ASCII tree like the example below.
5. Truncate outputs if the tree exceeds 100 lines (use "└── ...").
6. Provide absolutely NO extra conversational text, greetings, or file explanations.

Example Output format:
repository-name/
├── src/
│   ├── index.ts
│   └── utils/
│       └── helpers.ts
└── README.md
"""

# ChatMessage and ChatRequest moved to llm_client.py

def run_web_search(query: str) -> str:
    """Run a DuckDuckGo web search and return the top 5 results as text."""
    print(f"[Tool] Executing web_search for: {query}")
    # Improve query automatically
    enhanced_query = query
    if not any(word in query.lower() for word in ["today", "latest", "current"]):
        enhanced_query = f"{query} today latest current"
        
    try:
        results = DDGS().text(enhanced_query, max_results=3)
        if not results:
            return "Observation: Couldn't find current info — try checking Google/NDTV."
        
        obs = "Observation:\n"
        for i, res in enumerate(results):
            obs += f"{i+1}. {res.get('title')}\n   {res.get('body')}\n   Link: {res.get('href')}\n\n"
        return obs
    except Exception as e:
        print(f"[Tool Error] web_search failed: {e}")
        return "Observation: Couldn't find current info — try checking Google/NDTV."

def get_current_time() -> str:
    """Return the current time and date in IST."""
    try:
        ist = ZoneInfo("Asia/Kolkata")
        now = datetime.now(ist)
        formatted = now.strftime("%B %d, %Y %I:%M %p IST")
        print(f"[Tool] Executing get_current_time: {formatted}")
        return f"Observation: {formatted}"
    except Exception as e:
        print(f"[Tool Error] get_current_time failed: {e}")
        return f"Observation: Failed to get time: {str(e)}"

async def call_groq_api(request: ChatRequest, system_prompt: Optional[str] = None) -> str:
    # We keep the name 'call_groq_api' here to not break any external imports routing here, 
    # but it now uses the Universal LLM Adapter
    max_steps = 2
    current_step = 0
    full_response_text = ""
    effective_system_prompt = system_prompt or SYSTEM_PROMPT
    
    while current_step < max_steps:
        current_step += 1
        
        try:
            response = await llm_client.chat_completion(
                request=request, 
                system_prompt=effective_system_prompt, 
                temperature=0.2, 
                max_tokens=8192
            )
            data = response.json()
            assistant_message = data["choices"][0]["message"]["content"]
            
            # Append what the assistant just said to the UI output buffer
            if current_step > 1:
                full_response_text += "\n\n"
                
            # Format the assistant message to strip out internal code blocks if they are JUST Actions 
            # (but keep them if they are final code)
            # Actually, let's keep all text so the user sees the reasoning
            full_response_text += assistant_message
            
            # Check if assistant wants to take an action
            if "**Action:**" in assistant_message:
                request.messages.append(ChatMessage(role="assistant", content=assistant_message))
                
                # Try to extract JSON from the action
                action_json_str = ""
                try:
                    # Find code block after Action:
                    action_split = assistant_message.split("**Action:**")[1]
                    if "```json" in action_split:
                        action_json_str = action_split.split("```json")[1].split("```")[0].strip()
                    elif "```" in action_split:
                        action_json_str = action_split.split("```")[1].split("```")[0].strip()
                    else:
                        # Try to find raw JSON
                        start_idx = action_split.find("{")
                        end_idx = action_split.rfind("}") + 1
                        if start_idx != -1 and end_idx != -1:
                            action_json_str = action_split[start_idx:end_idx]
                    
                    action_data = json.loads(action_json_str)
                    tool_name = action_data.get("tool")
                    tool_executed = False
                    
                    if tool_name == "web_search":
                        query = action_data.get("query", "")
                        observation = run_web_search(query)
                        tool_executed = True
                    elif tool_name == "get_current_time":
                        observation = get_current_time()
                        tool_executed = True
                    else:
                        observation = f"Observation: Unknown tool '{tool_name}'"
                        
                except Exception as e:
                    print(f"Failed to parse or execute action: {e}")
                    observation = "Observation: Failed to parse action JSON or execute tool. Ensure you output valid JSON in the Action block."
                    tool_executed = False
                
                # Add observation to messages and loop again to let LLM process it
                if tool_executed:
                    observation_msg = f"**Observation:**\n{observation}\n\nCRITICAL: You have used your 1 allowed tool call. You MUST provide your final direct answer NOW. Do NOT output any more Actions."
                else:
                    observation_msg = f"**Observation:**\n{observation}\n\nCRITICAL: Action block failed parsing. Please correct your JSON format and output the **Action:** block again correctly."
                request.messages.append(ChatMessage(role="user", content=observation_msg))
                full_response_text += f"\n\n**Observation:**\n{observation}"
                continue # Let LLM think again
            
            # Check if intent is in the JSON for tasks
            if '"intent": "create_task"' in assistant_message and "```json" not in assistant_message:
                 # This usually means LLM output raw json instead of code block for intent. We enforce it in system prompt but fix here
                 pass
                 
            # No action requested, we are done
            # Strip internal formatting before returning to the user
            clean_reply = full_response_text
            # Remove Action + Observation blocks that should not be shown
            clean_reply = re.sub(r'\*\*Action:\*\*.*?(?=\*\*Output:|\Z)', '', clean_reply, flags=re.DOTALL | re.IGNORECASE).strip()
            clean_reply = re.sub(r'\*\*Observation:\*\*.*?(?=\*\*Output:|\Z)', '', clean_reply, flags=re.DOTALL | re.IGNORECASE).strip()
            # Strip the **Output:** prefix
            clean_reply = re.sub(r'\*\*Output:\*\*\s*', '', clean_reply, flags=re.IGNORECASE).strip()
            words = clean_reply.split()
            if len(words) > 8000:
                return " ".join(words[:8000]) + "... (very long — truncated)"
            return clean_reply
            
        except httpx.HTTPStatusError as e:
            print(f"[{llm_client.provider.upper()} API HTTP Error]: {e.response.status_code} - {e.response.text}")
            if e.response.status_code == 429:
                raise HTTPException(status_code=429, detail=f"{llm_client.provider.upper()} is busy (rate limit). Wait 60 seconds and try again.")
            elif e.response.status_code == 404:
                return "The selected model is not available. Please try a different model."
            elif e.response.status_code == 400:
                return "The request could not be processed. The selected model may not support this format."
            return f"I'm sorry, I encountered an API error (HTTP {e.response.status_code})."
        except httpx.TimeoutException:
            return "The request timed out. Please try again."
        except Exception as e:
            print(f"[{llm_client.provider.upper()} API Error]: {e}")
            return f"I'm sorry, I encountered an unexpected error. Please check your API Key and provider settings."
    
    # If we exit loop due to max_steps
    full_response_text += "\n\n*(Stopped after reaching maximum reasoning steps)*"
    words = full_response_text.split()
    if len(words) > 8000:
        return " ".join(words[:8000]) + "... (very long — truncated)"
    return full_response_text

# Friendly names with parameter counts
FRIENDLY_NAMES = {
    "llama3-70b-8192": "Llama 3 70B – 70B",
    "llama3-8b-8192": "Llama 3 8B – 8B",
    "llama-3.1-8b-instant": "Llama 3.1 8B Instant – 8B",
    "llama-3.1-70b-versatile": "Llama 3.1 70B Versatile – 70B",
    "llama-3.3-70b-specdec": "Llama 3.3 70B SpecDec – 70B",
    "llama-3.3-70b-versatile": "Llama 3.3 70B Versatile – 70B",
    "llama-guard-3-8b": "Llama Guard 3 8B – 8B",
    "llama3-groq-70b-8192-tool-use-preview": "Llama 3 Groq 70B Tool Use – 70B",
    "llama3-groq-8b-8192-tool-use-preview": "Llama 3 Groq 8B Tool Use – 8B",
    "mixtral-8x7b-32768": "Mixtral 8x7B – 46.7B",
    "gemma2-9b-it": "Gemma 2 9B IT – 9B",
    "qwen-2.5-32b": "Qwen 2.5 32B – 32B",
    "qwen-2.5-coder-32b": "Qwen 2.5 Coder 32B – 32B",
    "deepseek-r1-distill-llama-70b": "DeepSeek R1 Distill 70B – 70B",
}

# Models to exclude (non-chat models)
EXCLUDED_KEYWORDS = ["whisper", "orpheus", "guard", "compound", "playai", "distil-whisper"]

# In-memory cache for available models
_cached_models = []
_cache_timestamp = 0
CACHE_TTL = 300  # 5 minutes

async def test_model_ping(model_id: str) -> bool:
    """Test if a model actually responds to a simple ping."""
    try:
        req = ChatRequest(
            model=model_id,
            messages=[ChatMessage(role="user", content="ping")]
        )
        resp = await llm_client.chat_completion(req, system_prompt="Reply exactly with 'pong'", max_tokens=2)
        return resp.status_code == 200
    except Exception:
        return False

async def get_available_models() -> List[dict]:
    global _cached_models, _cache_timestamp
    
    current_time = time.time()
    if _cached_models and (current_time - _cache_timestamp) < CACHE_TTL:
        print("Returning cached models")
        return _cached_models

    try:
        data = await llm_client.list_models()
        models_to_test = []
        
        for m in data.get("data", []):
            model_id = m.get("id")
            
            # Filter out non-chat models
            if any(k in model_id.lower() for k in EXCLUDED_KEYWORDS):
                continue
                
            name = FRIENDLY_NAMES.get(model_id, model_id.replace("-", " ").title())
            models_to_test.append({"id": model_id, "name": name})
            
        # Sort: Llama first, then alphabetically
        models_to_test.sort(key=lambda x: ("llama" not in x["name"].lower(), x["name"]))
        
        # Ping test models concurrently (limit to top 15 to avoid long wait)
        print(f"Testing {len(models_to_test[:15])} models from {llm_client.provider.upper()}...")
        tasks = [test_model_ping(m["id"]) for m in models_to_test[:15]]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        validated_models = []
        for i, is_active in enumerate(results):
            if is_active is True:
                validated_models.append(models_to_test[i])
            else:
                print(f"Model {models_to_test[i]['id']} failed ping test.")
        
        if validated_models:
            _cached_models = validated_models
            _cache_timestamp = current_time
            return validated_models
        else:
            raise Exception("All models failed ping test")
        
    except Exception as e:
        print(f"[{llm_client.provider.upper()}] Model Fetch/Test Error: {e}")
        # Return fallback models based on provider
        fallback = [
            {"id": "llama-3.3-70b-versatile", "name": "Llama 3.3 70B Versatile – 70B"},
            {"id": "llama-3.1-8b-instant", "name": "Llama 3.1 8B Instant – 8B"},
        ]
        if not _cached_models:
            _cached_models = fallback
            _cache_timestamp = current_time
        return _cached_models
