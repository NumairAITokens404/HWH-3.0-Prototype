"""Resolve approval reviewers from configured bearer credentials."""

import hmac


class ApprovalAuthenticationError(ValueError):
    """Raised when an approval credential is missing or invalid."""


class ApprovalAuthenticator:
    def __init__(self, credentials: tuple[tuple[str, str], ...] = ()):
        self._credentials = credentials

    @property
    def enabled(self) -> bool:
        return bool(self._credentials)

    def authenticate(self, authorization: str | None, claimed_reviewer: str | None) -> str:
        if not self.enabled:
            if not claimed_reviewer or not claimed_reviewer.strip():
                raise ApprovalAuthenticationError("Reviewer is required in local approval mode")
            return claimed_reviewer.strip()
        if not authorization or not authorization.startswith("Bearer "):
            raise ApprovalAuthenticationError("A bearer token is required for approval")
        token = authorization.removeprefix("Bearer ").strip()
        for reviewer, expected in self._credentials:
            if hmac.compare_digest(token, expected):
                if claimed_reviewer and claimed_reviewer.strip() != reviewer:
                    raise ApprovalAuthenticationError("Reviewer does not match the authenticated identity")
                return reviewer
        raise ApprovalAuthenticationError("Invalid approval bearer token")
