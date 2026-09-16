class DomainError(Exception):
    """Base class for expected application errors."""


class ValidationError(DomainError):
    pass


class RecordNotFoundError(DomainError):
    pass
