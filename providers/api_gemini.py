"""
ALFA GEMINI PROVIDER — WERSJA OSTATECZNA
Zero bullshitu. Działa. Odpala. Daje odpowiedzi.
"""

import os
import requests
from typing import Optional


class GeminiAPI:
    def __init__(self, api_key: Optional[str] = None, model: str = "gemini-1.5-flash"):
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY", "")
        self.model = model
        self.url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

    def ask(self, prompt: str) -> str:
        if not self.api_key:
            return "[ERROR] Brak GEMINI_API_KEY"

        payload = {
            "contents": [
                {"role": "user", "parts": [{"text": prompt}]}
            ],
            "safetySettings": [
                {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"}
            ]
        }

        try:
            response = requests.post(
                self.url,
                headers={
                    "Content-Type": "application/json",
                    "x-goog-api-key": self.api_key
                },
                json=payload,
                timeout=30
            )

            if response.status_code != 200:
                return f"[GEMINI ERROR] {response.status_code}: {response.text}"

            data = response.json()
            return data["candidates"][0]["content"]["parts"][0]["text"]

        except requests.exceptions.Timeout:
            return "[ERROR] Gemini timeout"
        except Exception as e:
            return f"[ERROR] {e}"


# Singleton
_instance: Optional[GeminiAPI] = None

def get_gemini(api_key: Optional[str] = None) -> GeminiAPI:
    global _instance
    if _instance is None:
        _instance = GeminiAPI(api_key)
    return _instance
