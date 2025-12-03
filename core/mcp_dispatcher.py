#!/usr/bin/env python3
"""
ALFA_CORE / MCP DISPATCHER v2.0
================================
Central dispatcher for Model Context Protocol servers.
Handles HTTP, SSE (Server-Sent Events), and STDIO transports.

Layers:
- Creative: figma, webflow
- Knowledge: deepwiki, microsoft-docs
- Automation: apify, markitdown
- Dev: idl-vscode, pylance

Author: ALFA System / Karen86Tonoyan
"""

import json
import asyncio
import subprocess
import logging
import os
from pathlib import Path
from typing import Dict, Any, Optional, List, AsyncGenerator
from dataclasses import dataclass, field
from enum import Enum
import httpx

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] [%(levelname)s] [MCP] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


# =============================================================================
# ENUMS & DATA CLASSES
# =============================================================================

class ServerType(Enum):
    HTTP = "http"
    SSE = "sse"
    STDIO = "stdio"
    INTERNAL = "internal"


class ServerStatus(Enum):
    ONLINE = "online"
    OFFLINE = "offline"
    DEGRADED = "degraded"
    UNKNOWN = "unknown"


@dataclass
class MCPServer:
    """Represents a single MCP server configuration."""
    name: str
    type: ServerType
    layer: str
    enabled: bool = True
    description: str = ""
    url: Optional[str] = None
    command: Optional[str] = None
    args: List[str] = field(default_factory=list)
    timeout: int = 30
    healthcheck: Optional[str] = None
    auth: Optional[Dict[str, str]] = None
    status: ServerStatus = ServerStatus.UNKNOWN
    
    @classmethod
    def from_dict(cls, name: str, data: Dict[str, Any]) -> 'MCPServer':
        return cls(
            name=name,
            type=ServerType(data.get('type', 'http')),
            layer=data.get('layer', 'unknown'),
            enabled=data.get('enabled', True),
            description=data.get('description', ''),
            url=data.get('url'),
            command=data.get('command'),
            args=data.get('args', []),
            timeout=data.get('timeout', 30),
            healthcheck=data.get('healthcheck'),
            auth=data.get('auth')
        )


@dataclass
class MCPRequest:
    """MCP JSON-RPC request."""
    method: str
    params: Dict[str, Any] = field(default_factory=dict)
    id: int = 1
    
    def to_json(self) -> str:
        return json.dumps({
            "jsonrpc": "2.0",
            "method": self.method,
            "params": self.params,
            "id": self.id
        })


@dataclass
class MCPResponse:
    """MCP JSON-RPC response."""
    result: Any = None
    error: Optional[Dict[str, Any]] = None
    id: int = 1
    raw: Optional[str] = None
    
    @property
    def success(self) -> bool:
        return self.error is None
    
    @classmethod
    def from_json(cls, data: str) -> 'MCPResponse':
        try:
            parsed = json.loads(data)
            return cls(
                result=parsed.get('result'),
                error=parsed.get('error'),
                id=parsed.get('id', 1),
                raw=data
            )
        except json.JSONDecodeError as e:
            return cls(error={"code": -32700, "message": f"Parse error: {e}"}, raw=data)


# =============================================================================
# MCP DISPATCHER
# =============================================================================

