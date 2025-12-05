"""
ALFA DELTA v1 — SENDER
SMTP sender dla Delta Chat.
"""

from typing import Optional, Dict, Any, List
import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from pathlib import Path

logger = logging.getLogger("ALFA.Delta.Sender")


class DeltaSender:
    """
    SMTP Sender dla Delta Chat.
    """
    
    def __init__(
        self,
        smtp_host: str,
        smtp_port: int = 587,
        email_address: str = "",
        password: str = "",
        use_tls: bool = True
    ):
        """
        Args:
            smtp_host: Host SMTP
            smtp_port: Port SMTP (587 dla TLS)
            email_address: Adres email
            password: Hasło
            use_tls: Czy używać TLS
        """
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.email_address = email_address
        self.password = password
        self.use_tls = use_tls
        
        logger.info(f"DeltaSender initialized ({smtp_host})")
    
    def send(
        self,
        to: str,
        text: str,
        subject: str = "",
        attachments: Optional[List[str]] = None
    ) -> bool:
        """
        Wysyła wiadomość.
        
        Args:
            to: Adres odbiorcy
            text: Treść wiadomości
            subject: Temat (opcjonalny)
            attachments: Lista ścieżek do załączników
            
        Returns:
            True jeśli wysłano
        """
        try:
            # Create message
            if attachments:
                msg = MIMEMultipart()
                msg.attach(MIMEText(text, "plain", "utf-8"))
                
                for attachment_path in attachments:
                    self._attach_file(msg, attachment_path)
            else:
                msg = MIMEText(text, "plain", "utf-8")
            
            msg["From"] = self.email_address
            msg["To"] = to
            msg["Subject"] = subject or "ALFA Message"
            
            # Send
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                if self.use_tls:
                    server.starttls()
                
                server.login(self.email_address, self.password)
                server.send_message(msg)
            
            logger.info(f"Message sent to {to}")
            return True
            
        except Exception as e:
            logger.error(f"Send failed: {e}")
            return False
    
    def send_voice(
        self,
        to: str,
        audio_path: str,
        text: str = ""
    ) -> bool:
        """
        Wysyła wiadomość głosową (OGG).
        
        Args:
            to: Adres odbiorcy
            audio_path: Ścieżka do pliku audio
            text: Opcjonalny tekst
            
        Returns:
            True jeśli wysłano
        """
        # Delta Chat wymaga OGG Opus dla voice messages
        audio_file = Path(audio_path)
        
        if not audio_file.exists():
            logger.error(f"Audio file not found: {audio_path}")
            return False
        
        # Convert to OGG if needed
        if audio_file.suffix.lower() != ".ogg":
            try:
                from ..voice.audio_utils import convert_to_ogg
                ogg_path = convert_to_ogg(str(audio_file))
                if ogg_path:
                    audio_path = ogg_path
            except ImportError:
                logger.warning("Cannot convert to OGG, sending as-is")
        
        return self.send(
            to=to,
            text=text or "[Voice Message]",
            attachments=[audio_path]
        )
    
    def _attach_file(self, msg: MIMEMultipart, file_path: str) -> None:
        """Dodaje załącznik do wiadomości."""
        file = Path(file_path)
        
        if not file.exists():
            logger.warning(f"Attachment not found: {file_path}")
            return
        
        with open(file, "rb") as f:
            part = MIMEBase("application", "octet-stream")
            part.set_payload(f.read())
        
        encoders.encode_base64(part)
        part.add_header(
            "Content-Disposition",
            f"attachment; filename= {file.name}"
        )
        
        msg.attach(part)
    
    def test_connection(self) -> bool:
        """Testuje połączenie SMTP."""
        try:
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                if self.use_tls:
                    server.starttls()
                server.login(self.email_address, self.password)
                logger.info("SMTP connection test successful")
                return True
        except Exception as e:
            logger.error(f"SMTP connection test failed: {e}")
            return False
    
    def status(self) -> Dict[str, Any]:
        """Status sendera."""
        return {
            "host": self.smtp_host,
            "port": self.smtp_port,
            "email": self.email_address,
            "use_tls": self.use_tls
        }
