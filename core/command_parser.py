"""
CommandParser V4 — Converts a parsed Telegram signal dict into an ordered
sequence of TaskStep objects that the Controller can execute one by one.

Input:  {"teams": "Inter - Milan", "market": "Over 2.5", "score": "1-0"}
Output: [TaskStep(login), TaskStep(navigate, ...), TaskStep(select_market, ...), TaskStep(place_bet)]

This decouples "what to do" (parser) from "how to do it" (executor),
allowing the Controller to add retry / healing / logging between steps.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, List, Optional


@dataclass
class TaskStep:
    """Single atomic action in a betting task sequence."""
    action: str                          # e.g. "login", "navigate", "select_market", "place_bet"
    params: dict[str, Any] = field(default_factory=dict)
    retries: int = 2                     # max retries before giving up
    heal_on_fail: bool = True            # trigger AI selector healing on failure
    description: str = ""                # human-readable description for logs

    def __repr__(self):
        return f"TaskStep({self.action}, {self.params})"


class CommandParser:
    """Transforms a signal dict into an executable task sequence.

    Usage:
        parser = CommandParser(logger)
        steps = parser.parse(signal_dict)
        for step in steps:
            controller.execute_step(step)
    """

    def __init__(self, logger: logging.Logger, config: dict = None):
        self.logger = logger
        self.config = config or {}

    def parse(self, signal: dict) -> List[TaskStep]:
        """Convert a parsed signal into ordered TaskSteps.

        Args:
            signal: dict with keys like "teams", "market", "score", "amount"

        Returns:
            Ordered list of TaskStep objects. Empty list if signal is invalid.
        """
        if not signal:
            return []

        teams = signal.get("teams", "").strip()
        market = signal.get("market", "").strip()
        score = signal.get("score", "").strip()
        amount = signal.get("amount", self.config.get("default_bet_amount", ""))

        if not teams:
            self.logger.warning("[CommandParser] Signal has no teams — skipping")
            return []

        steps: List[TaskStep] = []

        # Step 1: Ensure login
        steps.append(TaskStep(
            action="login",
            description="Ensure logged in to betting platform",
            retries=3,
            heal_on_fail=False,
        ))

        # Step 2: Navigate to match
        steps.append(TaskStep(
            action="navigate",
            params={"teams": teams},
            description=f"Navigate to match: {teams}",
            retries=2,
        ))

        # Step 3: Select market (if provided)
        if market:
            steps.append(TaskStep(
                action="select_market",
                params={"market": market, "score": score},
                description=f"Select market: {market}",
                retries=2,
            ))

        # Step 4: Place bet
        bet_params = {"teams": teams, "market": market}
        if amount:
            bet_params["amount"] = amount
        steps.append(TaskStep(
            action="place_bet",
            params=bet_params,
            description=f"Place bet on {teams} — {market or 'default market'}",
            retries=1,
            heal_on_fail=True,
        ))

        self.logger.info(f"[CommandParser] Signal → {len(steps)} steps for {teams} / {market}")
        return steps

    def parse_multi(self, signals: List[dict]) -> List[List[TaskStep]]:
        """Parse multiple signals into separate task sequences."""
        return [self.parse(s) for s in signals if s]
