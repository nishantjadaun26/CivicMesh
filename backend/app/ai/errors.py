class AIError(Exception):
    """Sanitized error for translation into the backend's eventual API contract."""

    def __init__(self, code: str, message: str, *, retryable: bool = False):
        super().__init__(message)
        self.code = code
        self.retryable = retryable
