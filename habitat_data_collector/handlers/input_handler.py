"""Input handling."""

import cv2
import time
from typing import Optional, Tuple

from .base_handler import BaseHandler
from ..core.event_dispatcher import Event, EventType, ActionEvent


class InputHandler(BaseHandler):
    """Handler for keyboard input."""

    # Key mappings
    KEY_MAPPINGS = {
        ord("a"): ("turn_left", EventType.ACTION_TURN),
        ord("d"): ("turn_right", EventType.ACTION_TURN),
        ord("w"): ("move_forward", EventType.ACTION_MOVE),
        ord("s"): ("move_backward", EventType.ACTION_MOVE),
        81: ("turn_left", EventType.ACTION_TURN),  # Left arrow
        83: ("turn_right", EventType.ACTION_TURN),  # Right arrow
        82: ("look_up", EventType.ACTION_LOOK),     # Up arrow
        84: ("look_down", EventType.ACTION_LOOK),   # Down arrow
    }
    
    # Special action keys
    SPECIAL_ACTIONS = {
        ord("q"): EventType.SYSTEM_STOP,
        ord("h"): EventType.UI_TOGGLE_HELP,
        ord("m"): EventType.UI_TOGGLE_MAP,
        ord("e"): EventType.SYSTEM_SAVE_CONFIG,
        ord(" "): EventType.RECORDING_START,  # Will toggle
        ord("="): EventType.OBJECT_ADD,
        ord("-"): EventType.OBJECT_REMOVE,
        ord("p"): EventType.OBJECT_PLACE_IN_VIEW,
        ord("n"): EventType.NAVIGATION_START,  # Will toggle
        ord("g"): EventType.OBJECT_GRAB,
        ord("r"): EventType.OBJECT_RELEASE,
    }

    def poll(self) -> bool:
        """Poll for keyboard input and dispatch events.
        
        Returns:
            True if input was processed, False otherwise
        """
        k = cv2.waitKey(1)
        
        if k == -1:
            # No key pressed
            return False
        
        timestamp = time.time()

        if self.state.authoring.enabled:
            max_target_key = min(len(self.state.authoring.targets), 9)
            if ord("1") <= k < ord("1") + max_target_key:
                event = Event(
                    event_type=EventType.OBJECT_SELECT,
                    timestamp=timestamp,
                    data={"index": k - ord("1")},
                )
                self.events.dispatch(event)
                return True

            authoring_actions = {
                ord("v"): EventType.OBJECT_RELOCATE,
                ord("u"): EventType.OBJECT_UNDO,
            }
            if k in authoring_actions:
                self.events.dispatch(Event(
                    event_type=authoring_actions[k],
                    timestamp=timestamp,
                ))
                return True

            if k in (ord("="), ord("g"), ord("r"), ord(" ")):
                self.state.authoring.last_status = (
                    "Random add, grab/release, and recording are disabled "
                    "in authoring mode."
                )
                self.state.authoring.last_status_ok = False
                print(self.state.authoring.last_status)
                return True
        
        # Check for movement/action keys
        if k in self.KEY_MAPPINGS:
            action, event_type = self.KEY_MAPPINGS[k]
            event = ActionEvent(
                event_type=event_type,
                timestamp=timestamp,
                action=action
            )
            self.events.dispatch(event)
            return True
        
        # Check for special action keys
        if k in self.SPECIAL_ACTIONS:
            event_type = self.SPECIAL_ACTIONS[k]
            
            # Handle toggle events
            if event_type == EventType.RECORDING_START:
                if self.state.app.recording:
                    event_type = EventType.RECORDING_STOP
            elif event_type == EventType.NAVIGATION_START:
                if self.state.app.is_navigating:
                    event_type = EventType.NAVIGATION_STOP
            
            event = Event(
                event_type=event_type,
                timestamp=timestamp
            )
            self.events.dispatch(event)
            return True
        
        return False
