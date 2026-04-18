"""
core/groq_utils.py — Shared Groq API helpers

Single place for API key resolution and chat completion calls.
Used by verbatim_checks, NL rule builder, feedback letter generator,
and auto column detection.
"""

import os
import json
import requests

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
DEFAULT_MODEL = "llama3-8b-8192"


def get_api_key() -> str:
    key = os.environ.get("GROQ_API_KEY", "")
    if not key:
        env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
        if os.path.exists(env_path):
            try:
                with open(env_path) as f:
                    for line in f:
                        line = line.strip()
                        if line.startswith("GROQ_API_KEY="):
                            key = line.split("=", 1)[1].strip().strip('"').strip("'")
                            break
            except OSError:
                pass
    return key


def groq_available() -> bool:
    return bool(get_api_key())


def groq_chat(
    prompt: str,
    system: str = "",
    model: str = DEFAULT_MODEL,
    temperature: float = 0.1,
    max_tokens: int = 1024,
) -> str:
    """
    Call Groq chat completions. Returns response text.
    Raises RuntimeError if API key is missing, requests.HTTPError on API failure.
    """
    api_key = get_api_key()
    if not api_key:
        raise RuntimeError("GROQ_API_KEY not configured")

    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    resp = requests.post(
        GROQ_API_URL,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        },
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"].strip()


def groq_json(
    prompt: str,
    system: str = "",
    model: str = DEFAULT_MODEL,
) -> dict | list:
    """
    Call Groq and parse the response as JSON.
    Strips markdown code fences before parsing.
    """
    raw = groq_chat(prompt, system=system, model=model)
    # Strip ```json ... ``` fences if present
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[-1]
        if raw.endswith("```"):
            raw = raw.rsplit("```", 1)[0]
    return json.loads(raw.strip())
