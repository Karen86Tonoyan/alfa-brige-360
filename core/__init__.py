"""
ALFA_CORE / CORE v2.0
=====================
Core components for ALFA System:
- MCP Dispatcher (multi-protocol AI servers)
- Event Bus (pub/sub messaging)
- Cerber (security guardian)
- Sync Engine (LAN synchronization)
- Secure Executor (sandboxed code)
- Plugin Engine (dynamic plugins)
- Extensions Loader (module management)
"""

from .mcp_dispatcher import (
    MCPDispatcher,
    MCPServer,
    MCPRequest,
    MCPResponse,
    ServerType,
    ServerStatus,
)

from .event_bus import (
    EventBus,
    Event,
    Subscription,
    Priority,
    DeadLetterQueue,
    EventAuditLog,
    get_bus,
    publish,
)

from .cerber import (
    Cerber,
    CerberDB,
    FileInfo,
    Incident,
    IncidentLevel,
    get_cerber,
)

from .sync_engine import (
    SyncEngine,
    SyncState,
    MessageType,
    MessageEnvelope,
    Peer,
    FileEntry,
    get_sync_engine,
)

from .secure_executor import (
    SecureExecutor,
    SecurityLevel,
    ExecutionResult,
    ExecutionOutput,
    ValidationResult,
    PQXHybrid,
    get_executor,
    safe_exec,
    validate_code,
)

from .plugin_engine import (
    PluginEngine,
    PluginState,
    HookType,
    PluginManifest,
    PluginInfo,
    get_plugin_engine,
    command,
    hook,
)

from .extensions_loader import (
    ExtensionsLoader,
    ExtensionInfo,
    ExtensionConfig,
    LayerInfo,
    ConfigValidator,
    get_extensions_loader,
)

from .photos_vault_bridge import (
    PhotosVaultBridge,
    PhotoInfo,
    VaultStats,
    VaultState,
    OperationResult,
    get_photos_vault,
)

__all__ = [
    # MCP Dispatcher
    "MCPDispatcher",
    "MCPServer", 
    "MCPRequest",
    "MCPResponse",
    "ServerType",
    "ServerStatus",
    # Event Bus
    "EventBus",
    "Event",
    "Subscription",
    "Priority",
    "DeadLetterQueue",
    "EventAuditLog",
    "get_bus",
    "publish",
    # Cerber Security
    "Cerber",
    "CerberDB",
    "FileInfo",
    "Incident",
    "IncidentLevel",
    "get_cerber",
    # Sync Engine
    "SyncEngine",
    "SyncState",
    "MessageType",
    "MessageEnvelope",
    "Peer",
    "FileEntry",
    "get_sync_engine",
    # Secure Executor
    "SecureExecutor",
    "SecurityLevel",
    "ExecutionResult",
    "ExecutionOutput",
    "ValidationResult",
    "PQXHybrid",
    "get_executor",
    "safe_exec",
    "validate_code",
    # Plugin Engine
    "PluginEngine",
    "PluginState",
    "HookType",
    "PluginManifest",
    "PluginInfo",
    "get_plugin_engine",
    "command",
    "hook",
    # Extensions Loader
    "ExtensionsLoader",
    "ExtensionInfo",
    "ExtensionConfig",
    "LayerInfo",
    "ConfigValidator",
    "get_extensions_loader",
    # Photos Vault Bridge
    "PhotosVaultBridge",
    "PhotoInfo",
    "VaultStats",
    "VaultState",
    "OperationResult",
    "get_photos_vault",
]
