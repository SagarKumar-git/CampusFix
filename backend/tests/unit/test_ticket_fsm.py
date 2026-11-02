"""Comprehensive unit test suite for the Ticket Finite State Machine (TicketFSM).

Verifies all permitted transitions, prohibited jumps, terminal states,
role authorizations, ownership constraints, and mandatory commentary rules
per docs/ARCHITECTURE.md Section 6 and docs/REQUIREMENTS.md FR-013 to FR-016.
"""

import pytest

from app.models.ticket import TicketStatus
from app.models.user import UserRole
from app.services.ticket_fsm import (
    InvalidStateTransitionError,
    InvalidTargetStatusError,
    MissingTransitionCommentaryError,
    TerminalStateError,
    TicketFSM,
    UnauthorizedTransitionError,
)

# ==============================================================================
# 1. Permitted Transitions (Positive Cases)
# ==============================================================================


@pytest.mark.parametrize(
    ("from_status", "to_status", "role", "is_creator", "is_assignee", "notes"),
    [
        # SUBMITTED transitions
        (
            TicketStatus.SUBMITTED,
            TicketStatus.ASSIGNED,
            UserRole.ADMINISTRATOR,
            False,
            False,
            "Assigned to staff.",
        ),
        (
            TicketStatus.SUBMITTED,
            TicketStatus.ASSIGNED,
            UserRole.STAFF,
            False,
            False,
            "Claimed by technician.",
        ),
        (
            TicketStatus.SUBMITTED,
            TicketStatus.REJECTED,
            UserRole.ADMINISTRATOR,
            False,
            False,
            "Duplicate report of projector issue.",
        ),
        (
            TicketStatus.SUBMITTED,
            TicketStatus.REJECTED,
            UserRole.STAFF,
            False,
            False,
            "Out of scope for maintenance team.",
        ),
        (
            TicketStatus.SUBMITTED,
            TicketStatus.CANCELLED,
            UserRole.STUDENT,
            True,
            False,
            "Issue resolved by itself.",
        ),
        # ASSIGNED transitions
        (
            TicketStatus.ASSIGNED,
            TicketStatus.IN_PROGRESS,
            UserRole.STAFF,
            False,
            True,
            "Commencing physical repairs.",
        ),
        (
            TicketStatus.ASSIGNED,
            TicketStatus.IN_PROGRESS,
            UserRole.ADMINISTRATOR,
            False,
            False,
            "Overriding start of work.",
        ),
        (
            TicketStatus.ASSIGNED,
            TicketStatus.ASSIGNED,
            UserRole.ADMINISTRATOR,
            False,
            False,
            "Reassigning to different tech.",
        ),
        (
            TicketStatus.ASSIGNED,
            TicketStatus.REJECTED,
            UserRole.ADMINISTRATOR,
            False,
            False,
            "Parts obsolete and unsalvageable.",
        ),
        (
            TicketStatus.ASSIGNED,
            TicketStatus.REJECTED,
            UserRole.STAFF,
            False,
            True,
            "Facility decommissioned.",
        ),
        (
            TicketStatus.ASSIGNED,
            TicketStatus.CANCELLED,
            UserRole.STUDENT,
            True,
            False,
            "Item found and functioning.",
        ),
        # IN_PROGRESS transitions
        (
            TicketStatus.IN_PROGRESS,
            TicketStatus.RESOLVED,
            UserRole.STAFF,
            False,
            True,
            "Replaced damaged HDMI faceplate and tested.",
        ),
        (
            TicketStatus.IN_PROGRESS,
            TicketStatus.RESOLVED,
            UserRole.ADMINISTRATOR,
            False,
            False,
            "Supervised test completed successfully.",
        ),
        (
            TicketStatus.IN_PROGRESS,
            TicketStatus.ASSIGNED,
            UserRole.STAFF,
            False,
            True,
            "Work paused awaiting replacement part.",
        ),
        (
            TicketStatus.IN_PROGRESS,
            TicketStatus.ASSIGNED,
            UserRole.ADMINISTRATOR,
            False,
            False,
            "Work paused by administration.",
        ),
        (
            TicketStatus.IN_PROGRESS,
            TicketStatus.REJECTED,
            UserRole.ADMINISTRATOR,
            False,
            False,
            "Structural damage requires capital project.",
        ),
        # Reopening from RESOLVED (Administrator only)
        (
            TicketStatus.RESOLVED,
            TicketStatus.ASSIGNED,
            UserRole.ADMINISTRATOR,
            False,
            False,
            "Display flickering recurred during lecture.",
        ),
        (
            TicketStatus.RESOLVED,
            TicketStatus.SUBMITTED,
            UserRole.ADMINISTRATOR,
            False,
            False,
            "Returned to triage pool for reassessment.",
        ),
        # Reopening from REJECTED (Administrator only)
        (
            TicketStatus.REJECTED,
            TicketStatus.ASSIGNED,
            UserRole.ADMINISTRATOR,
            False,
            False,
            "Rejection overturned upon administrative review.",
        ),
        (
            TicketStatus.REJECTED,
            TicketStatus.SUBMITTED,
            UserRole.ADMINISTRATOR,
            False,
            False,
            "Rejection overturned back to triage queue.",
        ),
    ],
)
def test_permitted_transitions_pass_validation(
    from_status: TicketStatus,
    to_status: TicketStatus,
    role: UserRole,
    is_creator: bool,
    is_assignee: bool,
    notes: str,
):
    """Verifies that all approved transitions in the FSM matrix pass validation."""
    from_res, to_res = TicketFSM.validate_transition(
        from_status,
        to_status,
        role,
        is_creator=is_creator,
        is_assignee=is_assignee,
        notes=notes,
    )
    assert from_res == from_status
    assert to_res == to_status


