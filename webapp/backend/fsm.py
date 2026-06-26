from enum import Enum
from backend.logger import log

class ProxyState(str, Enum):
    DISCONNECTED = "Disconnected"
    CONNECTING = "Connecting"
    BOOTSTRAPPING = "Bootstrapping"
    CONNECTED = "Connected"
    DISCONNECTING = "Disconnecting"
    ERROR = "Error"

import threading

class ProxyFSM:
    def __init__(self):
        self._state = ProxyState.DISCONNECTED
        self._listeners = []
        self._lock = threading.Lock()

    def current_state(self) -> ProxyState:
        with self._lock:
            return self._state

    def add_listener(self, callback):
        with self._lock:
            self._listeners.append(callback)

    def can_transition(self, next_state: ProxyState) -> bool:
        valid_transitions = {
            ProxyState.DISCONNECTED: [ProxyState.CONNECTING],
            ProxyState.CONNECTING: [ProxyState.BOOTSTRAPPING, ProxyState.ERROR, ProxyState.DISCONNECTING],
            ProxyState.BOOTSTRAPPING: [ProxyState.CONNECTED, ProxyState.ERROR, ProxyState.DISCONNECTING],
            ProxyState.CONNECTED: [ProxyState.DISCONNECTING, ProxyState.ERROR],
            ProxyState.DISCONNECTING: [ProxyState.DISCONNECTED, ProxyState.ERROR],
            ProxyState.ERROR: [ProxyState.DISCONNECTED, ProxyState.CONNECTING]
        }
        return next_state in valid_transitions.get(self._state, [])

    def transition(self, next_state: ProxyState, force: bool = False):
        with self._lock:
            if not force and not self.can_transition(next_state):
                log.warning(f"Invalid FSM transition: {self._state.value} -> {next_state.value}")
                return False

            log.info(f"FSM State: {self._state.value} -> {next_state.value}")
            self._state = next_state
            
        for listener in self._listeners:
            try:
                listener(next_state)
            except Exception as e:
                log.error(f"FSM listener error: {e}")
        return True

fsm = ProxyFSM()
