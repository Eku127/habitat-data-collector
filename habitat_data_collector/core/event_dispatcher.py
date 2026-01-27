"""Event dispatching system."""

from dataclasses import dataclass
from typing import Callable, Dict, List, Any, Optional
from enum import Enum, auto


class EventType(Enum):
    """Types of events in the system."""
    # Action events
    ACTION_MOVE = auto()
    ACTION_TURN = auto()
    ACTION_LOOK = auto()
    
    # Recording events
    RECORDING_START = auto()
    RECORDING_STOP = auto()
    
    # Navigation events
    NAVIGATION_START = auto()
    NAVIGATION_STOP = auto()
    
    # Object events
    OBJECT_ADD = auto()
    OBJECT_REMOVE = auto()
    OBJECT_PLACE_IN_VIEW = auto()
    OBJECT_GRAB = auto()
    OBJECT_RELEASE = auto()
    
    # UI events
    UI_TOGGLE_MAP = auto()
    UI_TOGGLE_HELP = auto()
    
    # System events
    SYSTEM_STOP = auto()
    SYSTEM_SAVE_CONFIG = auto()


@dataclass
class Event:
    """Base event class."""
    event_type: EventType
    timestamp: float
    data: Optional[Dict[str, Any]] = None


@dataclass
class ActionEvent(Event):
    """Event for agent actions."""
    action: Optional[str] = None


class EventDispatcher:
    """Event dispatcher for decoupled communication."""

    def __init__(self):
        self._handlers: Dict[EventType, List[Callable]] = {}

    def subscribe(self, event_type: EventType, handler: Callable[[Event], None]):
        """Subscribe a handler to an event type.
        
        Args:
            event_type: The type of event to subscribe to.
            handler: Callback function to handle the event.
        """
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        self._handlers[event_type].append(handler)

    def unsubscribe(self, event_type: EventType, handler: Callable[[Event], None]):
        """Unsubscribe a handler from an event type.
        
        Args:
            event_type: The type of event to unsubscribe from.
            handler: The handler to remove.
        """
        if event_type in self._handlers:
            self._handlers[event_type].remove(handler)

    def dispatch(self, event: Event):
        """Dispatch an event to all subscribed handlers.
        
        Args:
            event: The event to dispatch.
        """
        if event.event_type in self._handlers:
            for handler in self._handlers[event.event_type]:
                handler(event)

