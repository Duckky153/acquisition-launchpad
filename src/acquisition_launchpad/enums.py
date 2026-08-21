from enum import StrEnum


class AccountType(StrEnum):
    ASSET = "ASSET"
    LIABILITY = "LIABILITY"
    EQUITY = "EQUITY"
    INCOME = "INCOME"
    EXPENSE = "EXPENSE"


class NormalBalance(StrEnum):
    DEBIT = "DEBIT"
    CREDIT = "CREDIT"


class MappingStatus(StrEnum):
    SUGGESTED = "SUGGESTED"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class BlockerSeverity(StrEnum):
    BLOCKING = "BLOCKING"
    WARNING = "WARNING"


class BlockerState(StrEnum):
    OPEN = "OPEN"
    RESOLVED = "RESOLVED"


class ReadinessStatus(StrEnum):
    DATA_PREPARATION_READY = "DATA_PREPARATION_READY"
    NOT_READY = "NOT_READY"


class SequenceStepState(StrEnum):
    COMPLETE = "COMPLETE"
    READY = "READY"
    BLOCKED = "BLOCKED"


class SequenceStepType(StrEnum):
    INTAKE = "INTAKE"
    MAP_ACCOUNTS = "MAP_ACCOUNTS"
    TIE_OUT = "TIE_OUT"
    RESOLVE_BLOCKERS = "RESOLVE_BLOCKERS"
    DATA_PREPARATION_READY = "DATA_PREPARATION_READY"


class ActorType(StrEnum):
    HUMAN = "HUMAN"
    SYSTEM = "SYSTEM"
