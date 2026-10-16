"""One exception type carrying the HTTP answer, so routes map it in one place."""


class ToolFilesError(Exception):
    def __init__(self, status: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message


class StoreUnavailable(RuntimeError):
    """The grant store cannot be read or written. Never an empty store: an
    admin shown no grants during an outage would start re-granting."""


class DirectoryUnavailable(RuntimeError):
    """The member directory cannot be listed, so team sizes are unknown."""