# ==============================================================================
# 2. Prohibited Transitions (Negative Cases)
# ==============================================================================


@pytest.mark.parametrize(
    ("from_status", "to_status"),
    [
        # Prohibited jumps from SUBMITTED
        (TicketStatus.SUBMITTED, TicketStatus.SUBMITTED),
        (TicketStatus.SUBMITTED, TicketStatus.IN_PROGRESS),
        (TicketStatus.SUBMITTED, TicketStatus.RESOLVED),
        # Prohibited jumps from ASSIGNED
        (TicketStatus.ASSIGNED, TicketStatus.SUBMITTED),
        (TicketStatus.ASSIGNED, TicketStatus.RESOLVED),  # Cannot bypass IN_PROGRESS
        # Prohibited jumps from IN_PROGRESS
        (TicketStatus.IN_PROGRESS, TicketStatus.SUBMITTED),
        (TicketStatus.IN_PROGRESS, TicketStatus.IN_PROGRESS),
        (TicketStatus.IN_PROGRESS, TicketStatus.CANCELLED),  # Cannot cancel once work started
        # Prohibited jumps from RESOLVED
        (TicketStatus.RESOLVED, TicketStatus.IN_PROGRESS),
        (TicketStatus.RESOLVED, TicketStatus.RESOLVED),
        (TicketStatus.RESOLVED, TicketStatus.REJECTED),
        (TicketStatus.RESOLVED, TicketStatus.CANCELLED),
        # Prohibited jumps from REJECTED
        (TicketStatus.REJECTED, TicketStatus.IN_PROGRESS),
        (TicketStatus.REJECTED, TicketStatus.RESOLVED),
        (TicketStatus.REJECTED, TicketStatus.REJECTED),
        (TicketStatus.REJECTED, TicketStatus.CANCELLED),
    ],
)
def test_prohibited_transitions_raise_invalid_state_transition_error(
    from_status: TicketStatus,
    to_status: TicketStatus,
):
    """Verifies that illegal status jumps raise InvalidStateTransitionError or InvalidTargetStatusError."""
    with pytest.raises((InvalidStateTransitionError, InvalidTargetStatusError)):
        TicketFSM.validate_state_transition(
            from_status,
            to_status,
            notes="Valid note with more than 10 characters.",
        )


