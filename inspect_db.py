import sqlite3
import json

DB_FILE = "context/context.db"

def display_context():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM context')
    rows = cursor.fetchall()
    conn.close()
    return rows

if __name__ == "__main__":
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    print("=== CONTEXT TABLE ===")
    cursor.execute("SELECT id, job, name FROM context")
    for row in cursor.fetchall():
        id, job, name = row
        print(f"ID: {id}, Job: {job}, Name: {name}")

    print("\n=== DIRECTOR TABLE ===")
    try:
        cursor.execute("SELECT id, goals, character_names FROM director")
        rows = cursor.fetchall()
        if not rows:
            print("Director table exists but has no data.")
        else:
            for row in rows:
                id, goals, char_names = row
                try:
                    # Try to parse as JSON
                    char_names_list = json.loads(char_names)
                    char_names_str = ", ".join(char_names_list)
                except (json.JSONDecodeError, TypeError):
                    # If not valid JSON, display as is
                    char_names_str = char_names
                    
                print(f"ID: {id}")
                print(f"Goals: {goals}")
                print(f"Character Names: {char_names_str}")
    except sqlite3.OperationalError as e:
        print(f"Director table error: {e}")

    print("\n=== CHARACTERS TABLE ===")
    cursor.execute("SELECT id, name, description FROM characters")
    for row in cursor.fetchall():
        id, name, description = row
        print(f"Character ID: {id}, Name: {name}, Description: {description if description else 'None'}")

    conn.close()
