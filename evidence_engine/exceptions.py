class EvidenceEngineError(Exception):
    """Base exception for the evidence engine."""


class ConfigurationError(EvidenceEngineError):
    """Raised when required configuration is missing or invalid."""


class UnsupportedConnectorError(EvidenceEngineError):
    """Raised when a request targets an unknown connector."""

    def __init__(self, connector_name: str) -> None:
        super().__init__(f"Unsupported connector: {connector_name}")
        self.connector_name = connector_name


class CollectionError(EvidenceEngineError):
    """Raised when a connector cannot collect evidence."""


class ArtifactError(EvidenceEngineError):
    """Raised when artifact creation fails."""


class StorageError(EvidenceEngineError):
    """Raised when artifact storage fails."""


class ControlError(EvidenceEngineError):
    """Raised when a control definition cannot be loaded or executed."""
