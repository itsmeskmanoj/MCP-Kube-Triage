from kube_triage.models import ErrorComponent


class OperationsError(Exception):
    def __init__(
        self,
        component: ErrorComponent,
        code: str,
        message: str,
        *,
        retryable: bool = False,
    ) -> None:
        super().__init__(message)
        self.component = component
        self.code = code
        self.message = message
        self.retryable = retryable


class ValidationError(OperationsError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(ErrorComponent.VALIDATION, code, message)


class DatabaseError(OperationsError):
    def __init__(self, code: str, message: str, *, retryable: bool = False) -> None:
        super().__init__(ErrorComponent.DATABASE, code, message, retryable=retryable)


class PrometheusError(OperationsError):
    def __init__(self, code: str, message: str, *, retryable: bool = False) -> None:
        super().__init__(ErrorComponent.PROMETHEUS, code, message, retryable=retryable)
