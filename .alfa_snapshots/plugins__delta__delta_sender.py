"""
ALFA Delta Sender v1.0
Wysyłanie wiadomości przez SMTP (z opcjonalnym voice attachment)
"""

from __future__ import annotations

import logging
import mimetypes
import smtplib
from email.mime.audio import MIMEAudio
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email import encoders
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

logger = logging.getLogger("alfa.delta.sender")


class DeltaSender:
    """
    SMTP Sender dla Delta Chat.
    
    Wysyła odpowiedzi z opcjonalnymi załącznikami (np. voice .ogg).
    """
    
    def __init__(
        self,
        host: str,
        port: int,
        username: str,
        password: str,
        *,
        starttls: bool = True,
        from_name: str = "ALFA",
    ):
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.starttls = starttls
        self.from_name = from_name
        self.from_address = username  # zwykle to samo co login
        
    def _create_connection(self) -> smtplib.SMTP:
        """Utwórz połączenie SMTP."""
        server = smtplib.SMTP(self.host, self.port)
        server.ehlo()
        
        if self.starttls:
            server.starttls()
            server.ehlo()
            
        server.login(self.username, self.password)
        return server
        
    def send_text(
        self,
        to: str,
        subject: str,
        body: str,
        *,
        reply_to_id: Optional[str] = None,
    ) -> bool:
        """Wyślij prostą wiadomość tekstową."""
        return self.send(
            to=to,
            subject=subject,
            body=body,
            attachments=[],
            reply_to_id=reply_to_id,
        )
        
    def send_with_voice(
        self,
        to: str,
        subject: str,
        body: str,
        voice_path: Union[str, Path],
        *,
        reply_to_id: Optional[str] = None,
    ) -> bool:
        """Wyślij wiadomość z załącznikiem głosowym."""
        voice_file = Path(voice_path)
        
        if not voice_file.exists():
            logger.error(f"[DELTA] Voice file not found: {voice_path}")
            return False
            
        attachment = {
            "path": voice_file,
            "filename": voice_file.name,
            "content_type": "audio/ogg",
        }
        
        return self.send(
            to=to,
            subject=subject,
            body=body,
            attachments=[attachment],
            reply_to_id=reply_to_id,
        )
        
    def send(
        self,
        to: str,
        subject: str,
        body: str,
        attachments: Optional[List[Dict[str, Any]]] = None,
        *,
        reply_to_id: Optional[str] = None,
        html_body: Optional[str] = None,
    ) -> bool:
        """
        Wyślij wiadomość email z załącznikami.
        
        Args:
            to: Adres odbiorcy
            subject: Temat
            body: Treść tekstowa
            attachments: Lista załączników [{"path": Path, "filename": str, "content_type": str}]
            reply_to_id: Message-ID do odpowiedzi (threading)
            html_body: Opcjonalna wersja HTML
            
        Returns:
            True jeśli wysłano pomyślnie
        """
        attachments = attachments or []
        
        try:
            # Twórz wiadomość
            if attachments or html_body:
                msg = MIMEMultipart("mixed")
                
                # Tekst
                text_part = MIMEText(body, "plain", "utf-8")
                msg.attach(text_part)
                
                # HTML (opcjonalnie)
                if html_body:
                    html_part = MIMEText(html_body, "html", "utf-8")
                    msg.attach(html_part)
                    
                # Załączniki
                for attachment in attachments:
                    self._attach_file(msg, attachment)
            else:
                msg = MIMEText(body, "plain", "utf-8")
                
            # Nagłówki
            msg["From"] = f"{self.from_name} <{self.from_address}>"
            msg["To"] = to
            msg["Subject"] = subject
            
            # Thread support (Delta Chat)
            if reply_to_id:
                msg["In-Reply-To"] = reply_to_id
                msg["References"] = reply_to_id
                
            # Wyślij
            with self._create_connection() as server:
                server.sendmail(self.from_address, [to], msg.as_string())
                
            logger.info(f"[DELTA] Sent message to {to}: {subject[:50]}")
            return True
            
        except Exception as e:
            logger.error(f"[DELTA] Send failed: {e}")
            return False
            
    def _attach_file(self, msg: MIMEMultipart, attachment: Dict[str, Any]) -> None:
        """Dodaj załącznik do wiadomości."""
        path = Path(attachment["path"])
        filename = attachment.get("filename", path.name)
        content_type = attachment.get("content_type")
        
        if not content_type:
            content_type, _ = mimetypes.guess_type(str(path))
            content_type = content_type or "application/octet-stream"
            
        main_type, sub_type = content_type.split("/", 1)
        
        with open(path, "rb") as f:
            data = f.read()
            
        if main_type == "audio":
            part = MIMEAudio(data, sub_type)
        else:
            part = MIMEBase(main_type, sub_type)
            part.set_payload(data)
            encoders.encode_base64(part)
            
        part.add_header(
            "Content-Disposition",
            "attachment",
            filename=filename,
        )
        
        msg.attach(part)


