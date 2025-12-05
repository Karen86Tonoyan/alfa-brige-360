"""
ALFA CERBER v2.0
Strażnik bezpieczeństwa - blokuje niebezpieczne komendy.
"""


class Cerber:
    """Strażnik ALFA - filtruje niebezpieczne prompty."""
    
    BLOCKED_PATTERNS = [
        "DELETE SYSTEM32",
        "FORMAT C:",
        "RM -RF /",
        "DROP TABLE",
        "EXEC(",
        "SHUTDOWN",
    ]
    
    def __init__(self):
        self.blocked_count = 0
    
    def check(self, text: str) -> bool:
        """
        Sprawdza czy prompt jest bezpieczny.
        Raises Exception jeśli wykryto zagrożenie.
        """
        upper_text = text.upper()
        
        for pattern in self.BLOCKED_PATTERNS:
            if pattern in upper_text:
                self.blocked_count += 1
                raise Exception(f"[CERBER] BLOCKED – wykryto: {pattern}")
        
        return True
    
    def status(self) -> dict:
        return {
            "active": True,
            "blocked_count": self.blocked_count,
            "patterns": len(self.BLOCKED_PATTERNS)
        }
