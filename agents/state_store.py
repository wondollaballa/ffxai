"""
State Store for reactive data management similar to observables
"""
import threading
import time
import logging
import warnings
from typing import Dict, List, Any, Callable
import traceback
import streamlit as st  # Import Streamlit for triggering UI updates

# Ignore ScriptRunContext warnings
warnings.filterwarnings("ignore", message=".*missing ScriptRunContext.*")
logger = logging.getLogger(__name__)

class StateStore:
    """
    A reactive state store that allows components to subscribe to state changes
    """
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(StateStore, cls).__new__(cls)
                cls._instance._initialize()
            return cls._instance
    
    def _initialize(self):
        """Initialize the state store"""
        self.state = {}
        self.subscribers = {}
        self.change_history = []
        self._update_thread = None
        self._running = False
        # Add buffer for changes that need to go to session state
        self.pending_ui_updates = {}
        self.has_new_updates = False
    
    def set_state(self, key: str, value: Any) -> None:
        """Update state and notify subscribers"""
        old_value = self.state.get(key)
        if old_value != value:  # Only update if value changed
            self.state[key] = value
            self._notify_subscribers(key, old_value, value)
            
            # Store change in history
            self.change_history.append({
                'key': key,
                'old': old_value,
                'new': value,
                'timestamp': time.time()
            })
            # Keep history manageable
            if len(self.change_history) > 100:
                self.change_history = self.change_history[-100:]
                
            # If this is character-related data, add to pending UI updates
            if key.startswith("character:") or ":" in key:
                with self._lock:
                    self.pending_ui_updates[key] = {
                        'value': value,
                        'timestamp': time.time()
                    }
                    self.has_new_updates = True
                    logger.info(f"State updated for {key}: has_new_updates set to True, pending_updates count: {len(self.pending_ui_updates)}")
                    # Trigger a UI update by calling st.rerun()
                    st.rerun()
    
    def get_state(self, key: str, default=None) -> Any:
        """Get current state for a key"""
        return self.state.get(key, default)
    
    def get_all_state(self) -> Dict:
        """Get a copy of the entire state"""
        return self.state.copy()
    
    def subscribe(self, key: str, callback: Callable) -> None:
        """Subscribe to changes for a specific state key"""
        if key not in self.subscribers:
            self.subscribers[key] = []
        self.subscribers[key].append(callback)
    
    def unsubscribe(self, key: str, callback: Callable) -> None:
        """Unsubscribe from changes for a key"""
        if key in self.subscribers:
            if callback in self.subscribers[key]:
                self.subscribers[key].remove(callback)
    
    def _notify_subscribers(self, key: str, old_value: Any, new_value: Any) -> None:
        """Notify all subscribers of a state change"""
        if key in self.subscribers:
            for callback in self.subscribers[key]:
                try:
                    # We wrap in try/except but don't access st.session_state directly here
                    callback(key, old_value, new_value)
                except Exception as e:
                    logger.error(f"Error in subscriber callback: {e}")
                    if logger.isEnabledFor(logging.DEBUG):
                        logger.debug(traceback.format_exc())
    
    def start_update_thread(self) -> None:
        """Start the update thread for periodic state checks"""
        if self._update_thread is None or not self._update_thread.is_alive():
            self._running = True
            self._update_thread = threading.Thread(target=self._update_loop)
            self._update_thread.daemon = True
            self._update_thread.name = "StateStoreUpdate"
            self._update_thread.start()
    
    def stop_update_thread(self) -> None:
        """Stop the update thread"""
        self._running = False
        if self._update_thread:
            self._update_thread.join(timeout=1.0)
    
    def _update_loop(self) -> None:
        """Background thread for periodic updates"""
        while self._running:
            # This can be extended with periodic data fetching
            time.sleep(0.5)
    
    def update_character_data(self, character_name: str, data: Dict) -> None:
        """Update character-specific data"""
        character_key = f"character:{character_name}"
        self.set_state(character_key, data)
        
        # Also set specific vital stats for more granular subscriptions
        if "vitals" in data:
            vitals = data["vitals"]
            for vital in ["hp", "mp", "tp"]:
                if vital in vitals:
                    vital_key = f"{character_name}:{vital}"
                    self.set_state(vital_key, vitals[vital])
    
    def get_pending_updates(self) -> Dict:
        """Get pending UI updates and clear the buffer"""
        with self._lock:
            updates = self.pending_ui_updates.copy()
            had_updates = self.has_new_updates
            logger.info(f"get_pending_updates called: returning had_updates={had_updates}, updates count={len(updates)}")
            self.pending_ui_updates = {}
            self.has_new_updates = False
            return updates, had_updates
    
    def add_refresh_button(self, label="Refresh Data", key="state_refresh_button"):
        """Adds a refresh button to a Streamlit page that triggers data fetch and UI update
        
        Returns:
            bool: True if the button was clicked, False otherwise
        """
        if st.button(label, key=key):
            logger.info("Manual refresh requested via button")
            self.force_refresh()
            return True
        return False
    
    def force_refresh(self):
        """Force a refresh of UI and data"""
        logger.info("Forcing UI refresh")
        # This will be called when the refresh button is clicked
        # You could add any data fetch operations here that need to run
        # before the rerun
        
        # Set a timestamp to indicate when the last manual refresh happened
        self.set_state("system:last_manual_refresh", time.time())
        
        # Trigger Streamlit to rerun the app
        st.rerun()

# Global state store instance
state_store = StateStore()
