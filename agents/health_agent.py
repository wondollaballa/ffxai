import os
import time
import glob
from datetime import datetime
import logging
import re
import warnings
import json  # Standard JSON library

# Reduce basic logging level to WARNING to cut down on spam
logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger("health_agent")
logger.setLevel(logging.WARNING)  # Only show WARNING and above by default

# Add a filter to suppress specific log messages
class MessageFilter(logging.Filter):
    def __init__(self, excluded_messages):
        self.excluded_messages = excluded_messages

    def filter(self, record):
        return not any(message in record.getMessage() for message in self.excluded_messages)

# Apply the filter to the logger
excluded_messages = ["missing ScriptRunContext! This warning can be ignored when running in bare mode."]
message_filter = MessageFilter(excluded_messages)
logger.addFilter(message_filter)

# Add import for state store
from .state_store import state_store

# Filter out the specific missing ScriptRunContext warnings
warnings.filterwarnings("ignore", message=".*missing ScriptRunContext.*")

class HealthAgent:
    """Agent that monitors character health data from Windower HealthCheck addon"""
    
    def __init__(self, character_name, cadence=3):
        """Initialize the health agent for a specific character"""
        self.character_name = character_name
        self.data_paths = [
            r"C:\Program Files (x86)\Windower\addons\HealthCheck\data",  # Default path
            r"C:\Program Files\Windower\addons\HealthCheck\data",        # Alternate path
            r"C:\Windower\addons\HealthCheck\data",                      # Another alternate path
            os.path.join(os.path.expanduser('~'), "Documents", "Windower", "addons", "HealthCheck", "data")  # User documents path
        ]
        self.json_file = self._find_json_file()
        self.last_data = None
        self.last_timestamp = None
        self.is_running = False
        self.last_checked = time.time()
        self.continuous_monitoring = False
        self.error_message = None
        self.monitoring_thread = None
        self.cadence = cadence
        logger.info(f"Initialized HealthAgent for {character_name}, JSON file path: {self.json_file}")
    
    def _find_json_file(self):
        """Find the correct JSON file for this character by searching multiple locations"""
        # First check for shared JSON files that might contain multiple characters
        shared_files = []
        for base_path in self.data_paths:
            if os.path.exists(base_path):
                # Look for general data files that might contain multiple characters
                json_files = glob.glob(os.path.join(base_path, "*.json"))
                for json_file in json_files:
                    try:
                        with open(json_file, 'r', encoding='utf-8', errors='ignore') as f:
                            # Just read the first 1000 bytes to check for character name
                            # This avoids loading large files completely
                            content_preview = f.read(1000)
                            if self.character_name.lower() in content_preview.lower():
                                # It might contain our character, add to the list to check in detail later
                                shared_files.append(json_file)
                                logger.info(f"Found potential data file for {self.character_name}: {json_file}")
                    except Exception as e:
                        logger.warning(f"Error examining {json_file}: {e}")
                
                # Check for exact filename match
                exact_match = os.path.join(base_path, f"{self.character_name}_data.json")
                if os.path.exists(exact_match):
                    logger.info(f"Found exact match for {self.character_name}: {exact_match}")
                    return exact_match
                
                # Check for case-insensitive match
                for filename in os.listdir(base_path):
                    if filename.lower() == f"{self.character_name.lower()}_data.json":
                        full_path = os.path.join(base_path, filename)
                        logger.info(f"Found case-insensitive match for {self.character_name}: {full_path}")
                        return full_path
        
        # Now check the shared files more thoroughly to confirm they contain the character
        for json_file in shared_files:
            try:
                with open(json_file, 'r', encoding='utf-8', errors='ignore') as f:
                    data = json.load(f)
                    # Check if this character exists in the file
                    if self.character_name in data:
                        logger.info(f"Confirmed {self.character_name} exists in shared file: {json_file}")
                        return json_file
                    # Try case-insensitive search
                    for char_key in data.keys():
                        if char_key.lower() == self.character_name.lower():
                            logger.info(f"Found {self.character_name} (as '{char_key}') in shared file: {json_file}")
                            # Update character name to match the actual case in the file
                            self.character_name = char_key
                            return json_file
            except Exception as e:
                logger.warning(f"Error checking shared file {json_file}: {e}")
        
        # If no file found, return the default path to be created
        default_path = os.path.join(self.data_paths[0], f"{self.character_name}_data.json")
        logger.warning(f"No data file found for {self.character_name}, will use default: {default_path}")
        return default_path
    
    def _repair_json(self, json_text):
        """Attempt to repair common JSON formatting issues"""
        logger.info("Attempting to repair malformed JSON")
        
        try:
            # Fix missing quotes around property names
            # Look for patterns like {key: value} and replace with {"key": value}
            fixed_text = re.sub(r'(\{|\,)\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*:', r'\1 "\2":', json_text)
            
            # Fix single quotes used instead of double quotes
            fixed_text = fixed_text.replace("'", '"')
            
            # Fix missing quotes around string values
            # This is a simplified approach and might not catch all cases
            fixed_text = re.sub(r':\s*([a-zA-Z_][a-zA-Z0-9_]*)(,|\})', r': "\1"\2', fixed_text)
            
            # Fix trailing commas in arrays and objects
            fixed_text = re.sub(r',\s*([\]}])', r'\1', fixed_text)
            
            # Add logging to see what changed
            if fixed_text != json_text:
                logger.info("JSON repair applied")
                # Log the first 200 chars of original and fixed text for debugging
                logger.debug(f"Original: {json_text[:200]}...")
                logger.debug(f"Fixed: {fixed_text[:200]}...")
            
            return fixed_text
        except Exception as e:
            logger.error(f"Error during JSON repair: {e}")
            return json_text
    
    def read_health_data(self):
        """Read the health data from the JSON file"""
        try:
            logger.debug(f"Reading health data for {self.character_name} from {self.json_file}")
            # Check if we need to re-find the file (it might have been created since initialization)
            if not os.path.exists(self.json_file):
                logger.info(f"File not found, searching again for {self.character_name}")
                self.json_file = self._find_json_file()
                logger.info(f"New json_file path: {self.json_file}")
            
            # Check if file exists before attempting to read
            if os.path.exists(self.json_file):
                logger.debug(f"File exists: {self.json_file}")
                # Track file modification time for change detection
                file_mod_time = os.path.getmtime(self.json_file)
                logger.debug(f"File modification time: {file_mod_time}")
                
                try:
                    with open(self.json_file, 'r', encoding='utf-8', errors='ignore') as f:
                        logger.debug(f"File opened successfully: {self.json_file}")
                        
                        # Check if file is empty
                        content = f.read()
                        if not content.strip():
                            # File is empty, don't log an error, this is expected behavior
                            logger.debug(f"File is empty: {self.json_file}")
                            return self.last_data
                        
                        try:
                            # Read the full JSON and extract the character data
                            data = json.loads(content)
                            logger.debug(f"Data loaded from JSON: {data}")
                            
                            if self.character_name not in data:
                                # Try case-insensitive search if exact match fails
                                character_key = next((key for key in data.keys() 
                                                     if key.lower() == self.character_name.lower()), None)
                                if character_key:
                                    logger.info(f"Found character with different case: '{character_key}'")
                                    self.character_name = character_key
                                else:
                                    self.error_message = f"Character '{self.character_name}' not found in data file"
                                    logger.warning(self.error_message)
                                    return self.last_data
                            
                            character_data = data.get(self.character_name)
                            logger.debug(f"Character data: {character_data}")
                            
                            if not character_data:
                                self.error_message = f"No data found for {self.character_name}"
                                logger.warning(self.error_message)
                                return self.last_data
                            
                            # Log the keys in character data for debugging
                            logger.debug(f"Character data keys: {list(character_data.keys())}")
                            
                            # If timestamp is missing but we have other data, add a timestamp
                            if "timestamp" not in character_data and character_data:
                                logger.info(f"Adding missing timestamp for {self.character_name}")
                                character_data["timestamp"] = time.time()
                            
                            # Rest of the processing remains the same
                            if "timestamp" in character_data:
                                new_timestamp = character_data["timestamp"]
                                old_data = self.last_data
                                
                                # Before updating data, check specifically for TP changes
                                tp_changed = False
                                old_tp = None
                                new_tp = None
                                
                                if old_data and self.character_name in old_data and "vitals" in old_data[self.character_name]:
                                    old_vitals = old_data[self.character_name]["vitals"]
                                    old_tp = old_vitals.get("tp", 0)
                                
                                if "vitals" in character_data:
                                    new_vitals = character_data["vitals"]
                                    new_tp = new_vitals.get("tp", 0)
                                
                                # Log TP changes only when they actually change (reduce logging)
                                if old_tp is not None and new_tp is not None and old_tp != new_tp:
                                    tp_changed = True
                                    logger.debug(f"TP changed for {self.character_name}: {old_tp} -> {new_tp}")
                                
                                # Update data regardless to catch TP changes
                                self.last_data = {self.character_name: character_data}  # Wrap in a dict
                                self.is_running = True
                                
                                # Always update the state store with new data
                                # This sends all character data to the state store
                                state_store.update_character_data(self.character_name, character_data)
                                
                                # Additionally update the "is_running" status
                                state_store.set_state(f"{self.character_name}:status", {
                                    "is_running": self.is_running,
                                    "timestamp": time.time()
                                })
                                
                                # Always set last_timestamp if it's None
                                if self.last_timestamp is None:
                                    self.last_timestamp = new_timestamp
                                    self.error_message = None
                                elif new_timestamp > self.last_timestamp or tp_changed:
                                    self.last_timestamp = new_timestamp
                                    self.error_message = None
                                elif time.time() - self.last_timestamp > 10:
                                    self.is_running = False

                                return self.last_data
                            
                            # If we got here, there was an issue with the data structure
                            if "timestamp" not in character_data:
                                self.error_message = f"No timestamp in data for {self.character_name}"
                                logger.warning(self.error_message)
                            else:
                                self.error_message = "Unknown error processing character data"
                                logger.warning(self.error_message)
                                
                        except json.JSONDecodeError as e:
                            # Only log at debug level for empty file parse errors
                            if "Expecting value" in str(e) and content.strip() == "":
                                logger.debug(f"Empty file or whitespace-only: {self.json_file}")
                            else:
                                logger.error(f"JSON parsing error: {e}")
                                self.error_message = f"JSON parsing error: {str(e)}"
                            return self.last_data
                    
                except Exception as e:
                    self.error_message = f"Error reading JSON data: {str(e)}"
                    logger.error(self.error_message)
            else:
                self.error_message = f"Health data file not found"
                logger.warning(self.error_message)
        except Exception as e:
            self.error_message = f"Error accessing health data: {str(e)}"
            logger.error(self.error_message)
            
        return self.last_data
    
    def get_time_since_last_update(self):
        """Get human-readable time since last update"""
        if self.last_timestamp is None:
            return "Never updated"
        
        seconds_since_update = time.time() - self.last_timestamp
        
        # Format the time difference
        if seconds_since_update < 60:
            return f"{int(seconds_since_update)} seconds ago"
        elif seconds_since_update < 3600:
            return f"{int(seconds_since_update / 60)} minutes ago"
        elif seconds_since_update < 86400:
            return f"{int(seconds_since_update / 3600)} hours ago"
        else:
            return f"{int(seconds_since_update / 86400)} days ago"
    
    def get_status_summary(self):
        """Get a summary of the character's current status"""
        if not self.last_data:
            self.read_health_data()
            
        if self.last_data is None:
            return {
                "status": "No data available",
                "last_update": "Never",
                "character": self.character_name,
                "is_running": False,
                "error": self.error_message
            }
        
        if self.character_name not in self.last_data:
            return {
                "status": "Character not found",
                "last_update": "Never",
                "character": self.character_name,
                "is_running": False,
                "error": f"Character '{self.character_name}' not found in data file"
            }
        
        char_data = self.last_data.get(self.character_name, {})
        vitals = char_data.get("vitals", {})
        player = char_data.get("player", {})
        zone = char_data.get("zone", {})
        state = char_data.get("state", {})
        position = char_data.get("position", {})
        
        # Calculate HP and MP percentages
        hp_max = vitals.get("hp_max", 1)
        mp_max = vitals.get("mp_max", 1)
        hp_percent = round((vitals.get("hp", 0) / hp_max) * 100) if hp_max > 0 else 0
        mp_percent = round((vitals.get("mp", 0) / mp_max) * 100) if mp_max > 0 else 0
        
        status_val = state.get("status", 0)
        status_map = {
            0: "Idle",
            1: "Engaged",
            2: "Dead",
            3: "Engaged (Dead)",
            # Add other status codes as needed
        }
        
        # Convert epoch timestamp to readable time if available
        timestamp_readable = "Unknown"
        if char_data.get("timestamp"):
            try:
                timestamp_readable = datetime.fromtimestamp(
                    char_data["timestamp"]).strftime('%Y-%m-%d %H:%M:%S')
            except:
                pass
        
        return {
            "name": player.get("name", self.character_name),
            "jobs": f"{player.get('main_job', '??')}{player.get('main_job_level', '??')}/{player.get('sub_job', '??')}{player.get('sub_job_level', '??')}",
            "hp": f"{vitals.get('hp', 0)}/{vitals.get('hp_max', 0)} ({hp_percent}%)",
            "mp": f"{vitals.get('mp', 0)}/{vitals.get('mp_max', 0)} ({mp_percent}%)",
            "tp": vitals.get("tp", 0),
            "zone": zone.get("name", "Unknown"),
            "position": f"X:{position.get('x', 0):.2f}, Y:{position.get('y', 0):.2f}, Z:{position.get('z', 0):.2f}",
            "status": status_map.get(status_val, f"Unknown ({status_val})"),
            "target": state.get("target_name", "None"),
            "timestamp": timestamp_readable,
            "last_update": self.get_time_since_last_update(),
            "last_update_dt": datetime.fromtimestamp(self.last_timestamp).strftime('%Y-%m-%d %H:%M:%S') if self.last_timestamp else "Never updated",
            "is_running": self.is_running,
            "error": self.error_message,
            "buffs": state.get("buffs", [])  # Add buffs to the status
        }
    
    def send_command(self, command):
        """Send a command to the character (placeholder for future implementation)"""
        logger.info(f"[HealthAgent] Would send command to {self.character_name}: {command}")
        logger.debug(f"Sending command '{command}' to {self.character_name}")
        return {"status": "command_queued", "command": command}