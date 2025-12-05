"""
ALFA_CORE_KERNEL v3.0 — ROUTER
Routing requestów do odpowiednich providerów i handlerów.
"""

from typing import Optional, Dict, Any, Callable, List
import logging
import re
from enum import Enum, auto

logger = logging.getLogger("ALFA.Router")


class RouteType(Enum):
    """Typ routingu."""
    CHAT = auto()        # Standardowy chat
    COMMAND = auto()     # Komenda systemowa
    CODE = auto()        # Generowanie/analiza kodu
    VOICE = auto()       # Operacje głosowe
    DELTA = auto()       # Delta Chat
    MEMORY = auto()      # Operacje pamięci
    SYSTEM = auto()      # Operacje systemowe


class Route:
    """Definicja pojedynczej trasy."""
    
    def __init__(
        self,
        name: str,
        route_type: RouteType,
        pattern: Optional[str] = None,
        handler: Optional[Callable] = None,
        provider: Optional[str] = None,
        priority: int = 0
    ):
        self.name = name
        self.route_type = route_type
        self.pattern = re.compile(pattern, re.IGNORECASE) if pattern else None
        self.handler = handler
        self.provider = provider
        self.priority = priority
    
    def matches(self, text: str) -> bool:
        """Sprawdza czy tekst pasuje do trasy."""
        if self.pattern:
            return bool(self.pattern.search(text))
        return False


class Router:
    """
    Router kieruje requesty do odpowiednich handlerów/providerów.
    """
    
    def __init__(self):
        self.routes: List[Route] = []
        self._default_route: Optional[Route] = None
        self._setup_default_routes()
    
    def _setup_default_routes(self) -> None:
        """Konfiguruje domyślne trasy."""
        # Komendy systemowe
        self.add_route(Route(
            name="system_command",
            route_type=RouteType.COMMAND,
            pattern=r"^/(status|help|exit|quit|clear|reset)",
            priority=100
        ))
        
        # Kod
        self.add_route(Route(
            name="code_request",
            route_type=RouteType.CODE,
            pattern=r"(napisz kod|write code|python|javascript|```|function|def |class )",
            priority=50
        ))
        
        # Voice
        self.add_route(Route(
            name="voice_request",
            route_type=RouteType.VOICE,
            pattern=r"(powiedz|mów|głos|voice|speak|say|audio)",
            priority=40
        ))
        
        # Memory
        self.add_route(Route(
            name="memory_request",
            route_type=RouteType.MEMORY,
            pattern=r"(pamiętaj|zapamiętaj|przypomnij|remember|recall|memory)",
            priority=30
        ))
        
        # Default chat
        self._default_route = Route(
            name="default_chat",
            route_type=RouteType.CHAT,
            priority=0
        )
    
    def add_route(self, route: Route) -> None:
        """Dodaje trasę."""
        self.routes.append(route)
        # Sortuj po priorytecie (wyższy = sprawdzany pierwszy)
        self.routes.sort(key=lambda r: r.priority, reverse=True)
        logger.debug(f"Added route: {route.name} (priority: {route.priority})")
    
    def remove_route(self, name: str) -> bool:
        """Usuwa trasę po nazwie."""
        for i, route in enumerate(self.routes):
            if route.name == name:
                self.routes.pop(i)
                logger.debug(f"Removed route: {name}")
                return True
        return False
    
    def route(self, text: str) -> Route:
        """
        Znajduje trasę dla tekstu.
        
        Args:
            text: Tekst do routing
            
        Returns:
            Pasująca trasa lub domyślna
        """
        for route in self.routes:
            if route.matches(text):
                logger.debug(f"Matched route: {route.name}")
                return route
        
        logger.debug(f"Using default route: {self._default_route.name}")
        return self._default_route
    
    def route_with_context(
        self,
        text: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Routing z dodatkowym kontekstem.
        
        Args:
            text: Tekst do routing
            context: Dodatkowy kontekst
            
        Returns:
            Dict z informacjami o routingu
        """
        context = context or {}
        matched = self.route(text)
        
        return {
            "route": matched,
            "route_name": matched.name,
            "route_type": matched.route_type.name,
            "provider": matched.provider,
            "handler": matched.handler,
            "context": context
        }
    
    def get_route_by_name(self, name: str) -> Optional[Route]:
        """Zwraca trasę po nazwie."""
        for route in self.routes:
            if route.name == name:
                return route
        if self._default_route and self._default_route.name == name:
            return self._default_route
        return None
    
    def list_routes(self) -> List[Dict[str, Any]]:
        """Lista wszystkich tras."""
        routes = []
        for route in self.routes:
            routes.append({
                "name": route.name,
                "type": route.route_type.name,
                "pattern": route.pattern.pattern if route.pattern else None,
                "provider": route.provider,
                "priority": route.priority
            })
        if self._default_route:
            routes.append({
                "name": self._default_route.name,
                "type": self._default_route.route_type.name,
                "pattern": None,
                "provider": self._default_route.provider,
                "priority": self._default_route.priority,
                "is_default": True
            })
        return routes
    
    def status(self) -> Dict[str, Any]:
        """Status routera."""
        return {
            "total_routes": len(self.routes) + (1 if self._default_route else 0),
            "routes": self.list_routes()
        }
