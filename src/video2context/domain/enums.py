from enum import StrEnum


class Intent(StrEnum):
    UI_FEEDBACK = "ui-feedback"
    BUG_REPRO = "bug-repro"
    WALKTHROUGH = "walkthrough"
    GENERAL = "general"


class Detail(StrEnum):
    COMPACT = "compact"
    BALANCED = "balanced"
    DETAILED = "detailed"
