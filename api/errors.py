"""Expected, client-caused failures. Rendered by one handler as the standard error envelope."""


class DomainError(Exception):
    def __init__(self, status_code: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message


def not_found(code: str, message: str) -> DomainError:
    return DomainError(404, code, message)


def conflict(code: str, message: str) -> DomainError:
    return DomainError(409, code, message)


def invalid(code: str, message: str) -> DomainError:
    return DomainError(422, code, message)
