"""
CERBER NETWORK SHIELD
Automatyczne maskowanie ruchu sieciowego.
Wstrzykuje szum i fałszywe ślady.
"""

from __future__ import annotations

import asyncio
import random
import aiohttp
from typing import Dict, List, Optional, Any
from datetime import datetime
import json

from .cerber_phantom import get_cerber, PhantomGenerator


class NetworkShield:
    """
    Tarcza sieciowa - maskuje prawdziwy ruch
    mieszając go z fałszywymi requestami.
    """
    
    # Losowe URL-e do generowania szumu
    NOISE_URLS = [
        "https://www.google.com/search?q=weather",
        "https://www.wikipedia.org/wiki/Special:Random",
        "https://www.reddit.com/r/all",
        "https://news.ycombinator.com/",
        "https://www.github.com/trending",
        "https://stackoverflow.com/questions",
    ]
    
    def __init__(self):
        self.cerber = get_cerber()
        self.phantom = PhantomGenerator()
        self.noise_enabled = True
        self.noise_ratio = 0.3  # 30% fałszywych requestów
    
    async def masked_request(
        self,
        method: str,
        url: str,
        headers: Optional[Dict[str, str]] = None,
        data: Any = None,
        **kwargs
    ) -> aiohttp.ClientResponse:
        """
        Wykonaj zamaskowany request.
        Automatycznie dodaje fałszywe nagłówki i generuje szum.
        """
        headers = headers or {}
        
        # Pobierz fałszywą tożsamość
        identity = self.cerber.shield.get_masked_identity()
        masked_headers = {
            **headers,
            **identity.to_headers(),
            "Accept-Language": random.choice([
                "en-US,en;q=0.9",
                "de-DE,de;q=0.9",
                "fr-FR,fr;q=0.9",
                "es-ES,es;q=0.9",
                "pl-PL,pl;q=0.9",
            ]),
            "DNT": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
        }
        
        async with aiohttp.ClientSession() as session:
            # Wygeneruj szum przed prawdziwym requestem
            if self.noise_enabled and random.random() < self.noise_ratio:
                await self._generate_noise(session)
            
            # Prawdziwy request
            response = await session.request(
                method,
                url,
                headers=masked_headers,
                data=data,
                **kwargs
            )
            
            # Więcej szumu po requeście
            if self.noise_enabled and random.random() < self.noise_ratio:
                asyncio.create_task(self._generate_noise(session))
            
            return response
    
    async def _generate_noise(self, session: aiohttp.ClientSession):
        """Wygeneruj fałszywy ruch sieciowy."""
        try:
            noise_url = random.choice(self.NOISE_URLS)
            identity = self.phantom.generate_identity()
            
            async with session.get(
                noise_url,
                headers=identity.to_headers(),
                timeout=aiohttp.ClientTimeout(total=5)
            ) as resp:
                await resp.read()  # Zużyj odpowiedź
        except Exception:
            pass  # Silent fail - szum może się nie udać
    
    async def obfuscated_dns_lookup(self, domain: str) -> str:
        """
        Zamaskowane zapytanie DNS.
        Wykonuje kilka fałszywych lookupów żeby ukryć prawdziwy.
        """
        import socket
        
        # Fałszywe domeny do lookup
        decoy_domains = [
            "google.com", "facebook.com", "amazon.com",
            "microsoft.com", "apple.com", "netflix.com"
        ]
        
        results = {}
        
        # Wymieszaj prawdziwą domenę z fałszywymi
        all_domains = decoy_domains + [domain]
        random.shuffle(all_domains)
        
        for d in all_domains:
            try:
                ip = socket.gethostbyname(d)
                results[d] = ip
            except socket.gaierror:
                results[d] = None
        
        return results.get(domain, "0.0.0.0")


class TrafficObfuscator:
    """
    Zaciemniacz ruchu - dodaje opóźnienia i zmienia wzorce.
    """
    
    def __init__(self):
        self.min_delay = 0.1  # sekundy
        self.max_delay = 2.0
        self.jitter = True
    
    async def delay(self):
        """Dodaj losowe opóźnienie."""
        if self.jitter:
            delay = random.uniform(self.min_delay, self.max_delay)
            await asyncio.sleep(delay)
    
    def obfuscate_payload(self, data: bytes) -> bytes:
        """
        Zaciemnij payload dodając padding.
        Ukrywa prawdziwy rozmiar danych.
        """
        # Dodaj losowy padding
        padding_size = random.randint(16, 256)
        padding = bytes([random.randint(0, 255) for _ in range(padding_size)])
        
        # Format: [4 bytes: real size][real data][padding]
        size_bytes = len(data).to_bytes(4, 'big')
        return size_bytes + data + padding
    
    def deobfuscate_payload(self, data: bytes) -> bytes:
        """Usuń zaciemnienie z payloadu."""
        if len(data) < 4:
            return data
        real_size = int.from_bytes(data[:4], 'big')
        return data[4:4 + real_size]


class AntiFingerprint:
    """
    Anti-fingerprinting - utrudnia identyfikację przeglądarki/klienta.
    """
    
    # Losowe wartości Canvas fingerprint
    CANVAS_NOISE = [
        "data:image/png;base64,iVBORw0KGgoAAAANSUhEUg...",
        "data:image/png;base64,R0lGODlhAQABAIAAAP///...",
    ]
    
    # Losowe wartości WebGL
    WEBGL_VENDORS = [
        "Google Inc. (NVIDIA)",
        "Google Inc. (Intel)",
        "Google Inc. (AMD)",
        "Apple Inc.",
        "Mozilla",
    ]
    
    WEBGL_RENDERERS = [
        "ANGLE (NVIDIA GeForce GTX 1080)",
        "ANGLE (Intel HD Graphics 630)",
        "ANGLE (AMD Radeon RX 580)",
        "Apple M1",
        "Mesa DRI Intel",
    ]
    
    @classmethod
    def generate_fingerprint_spoof(cls) -> Dict[str, Any]:
        """Generuj fałszywy fingerprint."""
        return {
            "canvas": random.choice(cls.CANVAS_NOISE),
            "webgl_vendor": random.choice(cls.WEBGL_VENDORS),
            "webgl_renderer": random.choice(cls.WEBGL_RENDERERS),
            "timezone": random.choice([
                "America/New_York",
                "Europe/London", 
                "Europe/Berlin",
                "Asia/Tokyo",
                "Australia/Sydney"
            ]),
            "language": random.choice(["en-US", "en-GB", "de-DE", "fr-FR", "es-ES"]),
            "platform": random.choice(["Win32", "MacIntel", "Linux x86_64"]),
            "screen_resolution": random.choice([
                "1920x1080", "2560x1440", "1366x768", "1440x900"
            ]),
            "color_depth": random.choice([24, 32]),
            "hardware_concurrency": random.choice([4, 8, 12, 16]),
            "device_memory": random.choice([4, 8, 16, 32]),
        }


# Quick access
_network_shield: Optional[NetworkShield] = None

def get_network_shield() -> NetworkShield:
    global _network_shield
    if _network_shield is None:
        _network_shield = NetworkShield()
    return _network_shield


async def masked_get(url: str, **kwargs):
    """Quick masked GET request."""
    shield = get_network_shield()
    return await shield.masked_request("GET", url, **kwargs)


async def masked_post(url: str, **kwargs):
    """Quick masked POST request."""
    shield = get_network_shield()
    return await shield.masked_request("POST", url, **kwargs)
