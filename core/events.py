from enum import Enum


class AppEvent(str, Enum):
    """
    Centralized application event registry.

    Using Enum prevents typos and enables IDE autocomplete.
    """

    BET_SUCCESS = "BET_SUCCESS"
    BET_FAILED = "BET_FAILED"
    BET_UNKNOWN = "BET_UNKNOWN"
    STATE_CHANGE = "STATE_CHANGE"
    BET_ERROR = "BET_ERROR"
