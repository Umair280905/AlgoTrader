class BrokerAPIError(Exception):
    """Raised when the Mirage broker API returns an unrecoverable error."""

    def __init__(self, message: str, status_code: int = None, response_body: str = None):
        super().__init__(message)
        self.status_code = status_code
        self.response_body = response_body

    def __str__(self):
        base = super().__str__()
        if self.status_code:
            return f"[HTTP {self.status_code}] {base}"
        return base


class OrderRejectedError(BrokerAPIError):
    """Order was rejected by the broker."""


class InsufficientFundsError(BrokerAPIError):
    """Insufficient margin/funds to place the order."""
