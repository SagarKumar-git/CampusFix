"""Ticket lifecycle Finite State Machine (FSM) engine.

Enforces deterministic ticket state transitions, role authorizations,
mandatory commentary thresholds, terminal states, and administrator reopening
rules as specified in docs/ARCHITECTURE.md Section 6 and docs/REQUIREMENTS.md FR-013-FR-016.
"""

from __future__ import annotations

from typing import Final

from app.models.ticket import TicketStatus
from app.models.user import UserRole

# ==============================================================================
# Threshold Constants
# ==============================================================================

MIN_RESOLUTION_NOTES_LENGTH: Final[int] = 10
MIN_REJECTION_REASON_LENGTH: Final[int] = 10
MIN_REOPENING_REASON_LENGTH: Final[int] = 10
MIN_GENERIC_NOTES_LENGTH: Final[int] = 10

# ==============================================================================
# Domain Exceptions
# ==============================================================================


class TicketDomainError(Exception):
    """Base domain exception for CampusFix ticket subsystem."""


class TicketFSMError(TicketDomainError):
    """Base exception for Ticket Finite State Machine violations."""


class InvalidStateTransitionError(TicketFSMError):
    """Raised when a status transition is not permitted by the state transition graph."""


class TerminalStateError(TicketFSMError):
    """Raised when attempting to transition a ticket out of a terminal state."""


class UnauthorizedTransitionError(TicketFSMError):
    """Raised when an actor lacks permission to execute a specific transition."""


class MissingTransitionCommentaryError(TicketFSMError):
    """Raised when mandatory notes (resolution, rejection, reopening) are missing or too short."""


class InvalidTargetStatusError(TicketFSMError):
    """Raised when an invalid target status is provided for reopening."""


class InvalidAssigneeError(TicketDomainError):
    """Raised when the assigned staff user is invalid, inactive, or not a staff technician."""


# ==============================================================================
# Transition Matrix & State Sets
# ==============================================================================

# Permitted state transition map: from_status -> frozenset of allowed target statuses
PERMITTED_TRANSITIONS: Final[dict[TicketStatus, frozenset[TicketStatus]]] = {
    TicketStatus.SUBMITTED: frozenset(
        {
            TicketStatus.ASSIGNED,
            TicketStatus.REJECTED,
            TicketStatus.CANCELLED,
        }
    ),
    TicketStatus.ASSIGNED: frozenset(
        {
            TicketStatus.IN_PROGRESS,
            TicketStatus.ASSIGNED,  # Administrative reassignment
            TicketStatus.REJECTED,
            TicketStatus.CANCELLED,
        }
    ),
    TicketStatus.IN_PROGRESS: frozenset(
        {
            TicketStatus.RESOLVED,
            TicketStatus.ASSIGNED,  # Work paused / reassigned
            TicketStatus.REJECTED,  # Administrative rejection
        }
    ),
    TicketStatus.RESOLVED: frozenset(
        {
            TicketStatus.ASSIGNED,  # Administrator reopening
            TicketStatus.SUBMITTED,  # Administrator reopening
        }
    ),
    TicketStatus.REJECTED: frozenset(
        {
            TicketStatus.ASSIGNED,  # Administrator reopening
            TicketStatus.SUBMITTED,  # Administrator reopening
        }
    ),
    TicketStatus.CANCELLED: frozenset(),  # Terminal state
}

TERMINAL_STATUSES: Final[frozenset[TicketStatus]] = frozenset({TicketStatus.CANCELLED})

REOPENING_SOURCE_STATUSES: Final[frozenset[TicketStatus]] = frozenset(
    {
        TicketStatus.RESOLVED,
        TicketStatus.REJECTED,
    }
)

REOPENING_TARGET_STATUSES: Final[frozenset[TicketStatus]] = frozenset(
    {
        TicketStatus.ASSIGNED,
        TicketStatus.SUBMITTED,
    }
)


# ==============================================================================
# Ticket State Machine
# ==============================================================================


