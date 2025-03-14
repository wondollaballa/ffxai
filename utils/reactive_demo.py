"""
Simple demo to show reactive updates in action
"""
import sys
import os
import time
import random
import threading

# Add parent directory to path to allow imports from agents
parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.append(parent_dir)

from agents.state_store import state_store

def tp_callback(key, old_val, new_val):
    """Callback that will be called when TP changes"""
    print(f"TP CHANGED: {key} from {old_val} to {new_val}")

def simulate_tp_changes(character_names):
    """Simulate TP changes for testing"""
    print(f"Simulating TP changes for: {', '.join(character_names)}")
    
    # Subscribe to TP changes for each character
    for char in character_names:
        state_store.subscribe(f"{char}:tp", tp_callback)
    
    # Simulate changes
    try:
        count = 0
        while count < 50:  # Run for 50 iterations
            for char in character_names:
                # Generate random TP value from 0 to 3000
                tp = random.randint(0, 3000)
                
                # Update TP in state store
                state_store.set_state(f"{char}:tp", tp)
                
                # Also update character data
                char_data = state_store.get_state(f"character:{char}", {})
                if not char_data:
                    char_data = {"vitals": {}}
                if "vitals" not in char_data:
                    char_data["vitals"] = {}
                
                char_data["vitals"]["tp"] = tp
                state_store.set_state(f"character:{char}", char_data)
            
            count += 1
            time.sleep(1)
            
    except KeyboardInterrupt:
        print("Stopping simulation")

if __name__ == "__main__":
    # Characters to simulate
    chars = ["Wondolio", "Sintaroh", "Timbearu"]
    
    # Start the simulation in a thread
    sim_thread = threading.Thread(target=simulate_tp_changes, args=(chars,))
    sim_thread.daemon = True
    sim_thread.start()
    
    # Start the state store update thread
    state_store.start_update_thread()
    
    # Main loop - just wait for interruption
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Exiting...")
        state_store.stop_update_thread()
