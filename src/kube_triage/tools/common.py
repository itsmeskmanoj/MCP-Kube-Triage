import logging

from kube_triage.errors import OperationsError
from kube_triage.models import ErrorComponent, ToolResultEnvelope

logger = logging.getLogger(__name__)


def error_result(
    error: BaseException,
    default_component: ErrorComponent,
) -> ToolResultEnvelope:
    if isinstance(error, OperationsError):
        return ToolResultEnvelope.failure(
            error.component,
            error.code,
            error.message,
            retryable=error.retryable,
        )
    logger.exception("Unexpected MCP tool failure", exc_info=error)
    return ToolResultEnvelope.failure(
        default_component,
        "unexpected_error",
        "The read-only operation failed unexpectedly",
    )
