"""Core module containing state management and event handling."""

from .state_manager import (
    StateManager,
    AppState,
    RecordingState,
    NavigationState,
    ObjectState,
    AuthoringState,
)
from .event_dispatcher import EventDispatcher, Event, ActionEvent, EventType

__all__ = [
    "StateManager",
    "AppState",
    "RecordingState",
    "NavigationState",
    "ObjectState",
    "AuthoringState",
    "EventDispatcher",
    "Event",
    "ActionEvent",
    "EventType",
]
