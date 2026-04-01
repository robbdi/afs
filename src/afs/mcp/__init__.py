"""AFS MCP server package.

Re-exports public API for backward compatibility with code importing
from ``afs.mcp_server``.
"""

from .registry import (
    CORE_PROMPT_NAMES,
    CORE_RESOURCE_PREFIXES,
    CORE_RESOURCE_URIS,
    ExtensionMCPStatus,
    MCPExtensionContribution,
    MCPPromptDefinition,
    MCPResourceDefinition,
    MCPToolDefinition,
    MCPToolRegistry,
    PromptHandler,
    ResourceHandler,
    ToolHandler,
)
from .transport import (
    LEGACY_PROTOCOL_VERSION,
    PROTOCOL_VERSION,
    SERVER_NAME,
    SERVER_VERSION,
    SUPPORTED_PROTOCOL_VERSIONS,
    error_response,
    read_message,
    success_response,
    write_message,
)

__all__ = [
    # Registry types
    "MCPToolDefinition",
    "MCPResourceDefinition",
    "MCPPromptDefinition",
    "MCPExtensionContribution",
    "ExtensionMCPStatus",
    "MCPToolRegistry",
    "ToolHandler",
    "ResourceHandler",
    "PromptHandler",
    # Registry constants
    "CORE_RESOURCE_URIS",
    "CORE_RESOURCE_PREFIXES",
    "CORE_PROMPT_NAMES",
    # Transport
    "read_message",
    "write_message",
    "error_response",
    "success_response",
    # Protocol
    "SERVER_NAME",
    "SERVER_VERSION",
    "PROTOCOL_VERSION",
    "LEGACY_PROTOCOL_VERSION",
    "SUPPORTED_PROTOCOL_VERSIONS",
]
