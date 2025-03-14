import os
import json
import sys
import argparse
import re

def repair_json(json_text):
    """Attempt to repair common JSON formatting issues"""
    print("Attempting to repair malformed JSON")
    
    # Fix missing quotes around property names
    fixed_text = re.sub(r'(\{|\,)\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*:', r'\1 "\2":', json_text)
    
    # Fix single quotes used instead of double quotes
    fixed_text = fixed_text.replace("'", '"')
    
    # Fix missing quotes around string values
    fixed_text = re.sub(r':\s*([a-zA-Z_][a-zA-Z0-9_]*)(,|\})', r': "\1"\2', fixed_text)
    
    # Fix trailing commas in arrays and objects
    fixed_text = re.sub(r',\s*([\]}])', r'\1', fixed_text)
    
    return fixed_text

def test_json_file(file_path):
    """Test if a JSON file can be parsed and try to repair if needed"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        print(f"Testing JSON file: {file_path}")
        
        # First try parsing as-is
        try:
            data = json.loads(content)
            print("✓ JSON is valid!")
            return True
        except json.JSONDecodeError as e:
            print(f"✗ JSON is invalid: {e}")
            
            # Try to repair
            repaired = repair_json(content)
            if repaired != content:
                print("Attempted repair. Testing repaired JSON...")
                try:
                    data = json.loads(repaired)
                    print("✓ Repaired JSON is valid!")
                    
                    # Save repaired version
                    backup_path = file_path + ".backup"
                    print(f"Backing up original file to {backup_path}")
                    with open(backup_path, 'w', encoding='utf-8') as f:
                        f.write(content)
                    
                    print(f"Writing repaired JSON to {file_path}")
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.write(repaired)
                    
                    return True
                except json.JSONDecodeError as e2:
                    print(f"✗ Repair failed: {e2}")
                    return False
            else:
                print("No changes made by repair function")
                return False
    except Exception as e:
        print(f"Error reading file: {e}")
        return False

def find_health_files():
    """Find potential HealthCheck data files"""
    possible_paths = [
        r"C:\Program Files (x86)\Windower\addons\HealthCheck\data",
        r"C:\Program Files\Windower\addons\HealthCheck\data",
        r"C:\Windower\addons\HealthCheck\data",
        os.path.join(os.path.expanduser('~'), "Documents", "Windower", "addons", "HealthCheck", "data")
    ]
    
    found_files = []
    for path in possible_paths:
        if os.path.exists(path):
            json_files = [os.path.join(path, f) for f in os.listdir(path) if f.endswith('.json')]
            found_files.extend(json_files)
    
    return found_files

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Test and repair JSON files")
    parser.add_argument("file", nargs="?", help="Path to JSON file to test")
    
    args = parser.parse_args()
    
    if args.file:
        test_json_file(args.file)
    else:
        # Find and test all health files
        files = find_health_files()
        if not files:
            print("No health data files found")
        else:
            print(f"Found {len(files)} JSON files")
            for file in files:
                print("\n" + "="*50)
                test_json_file(file)
                print("="*50)
