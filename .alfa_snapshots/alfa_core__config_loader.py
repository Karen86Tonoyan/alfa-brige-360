# ═══════════════════════════════════════════════════════════════════════════
# ALFA BRIDGE 360° — Configuration Loader
# ═══════════════════════════════════════════════════════════════════════════
"""
Load and manage ALFA Bridge configuration from TOML files.

Usage:
    from alfa_core.config_loader import config, get_agent, get_agents_for_task
    
    # Get default agent
    agent = config.default_agent
    
    # Get specific agent
    claude = get_agent("claude")
    
    # Get agents for task type
    coding_agents = get_agents_for_task("coding")
"""

import os
import re
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

# Try to import tomllib (Python 3.11+) or tomli
try:
    import tomllib
except ImportError:
    try:
        import tomli as tomllib
    except ImportError:
        tomllib = None

LOG = logging.getLogger("alfa.config")

# ═══════════════════════════════════════════════════════════════════════════
# DATA CLASSES
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class Agent:
    """AI Agent configuration."""
    name: str
    provider: str
    model: str
    base_url: str
    enabled: bool = True
    default: bool = False
    description: str = ""
    local: bool = False
    env: Dict[str, str] = field(default_factory=dict)
    
    @property
    def api_key_env_var(self) -> str:
        """Get environment variable name for API key."""
        provider_map = {
            "google": "GEMINI_API_KEY",
            "anthropic": "ANTHROPIC_API_KEY",
            "deepseek": "DEEPSEEK_API_KEY",
            "openrouter": "OPENROUTER_API_KEY",
            "groq": "GROQ_API_KEY",
            "openai": "OPENAI_API_KEY",
            "ollama": None,  # No key needed
        }
        return provider_map.get(self.provider)
    
    @property
    def api_key(self) -> Optional[str]:
        """Get API key from environment."""
        env_var = self.api_key_env_var
        if env_var:
            return os.getenv(env_var)
        return None
    
    @property
    def is_available(self) -> bool:
        """Check if agent is available (enabled + has API key or is local)."""
        if not self.enabled:
            return False
        if self.local:
            return True
        return self.api_key is not None


@dataclass
class SecurityConfig:
    """Security settings."""
    enabled: bool = True
    max_tokens_per_request: int = 100000
    max_requests_per_minute: int = 60
    block_sensitive_data: bool = True
    blocked_patterns: List[str] = field(default_factory=list)
    redact_patterns: List[str] = field(default_factory=list)


@dataclass
class SandboxConfig:
    """Sandbox execution settings."""
    enabled: bool = True
    timeout: int = 30
    max_memory_mb: int = 512
    max_output_size: int = 100000
    allowed_modules: Dict[str, List[str]] = field(default_factory=dict)


@dataclass 
class ServerConfig:
    """API server settings."""
    host: str = "0.0.0.0"
    port: int = 8000
    workers: int = 4
    cors_origins: List[str] = field(default_factory=lambda: ["*"])
    api_prefix: str = "/api/v1"


@dataclass
class RoutingConfig:
    """Agent routing settings."""
    default: str = "gemini"
    fallback_chain: List[str] = field(default_factory=list)
    auto_enabled: bool = True
    tasks: Dict[str, List[str]] = field(default_factory=dict)


# ═══════════════════════════════════════════════════════════════════════════
# MAIN CONFIG CLASS
# ═══════════════════════════════════════════════════════════════════════════

