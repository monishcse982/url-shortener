from http import HTTPStatus


class ApplicationError(Exception):
    """Base class for expected application-level failures."""

    code = "application_error"
    status_code = HTTPStatus.INTERNAL_SERVER_ERROR

    def __init__(
        self,
        message: str,
        *,
        details: dict[str, str] | None = None,
    ) -> None:
        self.details = details or {}
        super().__init__(message)


class UnauthorizedError(ApplicationError):
    code = "unauthorized"
    status_code = HTTPStatus.UNAUTHORIZED

    def __init__(
        self,
        *,
        message: str,
    ) -> None:
        super().__init__(message)


class ForbiddenError(ApplicationError):
    code = "forbidden"
    status_code = HTTPStatus.FORBIDDEN

    def __init__(self) -> None:
        super().__init__("You do not have access to this link")


class ShortCodeConflictError(ApplicationError):
    code = "short_code_already_exists"
    status_code = HTTPStatus.BAD_REQUEST

    def __init__(self, short_code: str) -> None:
        self.short_code = short_code
        super().__init__(
            "Short code already exists",
            details={"short_code": short_code},
        )


class ResourceNotFoundError(ApplicationError):
    code = "resource_not_found"
    status_code = HTTPStatus.NOT_FOUND

    def __init__(self, *, resource: str, identifier: str) -> None:
        self.resource = resource
        self.identifier = identifier
        super().__init__(
            f"{resource} not found",
            details={
                "resource": resource,
                "identifier": identifier,
            },
        )


class ResourceGoneError(ApplicationError):
    status_code = HTTPStatus.GONE

    def __init__(
        self,
        *,
        resource: str,
        identifier: str,
        reason: str,
        code: str = "resource_gone",
    ) -> None:
        self.resource = resource
        self.identifier = identifier
        self.reason = reason
        self.code = code
        super().__init__(
            reason,
            details={
                "resource": resource,
                "identifier": identifier,
            },
        )
