"""Global exception definitions."""

from app.core.error_codes import ERROR_MESSAGES, ErrorCode


class AppException(Exception):
    def __init__(
        self,
        code: ErrorCode,
        message: str | None = None,
        detail: dict | list | None = None,
        http_status: int = 400,
    ) -> None:
        self.code = code
        self.message = message or ERROR_MESSAGES.get(code, "unknown error")
        self.detail = detail
        self.http_status = http_status
        super().__init__(self.message)


class AuthException(AppException):
    def __init__(self, code: ErrorCode, message: str | None = None) -> None:
        super().__init__(code=code, message=message, http_status=401)


class ForbiddenException(AppException):
    def __init__(self, message: str | None = None) -> None:
        super().__init__(
            code=ErrorCode.AUTH_PERMISSION_DENIED,
            message=message,
            http_status=403,
        )


class NotFoundException(AppException):
    def __init__(self, code: ErrorCode = ErrorCode.NOT_FOUND, message: str | None = None) -> None:
        super().__init__(code=code, message=message, http_status=404)


class ValidationException(AppException):
    def __init__(self, message: str | None = None, detail: dict | list | None = None) -> None:
        super().__init__(
            code=ErrorCode.VALIDATION_ERROR,
            message=message,
            detail=detail,
            http_status=422,
        )
