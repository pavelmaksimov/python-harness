class AppError(Exception):
    pass


class NotFoundError(AppError):
    def __init__(self, object_name: str, id: object) -> None:
        self.object_name = object_name
        self.id = id

    def __str__(self) -> str:
        return f"{self.object_name}={self.id} not found"


class AuthError(AppError):
    pass


class ExternalApiError(AppError):
    def __init__(self, message: str, url: str) -> None:
        self.message = message
        self.url = url

    def __str__(self) -> str:
        return f"{self.message} ({self.url})"


class ServerError(ExternalApiError):
    pass


class ClientError(ExternalApiError):
    pass


class ExternalHTTPConnectionError(ExternalApiError):
    pass