# === VOICE GENERATION HELPERS ===

class VoiceGenerator:
    """
    Generator głosu dla Delta Chat.
    
    Obsługuje różne backendy TTS.
    """
    
    def __init__(self, engine: str = "piper", output_dir: str = "/tmp/alfa_voice"):
        self.engine = engine
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
    def generate(self, text: str, filename: Optional[str] = None) -> Optional[Path]:
        """
        Wygeneruj plik audio z tekstu.
        
        Returns:
            Ścieżka do pliku .ogg lub None w przypadku błędu
        """
        if not filename:
            import hashlib
            hash_id = hashlib.md5(text.encode()).hexdigest()[:8]
            filename = f"voice_{hash_id}.ogg"
            
        output_path = self.output_dir / filename
        
        try:
            if self.engine == "piper":
                return self._generate_piper(text, output_path)
            elif self.engine == "edge":
                return self._generate_edge(text, output_path)
            elif self.engine == "deepseek":
                return self._generate_deepseek(text, output_path)
            else:
                logger.error(f"[VOICE] Unknown engine: {self.engine}")
                return None
                
        except Exception as e:
            logger.error(f"[VOICE] Generation failed: {e}")
            return None
            
    def _generate_piper(self, text: str, output_path: Path) -> Optional[Path]:
        """Generuj przez Piper TTS."""
        import subprocess
        
        # Piper command: echo "text" | piper --model pl_PL --output_file output.wav
        # Potem konwersja do OGG
        wav_path = output_path.with_suffix(".wav")
        
        try:
            # Piper
            process = subprocess.run(
                ["piper", "--model", "pl_PL-gosia-medium", "--output_file", str(wav_path)],
                input=text.encode("utf-8"),
                capture_output=True,
                timeout=30,
            )
            
            if process.returncode != 0:
                # Fallback: użyj espeak
                subprocess.run(
                    ["espeak", "-vpl", "-w", str(wav_path), text],
                    timeout=30,
                    check=True,
                )
                
            # Konwertuj do OGG
            subprocess.run(
                ["ffmpeg", "-y", "-i", str(wav_path), "-c:a", "libopus", str(output_path)],
                capture_output=True,
                timeout=30,
            )
            
            # Usuń WAV
            wav_path.unlink(missing_ok=True)
            
            if output_path.exists():
                return output_path
                
        except Exception as e:
            logger.error(f"[VOICE] Piper error: {e}")
            
        return None
        
    def _generate_edge(self, text: str, output_path: Path) -> Optional[Path]:
        """Generuj przez Edge TTS."""
        try:
            import edge_tts
            import asyncio
            
            async def generate():
                communicate = edge_tts.Communicate(text, "pl-PL-ZofiaNeural")
                await communicate.save(str(output_path))
                
            asyncio.run(generate())
            
            if output_path.exists():
                return output_path
                
        except ImportError:
            logger.error("[VOICE] edge-tts not installed: pip install edge-tts")
        except Exception as e:
            logger.error(f"[VOICE] Edge TTS error: {e}")
            
        return None
        
    def _generate_deepseek(self, text: str, output_path: Path) -> Optional[Path]:
        """Generuj przez DeepSeek Voice API."""
        # TODO: Implementacja gdy DeepSeek udostępni Voice API
        logger.warning("[VOICE] DeepSeek TTS not yet implemented")
        return None
