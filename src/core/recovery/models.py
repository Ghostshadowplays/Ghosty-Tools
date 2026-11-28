"""Data-only requests: recovery records never contain executable instructions."""

from dataclasses import asdict, dataclass, field
from contextlib import contextmanager
from contextvars import ContextVar
from enum import Enum
import hashlib
import json


class RecoveryError(RuntimeError):
    pass


class IntegrityError(RecoveryError):
    pass


class ConflictError(RecoveryError):
    pass


class Risk(str, Enum):
    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"


class Capability(str, Enum):
    FULL = "Fully Recoverable"
    PARTIAL = "Partially Recoverable"
    MANUAL = "Manual Recovery Required"
    NONE = "Non-Recoverable"


UNRESOLVED = {"Prepared", "Running", "Rolling Back", "Partial Recovery", "Pending Reboot", "Recovery Required"}
STATES = UNRESOLVED | {"Completed", "Failed", "Recovered", "Cancelled", "Manual Recovery Acknowledged"}
ENGINE_VERSION = 1
_active_change = ContextVar("ghosty_recovery_mutation", default=False)


@contextmanager
def _mutation_scope():
    token = _active_change.set(True)
    try:
        yield
    finally:
        _active_change.reset(token)


def require_transaction() -> None:
    if not _active_change.get():
        raise RecoveryError("Windows modifications must execute inside SecurityRecoveryEngine")


def unresolved(record: dict) -> bool:
    return record["status"] in UNRESOLVED or record.get("connectivity_confirmed") is False


def canonical(value) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                      allow_nan=False).encode("utf-8")


def digest(value) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def matches(actual, expected) -> bool:
    """Only compare supported properties; a missing property never verifies."""
    if isinstance(expected, dict):
        return isinstance(actual, dict) and all(key in actual and matches(actual[key], value)
                                                for key, value in expected.items())
    return actual == expected


def known_partial(actual, original, proposed) -> bool:
    if isinstance(original, dict) and isinstance(actual, dict) and isinstance(proposed, dict):
        for key in set(actual) | set(original):
            if key not in actual or key not in original:
                return False
            if key not in proposed:
                if actual[key] != original[key]:
                    return False
            elif not known_partial(actual[key], original[key], proposed[key]):
                return False
        return True
    return actual == original or actual == proposed


@dataclass(frozen=True)
class Operation:
    handler: str
    target: dict
    desired: dict
    description: str = ""
    dependencies: tuple[int, ...] = ()

    def data(self) -> dict:
        # Round-trip prevents callers changing a prepared plan through a mutable dict.
        return json.loads(canonical(asdict(self)))


@dataclass
class Result:
    transaction_id: str
    status: str
    message: str
    details: list = field(default_factory=list)
    operation_failed: bool = False

    @property
    def success(self) -> bool:
        return not self.operation_failed and self.status in {"Completed", "Recovered"}


class Handler:
    """Trusted implementation registered in code, never loaded from record paths."""
    risk = Risk.MEDIUM
    capability = Capability.FULL
    requires_admin = True
    connectivity = False
    resource_group = ""

    def validate(self, target: dict, desired: dict) -> None:
        raise NotImplementedError

    def capture(self, target: dict) -> dict:
        raise NotImplementedError

    def apply(self, target: dict, desired: dict) -> None:
        raise NotImplementedError

    def restore(self, target: dict, original: dict) -> None:
        raise NotImplementedError

    def compare_state(self, state: dict) -> dict:
        return state

    def verify(self, current: dict, expected: dict) -> bool:
        return matches(current, expected)

    def pending_reboot(self, current: dict, expected: dict) -> bool:
        return False

    def requires_reboot(self, target: dict) -> bool:
        return False

    def owns_partial(self, current: dict, original: dict, proposed: dict) -> bool:
        return known_partial(current, original, proposed)

    def resource_identity(self, target: dict) -> dict:
        return target

    def classify(self, target: dict, desired: dict) -> tuple[Risk, Capability, bool]:
        return self.risk, self.capability, self.requires_admin
