"""
execution_scope.py — Authorization context for NEXUS tool execution.

This module provides a minimal, explicit ExecutionScope that records:
  - The execution mode (PASSIVE_PUBLIC by default)
  - Any explicitly authorized domains / IPs (only relevant for
    AUTHORIZED_SECURITY_ASSESSMENT mode, and only after human approval)
  - Who authorized the scope and when

Design intent:
  - PASSIVE_PUBLIC must always be the default.
  - AUTHORIZED_SECURITY_ASSESSMENT is NOT self-proving authorization.
    A valid ExecutionScope object with that mode is a signal that the
    application layer *intends* to request elevated access, but Phase 3
    guardrails must still verify that `authorized_domains` or
    `authorized_ips` match the actual target before permitting active
    or private-IP access.
  - Source adapters and the HTTP client receive a scope object; they
    must not derive permissions from bare string comparisons.
  - Keep this structure flat and serializable. No ORM, no async.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass, field
from enum import Enum


class ExecutionMode(str, Enum):
    """Permitted execution modes for NEXUS tool invocations."""

    PASSIVE_PUBLIC = "PASSIVE_PUBLIC"
    """Default mode. Only passive, public-internet sources are permitted.
    No private IP ranges, no authenticated APIs, no active port scanning."""

    AUTHORIZED_SECURITY_ASSESSMENT = "AUTHORIZED_SECURITY_ASSESSMENT"
    """Elevated mode for authorized assessments. MUST be accompanied by
    explicit domain/IP authorization populated by the application layer.
    The presence of this mode value alone does NOT grant permission — the
    Phase 3 guardrail must verify authorized_domains / authorized_ips."""


@dataclass
class ExecutionScope:
    """
    Explicit authorization context passed to every tool and adapter call.

    Attributes
    ----------
    mode:
        The execution mode. Defaults to PASSIVE_PUBLIC.
    authorized_domains:
        Domains explicitly authorized for elevated access (only used when
        mode == AUTHORIZED_SECURITY_ASSESSMENT).  Must be populated by the
        application layer after verifying human authorization — never by
        the agent or adapter itself.
    authorized_ips:
        IP addresses or CIDR blocks explicitly authorized for elevated access.
        Same constraints as authorized_domains.
    authorized_by:
        Human-readable identifier of who granted the authorization
        (e.g. "user:jayesh", "api_key:abc123").  Empty string in
        PASSIVE_PUBLIC mode.
    authorized_at:
        UTC timestamp when the authorization was granted.  None in
        PASSIVE_PUBLIC mode.
    investigation_id:
        Optional UUID of the investigation this scope is attached to.
    """

    mode: ExecutionMode = ExecutionMode.PASSIVE_PUBLIC
    authorized_domains: list[str] = field(default_factory=list)
    authorized_ips: list[str] = field(default_factory=list)
    authorized_by: str = ""
    authorized_at: datetime.datetime | None = None
    investigation_id: str | None = None

    # ------------------------------------------------------------------
    # Convenience helpers
    # ------------------------------------------------------------------

    @property
    def is_passive_public(self) -> bool:
        """True when the scope is the safe default mode."""
        return self.mode == ExecutionMode.PASSIVE_PUBLIC

    @property
    def is_elevated(self) -> bool:
        """True only when mode is AUTHORIZED_SECURITY_ASSESSMENT AND
        at least one domain or IP has been explicitly authorized.

        NOTE: This does NOT verify that the current target matches the
        authorized list — that check must be performed by the guardrail.
        """
        return (
            self.mode == ExecutionMode.AUTHORIZED_SECURITY_ASSESSMENT
            and bool(self.authorized_domains or self.authorized_ips)
        )

    def allows_private_ip(self) -> bool:
        """Whether private/loopback IPs are *ever* permissible.

        Returns True only for elevated scopes where the caller has
        explicitly authorized private-range access.  The guardrail must
        additionally confirm the specific IP is in authorized_ips.
        """
        return self.is_elevated

    @classmethod
    def passive_public(cls, investigation_id: str | None = None) -> ExecutionScope:
        """Factory: return the default safe scope."""
        return cls(
            mode=ExecutionMode.PASSIVE_PUBLIC,
            investigation_id=investigation_id,
        )


# Singleton default scope — convenience import for adapters that have no
# specific scope injected yet.
DEFAULT_SCOPE: ExecutionScope = ExecutionScope.passive_public()
