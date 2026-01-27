"""Base handler class."""

from abc import ABC
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..core.state_manager import StateManager
    from ..core.simulator_service import SimulatorService
    from ..core.event_dispatcher import EventDispatcher


class BaseHandler(ABC):
    """Base class for all handlers."""

    def __init__(
        self,
        state_manager: "StateManager",
        simulator: "SimulatorService",
        event_dispatcher: "EventDispatcher",
    ):
        """Initialize handler.
        
        Args:
            state_manager: State manager instance
            simulator: Simulator service instance
            event_dispatcher: Event dispatcher instance
        """
        self.state = state_manager
        self.sim = simulator
        self.events = event_dispatcher

