"""
CERBER PHANTOM - Integracja z ALFA_SEAT
Automatyczne maskowanie wszystkich requestów.
"""

from __future__ import annotations

import functools
from typing import Callable, Any, Dict, Optional
from .cerber_phantom import get_cerber, cerber_check, cerber_mask_request, CerberPhantom


def cerber_protected(func: Callable) -> Callable:
    """
    Dekorator - ochrona funkcji przez Cerbera.
    Blokuje wywołanie jeśli Cerber uzna za niebezpieczne.
    
    Usage:
        @cerber_protected
        async def send_email(to: str, body: str):
            ...
    """
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        # Zbuduj opis akcji
        action = f"{func.__name__}({', '.join(str(a)[:20] for a in args)})"
        
        allowed, reason = cerber_check(action)
        if not allowed:
            raise PermissionError(f"CERBER BLOCKED: {reason}")
        
        return await func(*args, **kwargs)
    
    return wrapper


def cerber_masked_request(func: Callable) -> Callable:
    """
    Dekorator - maskuje wszystkie wychodzące requesty.
    Podmienia nagłówki na fałszywe.
    
    Usage:
        @cerber_masked_request
        async def fetch_data(url: str, headers: dict):
            ...
    """
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        # Znajdź headers w kwargs
        if 'headers' in kwargs:
            kwargs['headers'] = cerber_mask_request(kwargs['headers'])
        
        return await func(*args, **kwargs)
    
    return wrapper


class CerberMiddleware:
    """
    Middleware dla FastAPI/Starlette.
    Automatycznie chroni wszystkie endpointy.
    """
    
    def __init__(self, app, cerber: Optional[CerberPhantom] = None):
        self.app = app
        self.cerber = cerber or get_cerber()
    
    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            # Sprawdź request
            path = scope.get("path", "")
            method = scope.get("method", "GET")
            
            action = f"HTTP {method} {path}"
            allowed, reason = self.cerber.check(action)
            
            if not allowed:
                # Zwróć 403 bez ujawniania szczegółów
                response = {
                    "type": "http.response.start",
                    "status": 403,
                    "headers": [(b"content-type", b"application/json")],
                }
                await send(response)
                await send({
                    "type": "http.response.body",
                    "body": b'{"error": "Access denied"}',
                })
                return
            
            # Zamaskuj odpowiedź - usuń prawdziwe nagłówki serwera
            async def masked_send(message):
                if message["type"] == "http.response.start":
                    # Usuń nagłówki które mogą zdradzić tożsamość
                    headers = [
                        (k, v) for k, v in message.get("headers", [])
                        if k.lower() not in [b"server", b"x-powered-by", b"x-real-ip"]
                    ]
                    # Dodaj fałszywe
                    headers.append((b"server", b"nginx/1.24.0"))
                    message["headers"] = headers
                await send(message)
            
            await self.app(scope, receive, masked_send)
        else:
            await self.app(scope, receive, send)


def setup_cerber_protection(app):
    """
    Szybka konfiguracja Cerbera dla FastAPI.
    
    Usage:
        from fastapi import FastAPI
        from security.cerber_integration import setup_cerber_protection
        
        app = FastAPI()
        setup_cerber_protection(app)
    """
    from fastapi import Request
    from starlette.middleware.base import BaseHTTPMiddleware
    
    cerber = get_cerber()
    
    class CerberFastAPIMiddleware(BaseHTTPMiddleware):
        async def dispatch(self, request: Request, call_next):
            # Pobierz zamaskowane nagłówki
            masked_headers = cerber.get_masked_request_headers()
            
            # Sprawdź request
            action = f"{request.method} {request.url.path}"
            allowed, reason = cerber.check(action)
            
            if not allowed:
                from fastapi.responses import JSONResponse
                return JSONResponse(
                    status_code=403,
                    content={"error": "Access denied", "service": "gateway"}
                )
            
            response = await call_next(request)
            
            # Zamaskuj response headers
            response.headers["Server"] = "nginx/1.24.0"
            response.headers.pop("X-Powered-By", None)
            
            return response
    
    app.add_middleware(CerberFastAPIMiddleware)
    return cerber
