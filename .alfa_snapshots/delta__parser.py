"""
ALFA DELTA v1 — PARSER
Parser wiadomości Delta Chat.
"""

from typing import Optional, Dict, Any, List, Tuple
import logging
import re
from dataclasses import dataclass

logger = logging.getLogger("ALFA.Delta.Parser")


@dataclass
class ParsedCommand:
    """Sparsowana komenda."""
    command: str
    args: List[str]
    raw_text: str
    is_command: bool = True


class DeltaParser:
    """
    Parser wiadomości Delta Chat.
    Rozpoznaje komendy, pytania, i typy wiadomości.
    """
    
    # Prefiksy komend
    COMMAND_PREFIXES = ["/", "!", ".", "\\"]
    
    # Znane komendy
    KNOWN_COMMANDS = {
        "help": ["help", "pomoc", "?"],
        "status": ["status", "stan"],
        "clear": ["clear", "wyczyść", "reset"],
        "voice": ["voice", "głos", "mów"],
        "image": ["image", "obraz", "zdjęcie"],
        "code": ["code", "kod"],
        "stop": ["stop", "zatrzymaj"],
    }
    
    def __init__(self):
        # Compile command patterns
        self._command_aliases = {}
        for cmd, aliases in self.KNOWN_COMMANDS.items():
            for alias in aliases:
                self._command_aliases[alias.lower()] = cmd
        
        logger.info("DeltaParser initialized")
    
    def parse(self, text: str) -> Dict[str, Any]:
        """
        Parsuje wiadomość.
        
        Args:
            text: Tekst wiadomości
            
        Returns:
            Dict z informacjami o wiadomości
        """
        text = text.strip()
        
        # Check if it's a command
        command = self._parse_command(text)
        if command:
            return {
                "type": "command",
                "command": command.command,
                "args": command.args,
                "raw": text
            }
        
        # Check for questions
        if self._is_question(text):
            return {
                "type": "question",
                "text": text,
                "raw": text
            }
        
        # Check for code blocks
        code = self._extract_code(text)
        if code:
            return {
                "type": "code",
                "language": code[0],
                "code": code[1],
                "raw": text
            }
        
        # Default: regular message
        return {
            "type": "message",
            "text": text,
            "raw": text
        }
    
    def _parse_command(self, text: str) -> Optional[ParsedCommand]:
        """Parsuje komendę."""
        if not text:
            return None
        
        # Check for command prefix
        for prefix in self.COMMAND_PREFIXES:
            if text.startswith(prefix):
                text = text[len(prefix):]
                break
        else:
            return None
        
        # Split command and args
        parts = text.split()
        if not parts:
            return None
        
        cmd_text = parts[0].lower()
        args = parts[1:]
        
        # Resolve alias
        command = self._command_aliases.get(cmd_text, cmd_text)
        
        return ParsedCommand(
            command=command,
            args=args,
            raw_text=text
        )
    
    def _is_question(self, text: str) -> bool:
        """Sprawdza czy tekst jest pytaniem."""
        # Ends with question mark
        if text.endswith("?"):
            return True
        
        # Starts with question words
        question_words = [
            "co", "jak", "gdzie", "kiedy", "dlaczego", "czy", "kto",
            "what", "how", "where", "when", "why", "who", "which", "is", "are", "do", "does"
        ]
        
        first_word = text.split()[0].lower() if text.split() else ""
        return first_word in question_words
    
    def _extract_code(self, text: str) -> Optional[Tuple[str, str]]:
        """Wyciąga blok kodu z wiadomości."""
        # Markdown code block
        pattern = r"```(\w*)\n?([\s\S]*?)```"
        match = re.search(pattern, text)
        
        if match:
            language = match.group(1) or "text"
            code = match.group(2).strip()
            return (language, code)
        
        # Single backticks (inline code)
        pattern = r"`([^`]+)`"
        match = re.search(pattern, text)
        
        if match:
            return ("inline", match.group(1))
        
        return None
    
    def extract_mentions(self, text: str) -> List[str]:
        """Wyciąga wzmianki (@user)."""
        pattern = r"@(\w+)"
        return re.findall(pattern, text)
    
    def extract_urls(self, text: str) -> List[str]:
        """Wyciąga URLe."""
        pattern = r"https?://[^\s]+"
        return re.findall(pattern, text)
    
    def extract_emails(self, text: str) -> List[str]:
        """Wyciąga adresy email."""
        pattern = r"[\w\.-]+@[\w\.-]+\.\w+"
        return re.findall(pattern, text)
    
    def sanitize(self, text: str) -> str:
        """Czyści tekst z niebezpiecznych elementów."""
        # Remove control characters
        text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)
        
        # Limit length
        max_len = 10000
        if len(text) > max_len:
            text = text[:max_len] + "..."
        
        return text.strip()
    
    def format_response(
        self,
        text: str,
        include_voice: bool = False,
        include_code: bool = False
    ) -> str:
        """Formatuje odpowiedź dla Delta Chat."""
        # Delta Chat obsługuje podstawowy Markdown
        
        if include_code:
            # Ensure code blocks are properly formatted
            pass
        
        if include_voice:
            text = f"🔊 {text}"
        
        return text
