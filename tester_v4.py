#!/usr/bin/env python3
"""
SuperAgent V4 — Diagnostic Test Script
Runs offline checks on all V4 components without needing a browser or API keys.
Exit code 0 = all checks passed.
"""
import sys
import os
import logging
import traceback

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

# Minimal logger for tests
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("V4Test")

PASS = 0
FAIL = 0


def check(name: str, fn):
    global PASS, FAIL
    try:
        fn()
        print(f"  [OK] {name}")
        PASS += 1
    except Exception as e:
        print(f"  [FAIL] {name}: {e}")
        traceback.print_exc()
        FAIL += 1


# ─────────────────────────────────────────────
#  1. State Machine
# ─────────────────────────────────────────────
print("\n=== State Machine ===")


def test_states_exist():
    from core.state_machine import AgentState
    required = ["BOOT", "IDLE", "NAVIGATING", "BETTING", "HEALING",
                "RECOVERING", "TRAINING", "ERROR", "SHUTDOWN"]
    for s in required:
        assert hasattr(AgentState, s), f"Missing state: {s}"


def test_state_transitions():
    from core.state_machine import AgentState, StateManager
    sm = StateManager(logger)
    assert sm.state == AgentState.BOOT
    assert sm.transition(AgentState.IDLE)
    assert sm.state == AgentState.IDLE
    assert sm.transition(AgentState.NAVIGATING)
    assert sm.state == AgentState.NAVIGATING
    # Invalid transition: NAVIGATING -> BOOT should fail
    assert not sm.transition(AgentState.BOOT)
    assert sm.state == AgentState.NAVIGATING


def test_force_state():
    from core.state_machine import AgentState, StateManager
    sm = StateManager(logger)
    sm.force_state(AgentState.ERROR)
    assert sm.state == AgentState.ERROR


def test_state_history():
    from core.state_machine import AgentState, StateManager
    sm = StateManager(logger)
    sm.transition(AgentState.IDLE)
    sm.transition(AgentState.NAVIGATING)
    hist = sm.get_history(5)
    assert len(hist) >= 2


check("All V4 states exist", test_states_exist)
check("Valid/invalid transitions", test_state_transitions)
check("Force state", test_force_state)
check("State history tracking", test_state_history)


# ─────────────────────────────────────────────
#  2. Controller
# ─────────────────────────────────────────────
print("\n=== Controller ===")


def test_controller_init():
    from core.controller import SuperAgentController
    c = SuperAgentController(logger, {})
    assert c.get_state() == "BOOT"


def test_controller_boot():
    from core.controller import SuperAgentController
    c = SuperAgentController(logger, {})
    c.boot()
    assert c.get_state() == "IDLE"


def test_controller_shutdown():
    from core.controller import SuperAgentController
    c = SuperAgentController(logger, {})
    c.boot()
    c.shutdown()
    assert c.get_state() == "SHUTDOWN"


def test_controller_stats():
    from core.controller import SuperAgentController
    c = SuperAgentController(logger, {})
    c.boot()
    stats = c.get_stats()
    assert "state" in stats
    assert "signals_received" in stats
    assert stats["signals_received"] == 0


check("Controller init (BOOT)", test_controller_init)
check("Controller boot (IDLE)", test_controller_boot)
check("Controller shutdown", test_controller_shutdown)
check("Controller stats", test_controller_stats)


# ─────────────────────────────────────────────
#  3. Command Parser
# ─────────────────────────────────────────────
print("\n=== Command Parser ===")


def test_parser_import():
    from core.command_parser import CommandParser, TaskStep
    assert TaskStep is not None
    assert CommandParser is not None


def test_parser_basic_signal():
    from core.command_parser import CommandParser
    cp = CommandParser(logger)
    signal = {"teams": "Inter - Milan", "market": "Over 2.5", "score": "1-0"}
    steps = cp.parse(signal)
    assert len(steps) > 0
    step_types = [s.action for s in steps]
    assert "login" in step_types
    assert "navigate" in step_types
    assert "select_market" in step_types
    assert "place_bet" in step_types


def test_parser_minimal_signal():
    from core.command_parser import CommandParser
    cp = CommandParser(logger)
    signal = {"teams": "Roma - Lazio"}
    steps = cp.parse(signal)
    assert len(steps) >= 2  # at least login + navigate


def test_parser_empty_signal():
    from core.command_parser import CommandParser
    cp = CommandParser(logger)
    steps = cp.parse({})
    assert len(steps) == 0


check("CommandParser import", test_parser_import)
check("Parse full signal → task steps", test_parser_basic_signal)
check("Parse minimal signal (no market)", test_parser_minimal_signal)
check("Empty signal → no steps", test_parser_empty_signal)


# ─────────────────────────────────────────────
#  4. Module Imports (smoke test)
# ─────────────────────────────────────────────
print("\n=== Module Imports ===")

MODULES = [
    ("core.state_machine", "AgentState"),
    ("core.state_machine", "StateManager"),
    ("core.controller", "SuperAgentController"),
    ("core.command_parser", "CommandParser"),
    ("core.utils", None),
    ("gateway.telegram_parser_fixed", "TelegramParser"),
    ("gateway.pattern_memory", "PatternMemory"),
]

for mod_name, attr in MODULES:
    def _make_test(m, a):
        def _test():
            mod = __import__(m, fromlist=[a] if a else [])
            if a:
                assert hasattr(mod, a), f"{m} missing {a}"
        return _test
    check(f"import {mod_name}" + (f".{attr}" if attr else ""), _make_test(mod_name, attr))


# ─────────────────────────────────────────────
#  Summary
# ─────────────────────────────────────────────
print(f"\n{'='*40}")
print(f"  PASSED: {PASS}   FAILED: {FAIL}")
print(f"{'='*40}")

sys.exit(1 if FAIL > 0 else 0)
