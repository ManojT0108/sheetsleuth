"""Application errors mapped to HTTP responses at the edge."""


class AppError(Exception):
    status_code = 500

    def __init__(self, detail: str):
        super().__init__(detail)
        self.detail = detail


class WorkbookNotFound(AppError):
    status_code = 404


class FindingNotFound(AppError):
    status_code = 404


class NoDeterministicFix(AppError):
    status_code = 422


class IntegrationUnavailable(AppError):
    status_code = 503


class VerificationFailed(AppError):
    status_code = 500