class ALFAConfig:
    """Main configuration manager."""
    
    def __init__(self, config_path: Optional[Path] = None):
        self._agents: Dict[str, Agent] = {}
        self._routing = RoutingConfig()
        self._security = SecurityConfig()
        self._sandbox = SandboxConfig()
        self._server = ServerConfig()
        self._raw: Dict[str, Any] = {}
        
        if config_path:
            self.load(config_path)
        else:
            self._find_and_load()
    
    def _find_and_load(self):
        """Find and load config file."""
        search_paths = [
            Path("config/alfa_bridge.toml"),
            Path("alfa_bridge.toml"),
            Path("config.toml"),
            Path.home() / ".alfa" / "config.toml",
        ]
        
        for path in search_paths:
            if path.exists():
                self.load(path)
                return
        
        LOG.warning("No config file found, using defaults")
    
    def load(self, path: Path):
        """Load configuration from TOML file."""
        if tomllib is None:
            LOG.error("tomllib/tomli not available, install with: pip install tomli")
            return
        
        path = Path(path)
        if not path.exists():
            LOG.warning(f"Config file not found: {path}")
            return
        
        try:
            with open(path, "rb") as f:
                self._raw = tomllib.load(f)
            
            self._parse_agents()
            self._parse_routing()
            self._parse_security()
            self._parse_sandbox()
            self._parse_server()
            
            LOG.info(f"Loaded config from {path}")
            LOG.info(f"Available agents: {list(self._agents.keys())}")
            
        except Exception as e:
            LOG.error(f"Failed to load config: {e}")
    
    def _parse_agents(self):
        """Parse agent configurations."""
        for agent_data in self._raw.get("agents", []):
            agent = Agent(
                name=agent_data.get("name", "unknown"),
                provider=agent_data.get("provider", "unknown"),
                model=agent_data.get("model", ""),
                base_url=agent_data.get("base_url", ""),
                enabled=agent_data.get("enabled", True),
                default=agent_data.get("default", False),
                description=agent_data.get("description", ""),
                local=agent_data.get("local", False),
                env=agent_data.get("env", {}),
            )
            self._agents[agent.name] = agent
    
    def _parse_routing(self):
        """Parse routing configuration."""
        routing = self._raw.get("routing", {})
        self._routing = RoutingConfig(
            default=routing.get("default", "gemini"),
            fallback_chain=routing.get("fallback_chain", []),
            auto_enabled=routing.get("auto", {}).get("enabled", True),
            tasks=routing.get("tasks", {}),
        )
    
    def _parse_security(self):
        """Parse security configuration."""
        security = self._raw.get("security", {})
        filters = security.get("filters", {})
        self._security = SecurityConfig(
            enabled=security.get("enabled", True),
            max_tokens_per_request=security.get("max_tokens_per_request", 100000),
            max_requests_per_minute=security.get("max_requests_per_minute", 60),
            block_sensitive_data=security.get("block_sensitive_data", True),
            blocked_patterns=filters.get("blocked_patterns", []),
            redact_patterns=filters.get("redact_patterns", []),
        )
    
    def _parse_sandbox(self):
        """Parse sandbox configuration."""
        sandbox = self._raw.get("sandbox", {})
        self._sandbox = SandboxConfig(
            enabled=sandbox.get("enabled", True),
            timeout=sandbox.get("timeout", 30),
            max_memory_mb=sandbox.get("max_memory_mb", 512),
            max_output_size=sandbox.get("max_output_size", 100000),
            allowed_modules=sandbox.get("allowed_modules", {}),
        )
    
    def _parse_server(self):
        """Parse server configuration."""
        server = self._raw.get("server", {})
        self._server = ServerConfig(
            host=server.get("host", "0.0.0.0"),
            port=server.get("port", 8000),
            workers=server.get("workers", 4),
            cors_origins=server.get("cors_origins", ["*"]),
            api_prefix=server.get("api_prefix", "/api/v1"),
        )
    
    # ─────────────────────────────────────────────────────────────────────
    # PROPERTIES
    # ─────────────────────────────────────────────────────────────────────
    
    @property
    def agents(self) -> Dict[str, Agent]:
        return self._agents
    
    @property
    def enabled_agents(self) -> Dict[str, Agent]:
        return {k: v for k, v in self._agents.items() if v.enabled}
    
    @property
    def available_agents(self) -> Dict[str, Agent]:
        return {k: v for k, v in self._agents.items() if v.is_available}
    
    @property
    def default_agent(self) -> Optional[Agent]:
        # First try explicitly marked default
        for agent in self._agents.values():
            if agent.default and agent.is_available:
                return agent
        
        # Fall back to routing default
        default_name = self._routing.default
        if default_name in self._agents:
            agent = self._agents[default_name]
            if agent.is_available:
                return agent
        
        # Fall back to first available
        for agent in self._agents.values():
            if agent.is_available:
                return agent
        
        return None
    
    @property
    def routing(self) -> RoutingConfig:
        return self._routing
    
    @property
    def security(self) -> SecurityConfig:
        return self._security
    
    @property
    def sandbox(self) -> SandboxConfig:
        return self._sandbox
    
    @property
    def server(self) -> ServerConfig:
        return self._server
    
    # ─────────────────────────────────────────────────────────────────────
    # METHODS
    # ─────────────────────────────────────────────────────────────────────
    
    def get_agent(self, name: str) -> Optional[Agent]:
        """Get agent by name."""
        return self._agents.get(name)
    
    def get_agents_for_task(self, task: str) -> List[Agent]:
        """Get agents suitable for a task type."""
        agent_names = self._routing.tasks.get(task, [])
        agents = []
        
        for name in agent_names:
            agent = self._agents.get(name)
            if agent and agent.is_available:
                agents.append(agent)
        
        # Fall back to default if no agents found
        if not agents and self.default_agent:
            agents = [self.default_agent]
        
        return agents
    
    def get_fallback_agent(self, exclude: List[str] = None) -> Optional[Agent]:
        """Get next available fallback agent."""
        exclude = exclude or []
        
        for name in self._routing.fallback_chain:
            if name in exclude:
                continue
            agent = self._agents.get(name)
            if agent and agent.is_available:
                return agent
        
        return None
    
    def validate_prompt(self, prompt: str) -> tuple[bool, Optional[str]]:
        """Validate prompt against security rules."""
        if not self._security.enabled:
            return True, None
        
        for pattern in self._security.blocked_patterns:
            if re.search(pattern, prompt):
                return False, f"Blocked pattern detected: {pattern}"
        
        return True, None
    
    def redact_sensitive(self, text: str) -> str:
        """Redact sensitive information from text."""
        if not self._security.enabled:
            return text
        
        for pattern in self._security.redact_patterns:
            text = re.sub(pattern, "[REDACTED]", text)
        
        return text


# ═══════════════════════════════════════════════════════════════════════════
# SINGLETON & HELPERS
# ═══════════════════════════════════════════════════════════════════════════

_config: Optional[ALFAConfig] = None


def get_config() -> ALFAConfig:
    """Get or create config singleton."""
    global _config
    if _config is None:
        _config = ALFAConfig()
    return _config


def get_agent(name: str) -> Optional[Agent]:
    """Get agent by name."""
    return get_config().get_agent(name)


def get_agents_for_task(task: str) -> List[Agent]:
    """Get agents for task type."""
    return get_config().get_agents_for_task(task)


def get_default_agent() -> Optional[Agent]:
    """Get default agent."""
    return get_config().default_agent


# Alias for convenience
config = property(get_config)


__all__ = [
    "ALFAConfig",
    "Agent",
    "SecurityConfig",
    "SandboxConfig",
    "ServerConfig",
    "RoutingConfig",
    "get_config",
    "get_agent",
    "get_agents_for_task",
    "get_default_agent",
]
