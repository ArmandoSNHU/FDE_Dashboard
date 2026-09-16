"""One connector per data source. Connectors know nothing about MCP or roles."""

from .base import Connector, ConnectorStatus
from .github import GitHubConnector
from .sqlite import SQLiteConnector
from .telegram import TelegramConnector

__all__ = ["Connector", "ConnectorStatus", "GitHubConnector", "SQLiteConnector", "TelegramConnector"]