# ==============================================================================
# 3. Terminal State Tests
# ==============================================================================


@pytest.mark.parametrize(
    "target_status",
    [
        TicketStatus.SUBMITTED,
        TicketStatus.ASSIGNED,
        TicketStatus.IN_PROGRESS,
        TicketStatus.RESOLVED,
        TicketStatus.REJECTED,
        TicketStatus.CANCELLED,
    ],
)
def test_cancelled_is_terminal_and_cannot_transition(target_status: TicketStatus):
    """Verifies that CANCELLED is an immutable terminal status."""
    assert TicketFSM.is_terminal(TicketStatus.CANCELLED) is True

    with pytest.raises(TerminalStateError, match="terminal state 'CANCELLED'"):
        TicketFSM.validate_state_transition(
            TicketStatus.CANCELLED,
            target_status,
            notes="Attempting transition from terminal state.",
        )


# ==============================================================================
# 4. Mandatory Commentary & Notes Tests
# ==============================================================================


def test_transition_to_resolved_requires_resolution_notes():
    """Resolving a ticket strictly requires notes of at least 10 characters."""
    # Missing notes
    with pytest.raises(
        MissingTransitionCommentaryError, match="Resolving a ticket strictly requires 'notes'"
    ):
        TicketFSM.validate_state_transition(
            TicketStatus.IN_PROGRESS, TicketStatus.RESOLVED, notes=None
        )

    # Empty string
    with pytest.raises(
        MissingTransitionCommentaryError, match="Resolving a ticket strictly requires 'notes'"
    ):
        TicketFSM.validate_state_transition(
            TicketStatus.IN_PROGRESS, TicketStatus.RESOLVED, notes=""
        )

    # Whitespace only
    with pytest.raises(
        MissingTransitionCommentaryError, match="Resolving a ticket strictly requires 'notes'"
    ):
        TicketFSM.validate_state_transition(
            TicketStatus.IN_PROGRESS, TicketStatus.RESOLVED, notes="         "
        )

    # Too short (< 10 chars)
    with pytest.raises(MissingTransitionCommentaryError, match="minimum 10 characters"):
        TicketFSM.validate_state_transition(
            TicketStatus.IN_PROGRESS, TicketStatus.RESOLVED, notes="Fixed it"
        )

    # Valid notes (>= 10 chars)
    from_s, to_s = TicketFSM.validate_state_transition(
        TicketStatus.IN_PROGRESS,
        TicketStatus.RESOLVED,
        notes="Replaced projector bulb and calibrated.",
    )
    assert from_s == TicketStatus.IN_PROGRESS
    assert to_s == TicketStatus.RESOLVED


def test_transition_to_rejected_requires_rejection_reason():
    """Rejecting a ticket strictly requires notes of at least 10 characters."""
    # Missing notes
    with pytest.raises(
        MissingTransitionCommentaryError, match="Rejecting a ticket strictly requires 'notes'"
    ):
        TicketFSM.validate_state_transition(
            TicketStatus.SUBMITTED, TicketStatus.REJECTED, notes=None
        )

    # Too short
    with pytest.raises(MissingTransitionCommentaryError, match="minimum 10 characters"):
        TicketFSM.validate_state_transition(
            TicketStatus.SUBMITTED, TicketStatus.REJECTED, notes="Invalid"
        )

    # Valid notes
    from_s, to_s = TicketFSM.validate_state_transition(
        TicketStatus.SUBMITTED,
        TicketStatus.REJECTED,
        notes="Duplicate ticket reported by another student.",
    )
    assert to_s == TicketStatus.REJECTED


