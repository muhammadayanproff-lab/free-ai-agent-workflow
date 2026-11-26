"""Optional on-runner Qwen model using llama.cpp CPU inference.

The model is downloaded by the campaign workflow into models/. If the runtime
or model is unavailable, callers receive None and continue to their next
provider or deterministic Python fallback.
"""
import json
import os
from pathlib import Path

_MODEL = None
_MODEL_ERROR = None


def _load_model():
    global _MODEL, _MODEL_ERROR
    if _MODEL is not None:
        return _MODEL
    if _MODEL_ERROR:
        return None
    model_path = Path(os.getenv(
        "LOCAL_LLM_MODEL_PATH",
        "models/qwen2.5-1.5b-instruct-q4_k_m.gguf",
    ))
    if not model_path.is_file():
        _MODEL_ERROR = f"Local Qwen model file not found: {model_path}"
        print(_MODEL_ERROR)
        return None
    try:
        from llama_cpp import Llama
        _MODEL = Llama(
            model_path=str(model_path),
            n_ctx=int(os.getenv("LOCAL_LLM_CONTEXT", "8192")),
            n_threads=max(1, int(os.getenv("LOCAL_LLM_THREADS", "4"))),
            n_batch=256,
            verbose=False,
        )
        print(f"Loaded local CPU model: {model_path.name}")
        return _MODEL
    except Exception as exc:
        _MODEL_ERROR = f"Local Qwen runtime unavailable: {exc}"
        print(_MODEL_ERROR)
        return None


def qwen_chat(prompt, max_tokens=2500, json_mode=False):
    """Return local Qwen text or parsed JSON; None if unavailable."""
    model = _load_model()
    if model is None:
        return None
    try:
        kwargs = {
            "messages": [
                {"role": "system", "content": (
                    "You are a careful Pakistan ecommerce assistant. "
                    "Use only supplied facts. Clearly mark missing evidence. "
                    "Never invent prices, stock, delivery, COD, reviews or claims."
                )},
                {"role": "user", "content": str(prompt)},
            ],
            "temperature": 0.25,
            "max_tokens": max(128, min(int(max_tokens), 3500)),
        }
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        response = model.create_chat_completion(**kwargs)
        answer = response["choices"][0]["message"].get("content", "")
        if not isinstance(answer, str) or not answer.strip():
            return None
        answer = answer.strip()
        if not json_mode:
            return answer
        try:
            return json.loads(answer)
        except json.JSONDecodeError:
            start, end = answer.find("{"), answer.rfind("}")
            if start >= 0 and end > start:
                return json.loads(answer[start:end + 1])
            print("Local Qwen returned invalid JSON.")
            return None
    except Exception as exc:
        print(f"Local Qwen inference failed: {exc}")
        return None
