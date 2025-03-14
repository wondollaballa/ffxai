"""
Utility to monitor JSON files for changes and verify parsing
"""
import os
import json
import time
import logging
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import argparse

logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class JSONFileHandler(FileSystemEventHandler):
    def __init__(self, character_names=None):
        self.character_names = character_names or []
        self.last_modified = {}
        self.last_content = {}
        
    def on_modified(self, event):
        if not event.is_directory and event.src_path.endswith('.json'):
            try:
                file_path = event.src_path
                mod_time = os.path.getmtime(file_path)
                
                # Skip if we've already processed this modification
                if file_path in self.last_modified and self.last_modified[file_path] == mod_time:
                    return
                    
                self.last_modified[file_path] = mod_time
                
                # Read and parse the file
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                    
                try:
                    data = json.loads(content)
                    
                    # Check if content actually changed
                    if file_path in self.last_content and self.last_content[file_path] == content:
                        logger.info(f"File {os.path.basename(file_path)} was modified but content didn't change")
                        return
                        
                    self.last_content[file_path] = content
                    
                    # Look for character data
                    found_characters = []
                    for char_name in self.character_names:
                        if char_name in data:
                            found_characters.append(char_name)
                            char_data = data[char_name]
                            
                            # Log vitals if available
                            if "vitals" in char_data:
                                vitals = char_data["vitals"]
                                logger.info(f"{char_name}: HP={vitals.get('hp', '??')}/{vitals.get('hp_max', '??')}, " +
                                          f"MP={vitals.get('mp', '??')}/{vitals.get('mp_max', '??')}, " +
                                          f"TP={vitals.get('tp', 0)}")
                    
                    if found_characters:
                        logger.info(f"File {os.path.basename(file_path)} updated with data for: {', '.join(found_characters)}")
                    else:
                        # Log all character names in the file
                        logger.info(f"File {os.path.basename(file_path)} updated with characters: {list(data.keys())}")
                        
                except json.JSONDecodeError as e:
                    logger.error(f"Error parsing JSON in {file_path}: {e}")
                    
            except Exception as e:
                logger.error(f"Error processing file {event.src_path}: {e}")

def find_health_files():
    """Find potential HealthCheck data files directories"""
    possible_paths = [
        r"C:\Program Files (x86)\Windower\addons\HealthCheck\data",
        r"C:\Program Files\Windower\addons\HealthCheck\data",
        r"C:\Windower\addons\HealthCheck\data",
        os.path.join(os.path.expanduser('~'), "Documents", "Windower", "addons", "HealthCheck", "data")
    ]
    
    found_paths = []
    for path in possible_paths:
        if os.path.exists(path):
            found_paths.append(path)
    
    return found_paths

def main():
    parser = argparse.ArgumentParser(description="Monitor JSON files for changes")
    parser.add_argument("-c", "--characters", nargs='+', help="Character names to track")
    parser.add_argument("-p", "--path", help="Path to monitor (defaults to HealthCheck data directories)")
    
    args = parser.parse_args()
    
    # Get directories to monitor
    if args.path and os.path.exists(args.path):
        paths_to_watch = [args.path]
    else:
        paths_to_watch = find_health_files()
        
    if not paths_to_watch:
        logger.error("No valid paths to monitor found")
        return
        
    logger.info(f"Setting up file watchers for: {paths_to_watch}")
    
    # Set up file watchers
    event_handler = JSONFileHandler(args.characters)
    observer = Observer()
    
    for path in paths_to_watch:
        observer.schedule(event_handler, path, recursive=False)
        logger.info(f"Watching directory: {path}")
        
        # List current files
        json_files = [f for f in os.listdir(path) if f.endswith('.json')]
        logger.info(f"Found {len(json_files)} JSON files: {', '.join(json_files)}")
    
    observer.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()

if __name__ == "__main__":
    main()
