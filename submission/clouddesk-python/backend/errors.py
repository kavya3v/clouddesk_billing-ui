class IntegrationUnavailable(RuntimeError):
    """A required RAG capability has not been implemented."""

class ConfigurationError(RuntimeError):
    """Required server-side configuration is absent or invalid."""

class InvalidVector(ValueError):
    """Vector is incompatible with the configured retrieval model."""

class UpstreamError(RuntimeError):
    """Sanitized failure; never includes headers, response bodies, or credentials."""
    def __init__(self, stage: str, code: str, status_code: int | None = None):
        self.stage, self.code, self.status_code = stage, code, status_code
        super().__init__(f"{stage}: {code}" + (f" (HTTP {status_code})" if status_code else ""))

class PersistenceError(RuntimeError):
    """One or more inserts could not be confirmed; the commit state may be unknown."""
    def __init__(self):
        super().__init__("Required database writes could not be confirmed.")
