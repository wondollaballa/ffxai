import os
import sqlite3
from context.initial_greeting import initial_greeting

DB_FILE = "context/context.db"

def get_context():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('SELECT job, name FROM context WHERE id = 1')
    context = cursor.fetchone()
    conn.close()
    return context

def main():
    context = get_context()
    if not context:
        initial_greeting()
    else:
        job, name = context
        print(f"Welcome back, {name}! I am still your {job}.")

    # Start the chat interface
    while True:
        user_input = input("You: ")
        if user_input.lower() in ["exit", "quit"]:
            break
        # ...existing code to handle the chat functionality...
        print("Chatbot: ...response...")

if __name__ == "__main__":
    main()