class MCPDispatcher:
    """
    Central dispatcher for MCP servers.
    Manages connections, health checks, and request routing.
    """
    
    CONFIG_PATH = Path(__file__).parent.parent / "config" / "mcp_servers.json"
    
    def __init__(self, config_path: Optional[Path] = None):
        self.config_path = config_path or self.CONFIG_PATH
        self.servers: Dict[str, MCPServer] = {}
        self.layers: Dict[str, List[str]] = {}
        self.routing: Dict[str, Any] = {}
        self._http_client: Optional[httpx.AsyncClient] = None
        self._stdio_processes: Dict[str, subprocess.Popen] = {}
        self._load_config()
    
    def _load_config(self):
        """Load MCP server configuration."""
        if not self.config_path.exists():
            logger.warning(f"Config not found: {self.config_path}")
            return
        
        with open(self.config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        # Load layers
        self.layers = {
            name: layer.get('servers', [])
            for name, layer in config.get('layers', {}).items()
        }
        
        # Load servers
        for name, server_config in config.get('servers', {}).items():
            self.servers[name] = MCPServer.from_dict(name, server_config)
        
        # Load routing
        self.routing = config.get('routing', {})
        
        logger.info(f"Loaded {len(self.servers)} MCP servers in {len(self.layers)} layers")
    
    async def _get_http_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._http_client is None:
            self._http_client = httpx.AsyncClient(
                timeout=httpx.Timeout(60.0, read=120.0),
                follow_redirects=True
            )
        return self._http_client
    
    async def close(self):
        """Close all connections and processes."""
        if self._http_client:
            await self._http_client.aclose()
        
        for name, proc in self._stdio_processes.items():
            logger.info(f"Terminating STDIO process: {name}")
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
        
        self._stdio_processes.clear()
    
    # -------------------------------------------------------------------------
    # HEALTH CHECKS
    # -------------------------------------------------------------------------
    
    async def check_server_health(self, server: MCPServer) -> ServerStatus:
        """Check health of a single server."""
        if not server.enabled:
            return ServerStatus.OFFLINE
        
        try:
            if server.type == ServerType.HTTP:
                return await self._check_http_health(server)
            elif server.type == ServerType.SSE:
                return await self._check_sse_health(server)
            elif server.type == ServerType.STDIO:
                return await self._check_stdio_health(server)
            elif server.type == ServerType.INTERNAL:
                return ServerStatus.ONLINE
            else:
                return ServerStatus.UNKNOWN
        except Exception as e:
            logger.error(f"Health check failed for {server.name}: {e}")
            return ServerStatus.OFFLINE
    
    async def _check_http_health(self, server: MCPServer) -> ServerStatus:
        """Check HTTP server health."""
        client = await self._get_http_client()
        url = server.url
        if server.healthcheck:
            url = url.rstrip('/') + server.healthcheck
        
        try:
            resp = await client.get(url, timeout=5.0)
            return ServerStatus.ONLINE if resp.status_code < 400 else ServerStatus.DEGRADED
        except httpx.TimeoutException:
            return ServerStatus.DEGRADED
        except Exception:
            return ServerStatus.OFFLINE
    
    async def _check_sse_health(self, server: MCPServer) -> ServerStatus:
        """Check SSE server health (connection test only)."""
        client = await self._get_http_client()
        try:
            async with client.stream("GET", server.url, timeout=5.0) as resp:
                return ServerStatus.ONLINE if resp.status_code == 200 else ServerStatus.DEGRADED
        except Exception:
            return ServerStatus.OFFLINE
    
    async def _check_stdio_health(self, server: MCPServer) -> ServerStatus:
        """Check STDIO process health."""
        if server.name in self._stdio_processes:
            proc = self._stdio_processes[server.name]
            if proc.poll() is None:
                return ServerStatus.ONLINE
        return ServerStatus.OFFLINE
    
    async def check_all_health(self) -> Dict[str, ServerStatus]:
        """Check health of all servers."""
        results = {}
        tasks = []
        
        for name, server in self.servers.items():
            tasks.append(self.check_server_health(server))
        
        statuses = await asyncio.gather(*tasks, return_exceptions=True)
        
        for (name, server), status in zip(self.servers.items(), statuses):
            if isinstance(status, Exception):
                results[name] = ServerStatus.OFFLINE
            else:
                results[name] = status
                server.status = status
        
        return results
    
    # -------------------------------------------------------------------------
    # REQUEST EXECUTION
    # -------------------------------------------------------------------------
    
    async def execute(
        self,
        server_name: str,
        method: str,
        params: Optional[Dict[str, Any]] = None
    ) -> MCPResponse:
        """Execute MCP request on specified server."""
        if server_name not in self.servers:
            return MCPResponse(error={"code": -32600, "message": f"Unknown server: {server_name}"})
        
        server = self.servers[server_name]
        if not server.enabled:
            return MCPResponse(error={"code": -32600, "message": f"Server disabled: {server_name}"})
        
        request = MCPRequest(method=method, params=params or {})
        
        try:
            if server.type == ServerType.HTTP:
                return await self._execute_http(server, request)
            elif server.type == ServerType.SSE:
                return await self._execute_sse(server, request)
            elif server.type == ServerType.STDIO:
                return await self._execute_stdio(server, request)
            else:
                return MCPResponse(error={"code": -32600, "message": f"Unsupported type: {server.type}"})
        except Exception as e:
            logger.error(f"Execute failed for {server_name}: {e}")
            return MCPResponse(error={"code": -32603, "message": str(e)})
    
    async def _execute_http(self, server: MCPServer, request: MCPRequest) -> MCPResponse:
        """Execute HTTP MCP request."""
        client = await self._get_http_client()
        
        headers = {"Content-Type": "application/json"}
        if server.auth:
            if server.auth.get('type') == 'bearer':
                token = os.environ.get(server.auth.get('env_var', ''), '')
                if token:
                    headers["Authorization"] = f"Bearer {token}"
        
        resp = await client.post(
            server.url,
            content=request.to_json(),
            headers=headers,
            timeout=server.timeout
        )
        
        return MCPResponse.from_json(resp.text)
    
    async def _execute_sse(self, server: MCPServer, request: MCPRequest) -> MCPResponse:
        """Execute SSE MCP request (POST + stream response)."""
        client = await self._get_http_client()
        
        results = []
        async with client.stream(
            "POST",
            server.url,
            content=request.to_json(),
            headers={"Content-Type": "application/json"},
            timeout=server.timeout
        ) as resp:
            async for line in resp.aiter_lines():
                if line.startswith("data:"):
                    data = line[5:].strip()
                    if data:
                        results.append(data)
        
        # Return last complete response
        if results:
            return MCPResponse.from_json(results[-1])
        return MCPResponse(error={"code": -32600, "message": "No response from SSE stream"})
    
    async def _execute_stdio(self, server: MCPServer, request: MCPRequest) -> MCPResponse:
        """Execute STDIO MCP request."""
        # Start process if not running
        if server.name not in self._stdio_processes:
            proc = subprocess.Popen(
                [server.command] + server.args,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            self._stdio_processes[server.name] = proc
        
        proc = self._stdio_processes[server.name]
        
        # Send request
        proc.stdin.write(request.to_json() + "\n")
        proc.stdin.flush()
        
        # Read response (with timeout)
        try:
            line = proc.stdout.readline()
            return MCPResponse.from_json(line)
        except Exception as e:
            return MCPResponse(error={"code": -32603, "message": f"STDIO error: {e}"})
    
    # -------------------------------------------------------------------------
    # LAYER OPERATIONS
    # -------------------------------------------------------------------------
    
    def get_layer_servers(self, layer: str) -> List[MCPServer]:
        """Get all servers in a layer."""
        server_names = self.layers.get(layer, [])
        return [self.servers[name] for name in server_names if name in self.servers]
    
    async def execute_on_layer(
        self,
        layer: str,
        method: str,
        params: Optional[Dict[str, Any]] = None,
        parallel: bool = True
    ) -> Dict[str, MCPResponse]:
        """Execute MCP request on all servers in a layer."""
        servers = self.get_layer_servers(layer)
        if not servers:
            return {}
        
        if parallel and self.routing.get('parallel_queries', True):
            # Execute in parallel
            tasks = [
                self.execute(server.name, method, params)
                for server in servers if server.enabled
            ]
            responses = await asyncio.gather(*tasks, return_exceptions=True)
            return {
                server.name: resp if not isinstance(resp, Exception) 
                else MCPResponse(error={"code": -32603, "message": str(resp)})
                for server, resp in zip([s for s in servers if s.enabled], responses)
            }
        else:
            # Execute sequentially
            results = {}
            for server in servers:
                if server.enabled:
                    results[server.name] = await self.execute(server.name, method, params)
            return results
    
    # -------------------------------------------------------------------------
    # STATUS & INFO
    # -------------------------------------------------------------------------
    
    def get_status(self) -> Dict[str, Any]:
        """Get dispatcher status."""
        return {
            "servers": {
                name: {
                    "type": server.type.value,
                    "layer": server.layer,
                    "enabled": server.enabled,
                    "status": server.status.value,
                    "description": server.description
                }
                for name, server in self.servers.items()
            },
            "layers": self.layers,
            "routing": self.routing
        }
    
    def list_servers(self, layer: Optional[str] = None, enabled_only: bool = False) -> List[str]:
        """List server names."""
        servers = self.servers.values()
        if layer:
            servers = [s for s in servers if s.layer == layer]
        if enabled_only:
            servers = [s for s in servers if s.enabled]
        return [s.name for s in servers]


# =============================================================================
# QUICK API
# =============================================================================

_dispatcher: Optional[MCPDispatcher] = None


def get_dispatcher() -> MCPDispatcher:
    """Get global dispatcher instance."""
    global _dispatcher
    if _dispatcher is None:
        _dispatcher = MCPDispatcher()
    return _dispatcher


async def mcp_call(server: str, method: str, **params) -> MCPResponse:
    """Quick MCP call."""
    return await get_dispatcher().execute(server, method, params)


async def mcp_health() -> Dict[str, str]:
    """Quick health check."""
    statuses = await get_dispatcher().check_all_health()
    return {name: status.value for name, status in statuses.items()}


# =============================================================================
# CLI
# =============================================================================

async def _cli_main():
    """CLI entry point."""
    import sys
    
    dispatcher = get_dispatcher()
    
    if len(sys.argv) < 2:
        print("Usage: python mcp_dispatcher.py [status|health|list|call <server> <method>]")
        return
    
    cmd = sys.argv[1]
    
    if cmd == "status":
        status = dispatcher.get_status()
        print(json.dumps(status, indent=2))
    
    elif cmd == "health":
        print("Checking server health...")
        health = await mcp_health()
        for name, status in health.items():
            icon = "✅" if status == "online" else "❌" if status == "offline" else "⚠️"
            print(f"  {icon} {name}: {status}")
    
    elif cmd == "list":
        layer = sys.argv[2] if len(sys.argv) > 2 else None
        servers = dispatcher.list_servers(layer=layer)
        print(f"Servers{f' in layer {layer}' if layer else ''}:")
        for name in servers:
            server = dispatcher.servers[name]
            print(f"  - {name} ({server.type.value}) [{server.layer}]")
    
    elif cmd == "call" and len(sys.argv) >= 4:
        server_name = sys.argv[2]
        method = sys.argv[3]
        params = json.loads(sys.argv[4]) if len(sys.argv) > 4 else {}
        
        print(f"Calling {server_name}.{method}...")
        resp = await mcp_call(server_name, method, **params)
        
        if resp.success:
            print(f"Result: {json.dumps(resp.result, indent=2)}")
        else:
            print(f"Error: {resp.error}")
    
    else:
        print("Unknown command")
    
    await dispatcher.close()


if __name__ == "__main__":
    asyncio.run(_cli_main())
