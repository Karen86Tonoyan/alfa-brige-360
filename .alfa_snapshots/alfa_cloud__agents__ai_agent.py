"""
🤖 AI AGENT
Agent AI dla ALFA CLOUD z lokalnymi modelami
"""

from __future__ import annotations
import asyncio
import json
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass
from typing import Optional, List, Dict, Any, Callable, AsyncGenerator
import logging

from alfa_cloud.ai.local_llm import LocalLLM, LocalLLMConfig, SystemPrompts
from alfa_cloud.ai.analyzer import Analyzer, AnalysisResult
from alfa_cloud.core.event_bus import EventBus


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# DATA CLASSES
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@dataclass
class AITask:
    """Zadanie AI"""
    id: str
    type: str  # chat, analyze, summarize, embed
    prompt: str
    model: Optional[str] = None
    status: str = "pending"  # pending, running, completed, failed
    result: Optional[str] = None
    created_at: datetime = None
    completed_at: datetime = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()


@dataclass
class Conversation:
    """Rozmowa z AI"""
    id: str
    title: str
    messages: List[Dict[str, str]]
    model: str
    created_at: datetime
    updated_at: datetime
    
    def add_message(self, role: str, content: str):
        self.messages.append({"role": role, "content": content})
        self.updated_at = datetime.now()


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# AI AGENT
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class AIAgent:
    """
    🤖 Agent AI dla ALFA CLOUD
    
    Funkcje:
    - Chat z zachowaniem kontekstu
    - Analiza plików i dokumentów
    - Generowanie podsumowań
    - Embeddingi do wyszukiwania semantycznego
    - Automatyczne zadania AI
    """
    
    def __init__(self,
                 config: Optional[LocalLLMConfig] = None,
                 event_bus: Optional[EventBus] = None):
        
        self.config = config or LocalLLMConfig()
        self.event_bus = event_bus or EventBus()
        self.logger = logging.getLogger("ALFA_CLOUD.AIAgent")
        
        # LLM i Analyzer
        self.llm = LocalLLM(self.config)
        self.analyzer = Analyzer(self.llm)
        
        # Rozmowy
        self.conversations: Dict[str, Conversation] = {}
        self.current_conversation: Optional[str] = None
        
        # Kolejka zadań
        self.task_queue: List[AITask] = []
        self._processing = False
    
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # CHAT
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    
    def new_conversation(self, 
                        title: str = "Nowa rozmowa",
                        model: Optional[str] = None) -> str:
        """Tworzy nową rozmowę"""
        import uuid
        conv_id = str(uuid.uuid4())[:8]
        
        self.conversations[conv_id] = Conversation(
            id=conv_id,
            title=title,
            messages=[],
            model=model or self.config.default_model,
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        
        self.current_conversation = conv_id
        self.llm.clear_history()
        
        return conv_id
    
    def switch_conversation(self, conv_id: str) -> bool:
        """Przełącza rozmowę"""
        if conv_id in self.conversations:
            self.current_conversation = conv_id
            # Załaduj historię do LLM
            self.llm._conversation_history = [
                {"role": msg["role"], "content": msg["content"]}
                for msg in self.conversations[conv_id].messages
            ]
            return True
        return False
    
    async def chat(self, 
                   message: str,
                   conv_id: Optional[str] = None,
                   stream: bool = False) -> str | AsyncGenerator[str, None]:
        """
        Chat z AI
        
        Args:
            message: Wiadomość użytkownika
            conv_id: ID rozmowy (lub obecna)
            stream: Czy streamować odpowiedź
        """
        # Użyj lub utwórz rozmowę
        if conv_id:
            self.switch_conversation(conv_id)
        elif not self.current_conversation:
            self.new_conversation()
        
        conv = self.conversations[self.current_conversation]
        conv.add_message("user", message)
        
        self.event_bus.emit("ai:chat_start", {
            "conv_id": self.current_conversation,
            "message": message
        })
        
        if stream:
            return self._stream_response(message, conv)
        else:
            response = await self.llm.chat(
                message,
                model=conv.model,
                system=SystemPrompts.ALFA_ASSISTANT
            )
            conv.add_message("assistant", response)
            
            self.event_bus.emit("ai:chat_complete", {
                "conv_id": self.current_conversation,
                "response": response
            })
            
            return response
    
    async def _stream_response(self, message: str, conv: Conversation) -> AsyncGenerator[str, None]:
        """Streamuje odpowiedź"""
        full_response = ""
        
        async for chunk in self.llm.stream(
            message,
            model=conv.model,
            system=SystemPrompts.ALFA_ASSISTANT
        ):
            full_response += chunk
            yield chunk
        
        conv.add_message("assistant", full_response)
    
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # ANALYSIS
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    
    async def analyze_file(self, file_path: str) -> AnalysisResult:
        """Analizuje plik"""
        self.logger.info(f"📊 Analizuję plik: {file_path}")
        
        result = await self.analyzer.analyze_file(file_path)
        
        self.event_bus.emit("ai:file_analyzed", {
            "file_path": file_path,
            "result": result.to_dict()
        })
        
        return result
    
    async def summarize(self, text: str, max_sentences: int = 3) -> str:
        """Generuje podsumowanie"""
        return await self.analyzer.summarize(text, max_sentences)
    
    async def extract_keywords(self, text: str, max_keywords: int = 10) -> List[str]:
        """Ekstrahuje słowa kluczowe"""
        return await self.analyzer.extract_keywords(text, max_keywords)
    
    async def embed_text(self, text: str) -> List[float]:
        """Generuje embedding dla tekstu"""
        return await self.llm.embed(text)
    
    async def embed_file(self, file_path: str) -> Dict[str, Any]:
        """Generuje embedding dla pliku"""
        path = Path(file_path)
        if not path.exists():
            return {"error": "File not found"}
        
        content = path.read_text(encoding='utf-8', errors='ignore')[:8000]
        embedding = await self.llm.embed(content)
        
        return {
            "file_path": file_path,
            "embedding": embedding,
            "dimensions": len(embedding)
        }
    
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # TASKS
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    
    def queue_task(self, 
                   task_type: str,
                   prompt: str,
                   model: Optional[str] = None) -> AITask:
        """Dodaje zadanie do kolejki"""
        import uuid
        
        task = AITask(
            id=str(uuid.uuid4())[:8],
            type=task_type,
            prompt=prompt,
            model=model
        )
        
        self.task_queue.append(task)
        return task
    
    async def process_tasks(self):
        """Przetwarza kolejkę zadań"""
        if self._processing:
            return
        
        self._processing = True
        
        while self.task_queue:
            task = self.task_queue.pop(0)
            task.status = "running"
            
            try:
                if task.type == "chat":
                    task.result = await self.llm.generate(task.prompt, model=task.model)
                
                elif task.type == "analyze":
                    result = await self.analyzer.analyze_file(task.prompt)
                    task.result = result.analysis
                
                elif task.type == "summarize":
                    task.result = await self.analyzer.summarize(task.prompt)
                
                elif task.type == "embed":
                    embedding = await self.llm.embed(task.prompt)
                    task.result = json.dumps(embedding[:10])  # Tylko pierwsze 10 dla podglądu
                
                task.status = "completed"
                
            except Exception as e:
                task.status = "failed"
                task.result = str(e)
            
            task.completed_at = datetime.now()
            
            self.event_bus.emit("ai:task_complete", {
                "task_id": task.id,
                "status": task.status
            })
        
        self._processing = False
    
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # SPECIALIZED PROMPTS
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    
    async def code_review(self, code: str, language: str = "python") -> str:
        """Code review"""
        prompt = f"""Przeanalizuj poniższy kod {language} i podaj:
1. Potencjalne błędy
2. Problemy bezpieczeństwa
3. Sugestie optymalizacji
4. Ocena ogólna (1-10)

```{language}
{code}
```"""
        
        return await self.llm.generate(prompt, task="code", system=SystemPrompts.CODE_ASSISTANT)
    
    async def explain_code(self, code: str, language: str = "python") -> str:
        """Wyjaśnia kod"""
        prompt = f"""Wyjaśnij co robi poniższy kod {language}. Opisz:
1. Główny cel
2. Działanie krok po kroku
3. Używane wzorce/techniki

```{language}
{code}
```"""
        
        return await self.llm.generate(prompt, task="code")
    
    async def generate_code(self, description: str, language: str = "python") -> str:
        """Generuje kod na podstawie opisu"""
        prompt = f"""Napisz kod {language} który:
{description}

Wymagania:
- Czysty, czytelny kod
- Komentarze wyjaśniające
- Obsługa błędów

Kod:"""
        
        return await self.llm.generate(prompt, task="code", system=SystemPrompts.CODE_ASSISTANT)
    
    async def security_analysis(self, text: str) -> str:
        """Analiza bezpieczeństwa"""
        prompt = f"""Przeanalizuj poniższy tekst pod kątem bezpieczeństwa:

{text}

Oceń:
1. Czy zawiera wrażliwe dane?
2. Potencjalne zagrożenia
3. Rekomendacje"""
        
        return await self.llm.generate(prompt, system=SystemPrompts.SECURITY_ANALYST)
    
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # UTILS
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    
    def list_conversations(self) -> List[Dict[str, Any]]:
        """Lista rozmów"""
        return [
            {
                "id": c.id,
                "title": c.title,
                "messages_count": len(c.messages),
                "model": c.model,
                "created_at": c.created_at.isoformat(),
                "updated_at": c.updated_at.isoformat()
            }
            for c in self.conversations.values()
        ]
    
    def delete_conversation(self, conv_id: str) -> bool:
        """Usuwa rozmowę"""
        if conv_id in self.conversations:
            del self.conversations[conv_id]
            if self.current_conversation == conv_id:
                self.current_conversation = None
            return True
        return False
    
    async def check_availability(self) -> Dict[str, Any]:
        """Sprawdza dostępność AI"""
        available = self.llm.is_available
        models = await self.llm.list_models() if available else []
        
        return {
            "available": available,
            "endpoint": self.config.endpoint,
            "default_model": self.config.default_model,
            "models": models
        }


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# COMMAND LINE INTERFACE
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

import argparse

def main():
    parser = argparse.ArgumentParser(description="🤖 AI AGENT dla ALFA CLOUD")
    parser.add_argument("--mode", type=str, choices=["api", "sync", "cli"], default="api",
                        help="Tryb działania: api, sync, cli")
    parser.add_argument("--port", type=int, default=8000, help="Port dla API")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="Host dla API")
    
    args = parser.parse_args()
    
    if args.mode == "api":
        from alfa_core.api import start_api
        start_api(host=args.host, port=args.port)
    
    elif args.mode == "sync":
        from alfa_core.sync import start_sync
        start_sync()
    
    elif args.mode == "cli":
        from alfa_core.cli import start_cli
        start_cli()

if __name__ == "__main__":
    main()

# Usage:
# python -m alfa_core              # Full system
# python -m alfa_core --mode api   # API only
# python -m alfa_core --mode sync  # Sync only
# python -m alfa_core --mode cli   # Interactive CLI
# python -m alfa_core status       # Show status
# python -m alfa_core health       # Health check