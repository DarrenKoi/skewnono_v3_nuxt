"""One exception type carrying the HTTP answer, so routes map it in one place."""


class ToolFilesError(Exception):
    def __init__(self, status: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message



class StoreUnavailable(ToolFilesError):
    """The grant store cannot be read or written. Never an empty store: an
    admin shown no grants during an outage would start re-granting."""

    def __init__(self, message: str) -> None:
        super().__init__(503, "store_unavailable", message)


class RequestChanged(ToolFilesError):
    """The request an admin acted on is gone or was replaced by a re-request
    (its request_id no longer matches). Nothing was written."""

    def __init__(self, empno: str) -> None:
        super().__init__(
            409, "request_changed", "the request was replaced or withdrawn; reload and check again"
        )
        self.empno = empno
