import json
import re
from typing import Any, AsyncGenerator, Dict, List, Optional
from llm_client import ChatMessage, ChatRequest, llm_client


class AgentRuntime:
    def __init__(self):
        import os
        self.model_name = os.getenv("MODEL_NAME", "alibayram/smollm3")
        print(f"DEBUG: Successfully initialized with model: {self.model_name}")
        # Clean system prompt — no special /think formatting instructions needed.
        # The model natively uses <think>...</think> and we parse it server-side.
        self.system_prompt = """You are Smartbridge AI, an expert AI assistant for the Smartbridge platform.
You help users with tasks, questions, code, analysis, and anything related to their workspace.
Be concise, accurate, and helpful. Use Markdown in your responses when it improves readability.
"""

    def apply_semantic_snapshots(self, text: str, max_words: int = 1000) -> str:
        """Optimization: only send relevant snippets to the 3B model instead of whole file."""
        words = text.split()
        if len(words) > max_words:
            half_words = int(max_words / 2)
            return " ".join(words[:half_words]) + "\n\n... [snip] ...\n\n" + " ".join(words[-half_words:])
        return text

    def _parse_llm_response(self, raw: str) -> tuple[str, str]:
        """
        Parse an LLM raw response string and return (thoughts, final_message).

        Handles:
          - <think>...</think> native tags
          - /think prefix
          - **Thinking Process:** blocks (common in smaller models)
          - Raw JSON leakage like {"text": "Hello"}
        """
        thoughts = ""
        message = raw.strip()

        # 0. Strip leading markdown junk often emitted by 3B models
        message = re.sub(r'^"""\w*\n|^-{3,}\n|^-{3,}$', '', message, flags=re.MULTILINE).strip()

        # 1. Handle <think>...</think> native tags
        think_match = re.search(r"<think>([\s\S]*?)</think>", message, re.DOTALL)
        if think_match:
            thoughts = think_match.group(1).strip()
            message = message[:think_match.start()] + message[think_match.end():]
            message = message.strip()

        # 2. Handle **Thinking Process:** or **Thought:** blocks
        if not thoughts:
            tp_match = re.search(r"\*\*(Thinking Process|Thought):\*\*([\s\S]*?)(?=\*\*Action:\*\*|\*\*Output:\*\*|$)", message, re.IGNORECASE)
            if tp_match:
                thoughts = tp_match.group(2).strip()
                message = message[:tp_match.start()] + message[tp_match.end():]
                message = message.strip()

        # 3. Handle /think ...
        if not thoughts and message.startswith("/think"):
            parts = re.split(r"\n\s*\n", message, maxsplit=1)
            if len(parts) == 2:
                thoughts = parts[0].replace("/think", "").strip()
                message = parts[1].strip()
            else:
                thoughts = message.replace("/think", "").strip()
                message = ""

        # 4. Strip leftover semantic labels
        message = re.sub(r"\*\*(Action|Output|Final Response):\*\*\s*", "", message, flags=re.IGNORECASE).strip()

        # 5. Strip raw JSON leakage like {"text": "Hello"} at start
        json_leak_match = re.match(r'^\{"text":\s*"(.+?)"\}', message, re.DOTALL)
        if json_leak_match:
            message = json_leak_match.group(1)

        return thoughts.strip(), message.strip()

    async def run_loop_stream(
        self,
        request: ChatRequest,
        context_hits: Optional[List[Dict[str, Any]]] = None,
    ) -> AsyncGenerator[str, None]:
        """
        Stream SSE-formatted JSON events:
          data: {"type": "thought", "content": "..."}\n\n
          data: {"type": "message", "content": "..."}\n\n
          data: {"type": "done"}\n\n
        """
        # Inject semantic snapshots if we have context hits for document analysis
        if context_hits:
            context_str = "Context Snippets:\n"
            for hit in context_hits:
                content = hit.get("content", "")
                context_str += self.apply_semantic_snapshots(content, max_words=200) + "\n\n"
            request.messages.insert(0, ChatMessage(role="system", content=context_str))

        # Inject repository context if in GitHub Agent mode
        repo_data = request.workspace_options.get("repo_structure")
        if repo_data and isinstance(repo_data, dict):
            repo_url = request.workspace_options.get("active_repo", "unknown repo")
            structure_str = f"You are currently analyzing the following GitHub repository:\nURL: {repo_url}\nStructure (Limited to files): " + ", ".join(repo_data.get("files", []))
            request.messages.insert(0, ChatMessage(role="system", content=structure_str))

        try:
            response = await llm_client.chat_completion(
                request=request,
                system_prompt=self.system_prompt,
                temperature=0.3,
                max_tokens=4096,
            )
            data = response.json()
            raw_content = data["choices"][0]["message"]["content"]

            thoughts, final_message = self._parse_llm_response(raw_content)

            # Stream thoughts first
            if thoughts:
                yield f"data: {json.dumps({'type': 'thought', 'content': thoughts})}\n\n"

            # Then stream the final message
            if final_message:
                yield f"data: {json.dumps({'type': 'message', 'content': final_message})}\n\n"
            elif not thoughts:
                # Truly empty response — emit a fallback
                yield f"data: {json.dumps({'type': 'message', 'content': 'Sorry, I could not generate a response. Please try again.'})}\n\n"

        except Exception as e:
            error_msg = f"Error during reasoning: {str(e)}"
            yield f"data: {json.dumps({'type': 'error', 'content': error_msg})}\n\n"

        finally:
            yield f"data: {json.dumps({'type': 'done'})}\n\n"
