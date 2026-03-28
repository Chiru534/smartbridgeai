import os
from typing import Any, Dict, List, Optional

import httpx
from dotenv import load_dotenv
from pydantic import BaseModel, Field

# Ensure environment variables are loaded BEFORE llm_client initialization
load_dotenv()


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    model: str = "llama-3.3-70b-versatile"
    messages: List[ChatMessage]
    session_id: Optional[str] = None
    mode: str = "standard_chat"
    workspace_options: Dict[str, Any] = Field(default_factory=dict)


class UniversalLLMClient:
    def __init__(self):
        self.provider = os.getenv("LLM_PROVIDER", "groq").lower()

        default_base_urls = {
            "groq": "https://api.groq.com/openai/v1",
            "openai": "https://api.openai.com/v1",
            "ollama": "http://localhost:11434/v1",
        }

        self.base_url = os.getenv(
            "LLM_BASE_URL",
            default_base_urls.get(self.provider, default_base_urls["groq"]),
        )
        self.api_key = os.getenv("LLM_API_KEY", os.getenv("GROQ_API_KEY", ""))
        self.default_model = os.getenv("MODEL_NAME", "llama-3.3-70b-versatile")

        print(
            f"[LLM Adapter] Provider: {self.provider.upper()} | "
            f"Model: {self.default_model} | URL: {self.base_url}"
        )

    async def chat_completion(
        self,
        request: Optional[ChatRequest] = None,
        system_prompt: Optional[str] = None,
        temperature: float = 0.2,
        max_tokens: int = 8192,
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_choice: Optional[str] = None,
        messages: Optional[List[Dict[str, Any]]] = None,
        model: Optional[str] = None,
        timeout_seconds: float = 90.0,
    ) -> httpx.Response:
        """
        Sends a chat completion request using the OpenAI-compatible
        /chat/completions endpoint (Groq, OpenAI, or Ollama /v1).
        """
        headers: Dict[str, str] = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        if messages is None:
            if not request or not system_prompt:
                raise ValueError(
                    "Must provide either 'messages' or ('request' and 'system_prompt')"
                )
            messages = [{"role": "system", "content": system_prompt}] + [
                m.model_dump() if hasattr(m, "model_dump") else m
                for m in request.messages
            ]

        model = model or (request.model if request else None) or self.default_model

        payload: Dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if tools:
            payload["tools"] = tools
        if tool_choice:
            payload["tool_choice"] = tool_choice

        endpoint = f"{self.base_url.rstrip('/')}/chat/completions"

        async with httpx.AsyncClient() as client:
            response = await client.post(
                endpoint, headers=headers, json=payload, timeout=timeout_seconds
            )
            response.raise_for_status()
            return response

    async def list_models(self) -> Dict[str, Any]:
        """Returns available models from the configured provider."""
        headers: Dict[str, str] = {}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        endpoint = f"{self.base_url.rstrip('/')}/models"
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(endpoint, headers=headers, timeout=10.0)
                response.raise_for_status()
                return response.json()
            except Exception as e:
                print(f"[LLM Adapter] Failed to fetch models from {endpoint}: {e}")
                return {
                    "data": [
                        {
                            "id": self.default_model,
                            "name": f"Default {self.provider.title()} Model",
                        }
                    ]
                }


# Global singleton instance for the app to use
llm_client = UniversalLLMClient()