class TicketFSM:
    """Deterministic finite state machine controlling ticket lifecycle progression."""

    @staticmethod
    def normalize_status(status: TicketStatus | str) -> TicketStatus:
        """Coerces a string or TicketStatus enum into a verified TicketStatus enum.

        Raises:
            InvalidStateTransitionError: If the status string does not match any TicketStatus.
        """
        if isinstance(status, TicketStatus):
            return status
        try:
            return TicketStatus(str(status).strip())
        except ValueError as exc:
            raise InvalidStateTransitionError(f"Unknown ticket status '{status}'.") from exc

    @staticmethod
    def normalize_role(role: UserRole | str) -> UserRole:
        """Coerces a string or UserRole enum into a verified UserRole enum.

        Raises:
            UnauthorizedTransitionError: If the role string does not match any UserRole.
        """
        if isinstance(role, UserRole):
            return role
        try:
            return UserRole(str(role).strip())
        except ValueError as exc:
            raise UnauthorizedTransitionError(f"Unknown user role '{role}'.") from exc

    @classmethod
    def is_terminal(cls, status: TicketStatus | str) -> bool:
        """Returns True if the given status is a terminal state."""
        return cls.normalize_status(status) in TERMINAL_STATUSES

    @classmethod
    def is_reopening(cls, from_status: TicketStatus | str, to_status: TicketStatus | str) -> bool:
        """Returns True if this transition represents an administrative reopening."""
        from_s = cls.normalize_status(from_status)
        to_s = cls.normalize_status(to_status)
        return from_s in REOPENING_SOURCE_STATUSES and to_s in REOPENING_TARGET_STATUSES

    @classmethod
    def get_permitted_targets(cls, from_status: TicketStatus | str) -> frozenset[TicketStatus]:
        """Returns the set of permitted destination statuses from a given current status."""
        from_s = cls.normalize_status(from_status)
        return PERMITTED_TRANSITIONS.get(from_s, frozenset())

    @classmethod
    def validate_state_transition(
        cls,
        from_status: TicketStatus | str,
        to_status: TicketStatus | str,
        notes: str | None = None,
    ) -> tuple[TicketStatus, TicketStatus]:
        """Validates that a transition from from_status to to_status is syntactically valid

        and satisfies mandatory commentary length constraints.

        Raises:
            TerminalStateError: If the source state is terminal.
            InvalidStateTransitionError: If the transition is not in the permitted graph.
            MissingTransitionCommentaryError: If mandatory notes/reasons are missing or too short.
        """
        from_s = cls.normalize_status(from_status)
        to_s = cls.normalize_status(to_status)

        # 1. Terminal state check
        if from_s in TERMINAL_STATUSES:
            raise TerminalStateError(
                f"Ticket is in terminal state '{from_s.value}' and cannot be transitioned."
            )

        # 2. Permitted transition graph check
        allowed_targets = PERMITTED_TRANSITIONS.get(from_s, frozenset())
        if to_s not in allowed_targets:
            if from_s in REOPENING_SOURCE_STATUSES and to_s not in REOPENING_TARGET_STATUSES:
                raise InvalidTargetStatusError(
                    f"Cannot reopen ticket from '{from_s.value}' to '{to_s.value}'. "
                    f"Target status must be one of: {[s.value for s in REOPENING_TARGET_STATUSES]}."
                )
            raise InvalidStateTransitionError(
                f"Transition from '{from_s.value}' to '{to_s.value}' is not permitted."
            )

        # 3. Commentary length validation
        cleaned_notes = notes.strip() if notes else None

        if to_s == TicketStatus.RESOLVED:
            if not cleaned_notes or len(cleaned_notes) < MIN_RESOLUTION_NOTES_LENGTH:
                raise MissingTransitionCommentaryError(
                    "Resolving a ticket strictly requires 'notes' detailing resolution actions "
                    f"(minimum {MIN_RESOLUTION_NOTES_LENGTH} characters)."
                )

        elif to_s == TicketStatus.REJECTED:
            if not cleaned_notes or len(cleaned_notes) < MIN_REJECTION_REASON_LENGTH:
                raise MissingTransitionCommentaryError(
                    "Rejecting a ticket strictly requires 'notes' detailing the rejection reason "
                    f"(minimum {MIN_REJECTION_REASON_LENGTH} characters)."
                )

        elif from_s in REOPENING_SOURCE_STATUSES:
            if not cleaned_notes or len(cleaned_notes) < MIN_REOPENING_REASON_LENGTH:
                raise MissingTransitionCommentaryError(
                    "Reopening a ticket strictly requires 'notes' detailing the reopening reason "
                    f"(minimum {MIN_REOPENING_REASON_LENGTH} characters)."
                )

        elif cleaned_notes is not None and len(cleaned_notes) < MIN_GENERIC_NOTES_LENGTH:
            raise MissingTransitionCommentaryError(
                f"Transition notes must be at least {MIN_GENERIC_NOTES_LENGTH} characters if provided."
            )

        return from_s, to_s

    @classmethod
    def validate_transition_authorization(
        cls,
        from_status: TicketStatus | str,
        to_status: TicketStatus | str,
        actor_role: UserRole | str,
        *,
        is_creator: bool = False,
        is_assignee: bool = False,
    ) -> None:
        """Validates that the acting user role and ownership context permit this transition.

        Raises:
            UnauthorizedTransitionError: If the actor lacks required permissions.
        """
        from_s = cls.normalize_status(from_status)
        to_s = cls.normalize_status(to_status)
        role = cls.normalize_role(actor_role)

        # 1. Administrator-Only Reopening
        if from_s in REOPENING_SOURCE_STATUSES:
            if role != UserRole.ADMINISTRATOR:
                raise UnauthorizedTransitionError(
                    f"Only administrators are authorized to reopen {from_s.value} tickets. "
                    f"Role '{role.value}' is not permitted."
                )
            return

        # 2. Student Self-Cancellation
        if to_s == TicketStatus.CANCELLED:
            if not is_creator:
                raise UnauthorizedTransitionError("Only the ticket creator can cancel this ticket.")
            if role != UserRole.STUDENT and role != UserRole.ADMINISTRATOR:
                raise UnauthorizedTransitionError(
                    f"Role '{role.value}' is not permitted to cancel this ticket."
                )
            if from_s not in (TicketStatus.SUBMITTED, TicketStatus.ASSIGNED):
                raise UnauthorizedTransitionError(
                    f"Tickets in '{from_s.value}' status cannot be cancelled."
                )
            return

        # 3. Administrative Reassignment (ASSIGNED -> ASSIGNED)
        if from_s == TicketStatus.ASSIGNED and to_s == TicketStatus.ASSIGNED:
            if role != UserRole.ADMINISTRATOR:
                raise UnauthorizedTransitionError(
                    "Only administrators can reassign tickets to a different staff technician."
                )
            return

        # 4. Moving to IN_PROGRESS (ASSIGNED -> IN_PROGRESS)
        if to_s == TicketStatus.IN_PROGRESS:
            if role == UserRole.STAFF:
                if not is_assignee:
                    raise UnauthorizedTransitionError(
                        "Only the assigned staff technician can move this ticket to IN_PROGRESS."
                    )
            elif role != UserRole.ADMINISTRATOR:
                raise UnauthorizedTransitionError(
                    f"Role '{role.value}' is not authorized to transition tickets to IN_PROGRESS."
                )
            return

        # 5. Resolving Ticket (IN_PROGRESS -> RESOLVED)
        if to_s == TicketStatus.RESOLVED:
            if role == UserRole.STAFF:
                if not is_assignee:
                    raise UnauthorizedTransitionError(
                        "Only the assigned staff technician can mark this ticket as RESOLVED."
                    )
            elif role != UserRole.ADMINISTRATOR:
                raise UnauthorizedTransitionError(
                    f"Role '{role.value}' is not authorized to resolve tickets."
                )
            return

        # 6. Pausing Work (IN_PROGRESS -> ASSIGNED)
        if from_s == TicketStatus.IN_PROGRESS and to_s == TicketStatus.ASSIGNED:
            if role == UserRole.STAFF:
                if not is_assignee:
                    raise UnauthorizedTransitionError(
                        "Only the assigned staff technician can pause work on this ticket."
                    )
            elif role != UserRole.ADMINISTRATOR:
                raise UnauthorizedTransitionError(
                    f"Role '{role.value}' is not authorized to pause work on tickets."
                )
            return

        # 7. Initial Assignment from SUBMITTED (SUBMITTED -> ASSIGNED)
        if from_s == TicketStatus.SUBMITTED and to_s == TicketStatus.ASSIGNED:
            if role not in (UserRole.ADMINISTRATOR, UserRole.STAFF):
                raise UnauthorizedTransitionError(
                    f"Role '{role.value}' is not authorized to assign or claim tickets."
                )
            return

        # 8. Rejection Rules
        if to_s == TicketStatus.REJECTED:
            if from_s == TicketStatus.IN_PROGRESS:
                if role != UserRole.ADMINISTRATOR:
                    raise UnauthorizedTransitionError(
                        "Only administrators can reject a ticket that is already in progress."
                    )
            elif role not in (UserRole.ADMINISTRATOR, UserRole.STAFF):
                raise UnauthorizedTransitionError(
                    f"Role '{role.value}' is not authorized to reject tickets."
                )
            return

    @classmethod
    def validate_transition(
        cls,
        from_status: TicketStatus | str,
        to_status: TicketStatus | str,
        actor_role: UserRole | str,
        *,
        is_creator: bool = False,
        is_assignee: bool = False,
        notes: str | None = None,
    ) -> tuple[TicketStatus, TicketStatus]:
        """Performs full deterministic validation of a requested ticket transition:

        1. Validates the state transition against the FSM graph and commentary rules.
        2. Validates that the acting role and ownership context authorize the operation.

        Returns:
            A tuple of normalized (from_status, to_status) enums.
        """
        from_s, to_s = cls.validate_state_transition(from_status, to_status, notes=notes)
        cls.validate_transition_authorization(
            from_s,
            to_s,
            actor_role,
            is_creator=is_creator,
            is_assignee=is_assignee,
        )
        return from_s, to_s