def test_reopening_requires_reopening_reason():
    """Reopening a ticket from RESOLVED or REJECTED strictly requires notes of at least 10 characters."""
    # Reopening from RESOLVED with missing notes
    with pytest.raises(
        MissingTransitionCommentaryError, match="Reopening a ticket strictly requires 'notes'"
    ):
        TicketFSM.validate_state_transition(
            TicketStatus.RESOLVED, TicketStatus.ASSIGNED, notes=None
        )

    # Reopening from REJECTED with too short notes
    with pytest.raises(MissingTransitionCommentaryError, match="minimum 10 characters"):
        TicketFSM.validate_state_transition(
            TicketStatus.REJECTED, TicketStatus.SUBMITTED, notes="Reopen it"
        )

    # Valid reopening reason
    from_s, to_s = TicketFSM.validate_state_transition(
        TicketStatus.RESOLVED,
        TicketStatus.ASSIGNED,
        notes="Issue recurred during the morning class session.",
    )
    assert to_s == TicketStatus.ASSIGNED


def test_generic_notes_must_be_at_least_10_chars_if_provided():
    """If optional notes are provided on other transitions, they must meet the 10-char threshold."""
    with pytest.raises(MissingTransitionCommentaryError, match="at least 10 characters"):
        TicketFSM.validate_state_transition(
            TicketStatus.SUBMITTED,
            TicketStatus.ASSIGNED,
            notes="Short",
        )

    # Valid optional notes
    from_s, to_s = TicketFSM.validate_state_transition(
        TicketStatus.SUBMITTED,
        TicketStatus.ASSIGNED,
        notes="Assigned to the senior electrical engineer.",
    )
    assert to_s == TicketStatus.ASSIGNED


# ==============================================================================
# 5. Role Authorization & Ownership Tests
# ==============================================================================


def test_reopening_strictly_restricted_to_administrator():
    """Students and staff cannot reopen resolved or rejected tickets."""
    # Student attempting reopen
    with pytest.raises(
        UnauthorizedTransitionError, match="Only administrators are authorized to reopen"
    ):
        TicketFSM.validate_transition_authorization(
            TicketStatus.RESOLVED,
            TicketStatus.ASSIGNED,
            actor_role=UserRole.STUDENT,
        )

    # Staff attempting reopen
    with pytest.raises(
        UnauthorizedTransitionError, match="Only administrators are authorized to reopen"
    ):
        TicketFSM.validate_transition_authorization(
            TicketStatus.REJECTED,
            TicketStatus.SUBMITTED,
            actor_role=UserRole.STAFF,
        )

    # Administrator authorized
    TicketFSM.validate_transition_authorization(
        TicketStatus.RESOLVED,
        TicketStatus.ASSIGNED,
        actor_role=UserRole.ADMINISTRATOR,
    )


def test_cancellation_ownership_enforcement():
    """Only the student who created the ticket can cancel it."""
    # Student owner can cancel SUBMITTED
    TicketFSM.validate_transition_authorization(
        TicketStatus.SUBMITTED,
        TicketStatus.CANCELLED,
        actor_role=UserRole.STUDENT,
        is_creator=True,
    )

    # Student owner can cancel ASSIGNED
    TicketFSM.validate_transition_authorization(
        TicketStatus.ASSIGNED,
        TicketStatus.CANCELLED,
        actor_role=UserRole.STUDENT,
        is_creator=True,
    )

    # Non-creator student cannot cancel
    with pytest.raises(
        UnauthorizedTransitionError, match="Only the ticket creator can cancel this ticket."
    ):
        TicketFSM.validate_transition_authorization(
            TicketStatus.SUBMITTED,
            TicketStatus.CANCELLED,
            actor_role=UserRole.STUDENT,
            is_creator=False,
        )

    # Staff cannot cancel ticket
    with pytest.raises(UnauthorizedTransitionError, match="Only the ticket creator"):
        TicketFSM.validate_transition_authorization(
            TicketStatus.SUBMITTED,
            TicketStatus.CANCELLED,
            actor_role=UserRole.STAFF,
            is_creator=False,
        )


