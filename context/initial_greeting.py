import os
import sqlite3

DB_FILE = "context/context.db"

def create_context_table():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS context (
            id INTEGER PRIMARY KEY,
            job TEXT NOT NULL,
            name TEXT NOT NULL
        )
    ''')
    conn.commit()
    conn.close()

def get_context():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('SELECT job, name FROM context WHERE id = 1')
    context = cursor.fetchone()
    conn.close()
    return context

def save_context(job, name):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('INSERT OR REPLACE INTO context (id, job, name) VALUES (1, ?, ?)', (job, name))
    conn.commit()
    conn.close()

def initial_greeting():
    create_context_table()
    context = get_context()
    if context:
        job, name = context
        print(f"Welcome back, {name}! I am still your {job}.")
    else:
        print("Hello! This looks like it's your first visit.")
        job = input("Can you describe my purpose in assisting you? ")
        name = input("What is your name? ")
        save_context(job, name)
        print(f"Nice to meet you, {name}! I will be your {job}.")

if __name__ == "__main__":
    initial_greeting()
