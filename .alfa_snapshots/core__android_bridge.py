"""
ALFA MANUS - Android Integration
Kotlin wrapper dla integracji z aplikacją Android.
"""

# Ten plik definiuje API które Android app będzie wywoływać

from dataclasses import dataclass
from typing import Dict, List, Optional, Any
from enum import Enum
import json


class AndroidCommand(Enum):
    """Komendy z Androida."""
    ANALYZE_CODE = "analyze_code"
    BUILD_PROJECT = "build_project"
    STORE_SECRET = "store_secret"
    REVEAL_SECRET = "reveal_secret"
    GET_STATUS = "get_status"
    CHECK_NETWORK = "check_network"
    GENERATE_NOISE = "generate_noise"
    SWITCH_MODE = "switch_mode"


@dataclass
class AndroidRequest:
    """Request z aplikacji Android."""
    command: AndroidCommand
    payload: Dict[str, Any]
    timestamp: str
    device_id: str


@dataclass  
class AndroidResponse:
    """Response dla aplikacji Android."""
    success: bool
    data: Dict[str, Any]
    visible_to_observers: bool  # Czy to widzi inwigilator
    
    def to_json(self) -> str:
        return json.dumps({
            "success": self.success,
            "data": self.data,
            "public": self.visible_to_observers
        })


class AndroidBridge:
    """
    Most między Androidem a ALFA MANUS.
    """
    
    def __init__(self):
        from .alfa_manus import get_manus, ManusMode
        self.manus = get_manus()
    
    def handle_request(self, request: AndroidRequest) -> AndroidResponse:
        """Obsłuż request z Androida."""
        
        handlers = {
            AndroidCommand.ANALYZE_CODE: self._handle_analyze,
            AndroidCommand.BUILD_PROJECT: self._handle_build,
            AndroidCommand.STORE_SECRET: self._handle_store,
            AndroidCommand.REVEAL_SECRET: self._handle_reveal,
            AndroidCommand.GET_STATUS: self._handle_status,
            AndroidCommand.CHECK_NETWORK: self._handle_network,
            AndroidCommand.GENERATE_NOISE: self._handle_noise,
            AndroidCommand.SWITCH_MODE: self._handle_mode,
        }
        
        handler = handlers.get(request.command)
        if handler:
            return handler(request.payload)
        
        return AndroidResponse(False, {"error": "Unknown command"}, True)
    
    def _handle_analyze(self, payload: Dict) -> AndroidResponse:
        code = payload.get("code", "")
        result = self.manus.analyze(code)
        return AndroidResponse(True, result, True)  # Analiza jest publiczna
    
    def _handle_build(self, payload: Dict) -> AndroidResponse:
        import asyncio
        description = payload.get("description", "")
        
        async def _build():
            plan = await self.manus.plan(description)
            result = await self.manus.build(plan)
            return result
        
        result = asyncio.run(_build())
        return AndroidResponse(True, result, True)
    
    def _handle_store(self, payload: Dict) -> AndroidResponse:
        data = payload.get("data", {})
        category = payload.get("category", "general")
        secret_id = self.manus.store_secret(data, category)
        return AndroidResponse(True, {"secret_id": secret_id}, False)  # Nie widoczne!
    
    def _handle_reveal(self, payload: Dict) -> AndroidResponse:
        secret_id = payload.get("secret_id", "")
        result = self.manus.reveal_secret(secret_id)
        if result:
            return AndroidResponse(True, result, False)  # Nie widoczne!
        return AndroidResponse(False, {"error": "Not available or online"}, True)
    
    def _handle_status(self, payload: Dict) -> AndroidResponse:
        status = self.manus.status()
        # Status jest publiczny ale może być fałszywy (szum)
        return AndroidResponse(True, status, True)
    
    def _handle_network(self, payload: Dict) -> AndroidResponse:
        is_offline = self.manus.vault.check_network()
        return AndroidResponse(True, {"offline": is_offline}, True)
    
    def _handle_noise(self, payload: Dict) -> AndroidResponse:
        fake_state = self.manus.noise.get_fake_state()
        return AndroidResponse(True, fake_state, True)  # To jest szum - publiczne
    
    def _handle_mode(self, payload: Dict) -> AndroidResponse:
        from .alfa_manus import ManusMode
        mode_name = payload.get("mode", "ONLINE")
        mode = ManusMode[mode_name]
        self.manus.switch_mode(mode)
        return AndroidResponse(True, {"mode": mode.name}, False)


# API dla Kotlin/JNI
def process_android_command(command_json: str) -> str:
    """
    Główna funkcja wywoływana z Kotlin przez JNI/Chaquopy.
    
    Args:
        command_json: JSON string z AndroidRequest
        
    Returns:
        JSON string z AndroidResponse
    """
    try:
        data = json.loads(command_json)
        request = AndroidRequest(
            command=AndroidCommand(data["command"]),
            payload=data.get("payload", {}),
            timestamp=data.get("timestamp", ""),
            device_id=data.get("device_id", "")
        )
        
        bridge = AndroidBridge()
        response = bridge.handle_request(request)
        return response.to_json()
        
    except Exception as e:
        return json.dumps({
            "success": False,
            "data": {"error": str(e)},
            "public": True
        })