def test_staff_assignee_rules():
    """Only the assigned staff technician can move a ticket to IN_PROGRESS or RESOLVED."""
    # Assigned staff technician can move to IN_PROGRESS
    TicketFSM.validate_transition_authorization(
        TicketStatus.ASSIGNED,
        TicketStatus.IN_PROGRESS,
        actor_role=UserRole.STAFF,
        is_assignee=True,
    )

    # Unassigned staff technician cannot move to IN_PROGRESS
    with pytest.raises(UnauthorizedTransitionError, match="Only the assigned staff technician"):
        TicketFSM.validate_transition_authorization(
            TicketStatus.ASSIGNED,
            TicketStatus.IN_PROGRESS,
            actor_role=UserRole.STAFF,
            is_assignee=False,
        )

    # Assigned staff technician can resolve ticket
    TicketFSM.validate_transition_authorization(
        TicketStatus.IN_PROGRESS,
        TicketStatus.RESOLVED,
        actor_role=UserRole.STAFF,
        is_assignee=True,
    )

    # Unassigned staff technician cannot resolve ticket
    with pytest.raises(UnauthorizedTransitionError, match="Only the assigned staff technician"):
        TicketFSM.validate_transition_authorization(
            TicketStatus.IN_PROGRESS,
            TicketStatus.RESOLVED,
            actor_role=UserRole.STAFF,
            is_assignee=False,
        )


def test_reassignment_restricted_to_administrator():
    """Only administrators can reassign an already-assigned ticket (ASSIGNED -> ASSIGNED)."""
    # Administrator permitted
    TicketFSM.validate_transition_authorization(
        TicketStatus.ASSIGNED,
        TicketStatus.ASSIGNED,
        actor_role=UserRole.ADMINISTRATOR,
    )

    # Staff prohibited from reassignment
    with pytest.raises(
        UnauthorizedTransitionError, match="Only administrators can reassign tickets"
    ):
        TicketFSM.validate_transition_authorization(
            TicketStatus.ASSIGNED,
            TicketStatus.ASSIGNED,
            actor_role=UserRole.STAFF,
        )


def test_rejection_of_in_progress_restricted_to_administrator():
    """Staff cannot reject a ticket once work has commenced (IN_PROGRESS); requires Administrator."""
    # Administrator permitted
    TicketFSM.validate_transition_authorization(
        TicketStatus.IN_PROGRESS,
        TicketStatus.REJECTED,
        actor_role=UserRole.ADMINISTRATOR,
    )

    # Staff prohibited
    with pytest.raises(
        UnauthorizedTransitionError,
        match="Only administrators can reject a ticket that is already in progress",
    ):
        TicketFSM.validate_transition_authorization(
            TicketStatus.IN_PROGRESS,
            TicketStatus.REJECTED,
            actor_role=UserRole.STAFF,
            is_assignee=True,
        )


# ==============================================================================
# 6. Helper & Normalization Tests
# ==============================================================================


def test_normalize_status_and_role():
    """Verifies string to enum normalization and invalid inputs."""
    assert TicketFSM.normalize_status("SUBMITTED") == TicketStatus.SUBMITTED
    assert TicketFSM.normalize_status(TicketStatus.RESOLVED) == TicketStatus.RESOLVED

    with pytest.raises(InvalidStateTransitionError, match="Unknown ticket status"):
        TicketFSM.normalize_status("INVALID_STATUS")

    assert TicketFSM.normalize_role("ADMINISTRATOR") == UserRole.ADMINISTRATOR
    assert TicketFSM.normalize_role(UserRole.STAFF) == UserRole.STAFF

    with pytest.raises(UnauthorizedTransitionError, match="Unknown user role"):
        TicketFSM.normalize_role("SUPERUSER")
