"""Domain exceptions.

Each failure mode named in the assessment gets its own type, so the API layer
can map it to the right status code and the agent can degrade gracefully
instead of crashing the request.
"""


class AppError(Exception):
    """Base class for all application errors."""

    status_code: int = 500
    code: str = "internal_error"

    def __init__(self, message: str = "Unexpected error") -> None:
        super().__init__(message)
        self.message = message


class ValidationError(AppError):
    status_code = 422
    code = "validation_error"


class AuthenticationError(AppError):
    status_code = 401
    code = "authentication_error"


class AuthorizationError(AppError):
    """Raised when a role attempts a tool or document it may not access."""

    status_code = 403
    code = "authorization_error"


class RateLimitExceeded(AppError):
    status_code = 429
    code = "rate_limit_exceeded"


class PromptInjectionDetected(AppError):
    status_code = 400
    code = "prompt_injection_detected"


class RetrievalError(AppError):
    """Vector database or keyword index failure."""

    status_code = 503
    code = "retrieval_error"


class LLMError(AppError):
    status_code = 503
    code = "llm_error"


class ToolExecutionError(AppError):
    status_code = 500
    code = "tool_execution_error"


class ToolTimeout(ToolExecutionError):
    status_code = 504
    code = "tool_timeout"
