"""Core module containing state management and event handling."""

from .state_manager import StateManager, AppState, RecordingState, NavigationState, ObjectState
from .event_dispatcher import EventDispatcher, Event, ActionEvent, EventType

__all__ = [
    "StateManager",
    "AppState",
    "RecordingState",
    "NavigationState",
    "ObjectState",
    "EventDispatcher",
    "Event",
    "ActionEvent",
    "EventType",
]

