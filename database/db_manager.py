import sqlite3
import json
import time
import os

class DatabaseManager:
    """Class to handle all database operations"""
    
    def __init__(self, db_path="context/context.db"):
        """Initialize the database manager"""
        self.db_path = db_path
        # Create directory if it doesn't exist
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.create_tables()
    
    def create_tables(self):
        """Create all necessary tables if they don't exist"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Context table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS context (
                id INTEGER PRIMARY KEY,
                job TEXT NOT NULL,
                name TEXT NOT NULL
            )
        ''')
        
        # Characters table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS characters (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                description TEXT
            )
        ''')
        
        # Director table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS director (
                id INTEGER PRIMARY KEY,
                goals TEXT NOT NULL,
                character_names TEXT NOT NULL
            )
        ''')
        
        # Conversation history table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS conversation_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL
            )
        ''')
        
        # Instructions table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS instructions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                instruction TEXT NOT NULL,
                status TEXT DEFAULT 'pending'
            )
        ''')
        
        # Knowledge context table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS knowledge_context (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                topic TEXT NOT NULL,
                information TEXT NOT NULL,
                confidence REAL DEFAULT 0.0,
                last_updated TEXT
            )
        ''')
        
        # Agents table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS agents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                character_id INTEGER,
                capabilities TEXT,
                status TEXT DEFAULT 'inactive'
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def save_to_conversation_history(self, role, content):
        """Save a message to the conversation history database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute('INSERT INTO conversation_history (timestamp, role, content) VALUES (?, ?, ?)', 
                      (timestamp, role, content))
        conn.commit()
        conn.close()
    
    def get_context(self):
        """Get context from the database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('SELECT job, name FROM context WHERE id = 1')
        context = cursor.fetchone()
        conn.close()
        return context
    
    def save_context(self, job, name):
        """Save context to the database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('INSERT OR REPLACE INTO context (id, job, name) VALUES (1, ?, ?)', (job, name))
        conn.commit()
        conn.close()
    
    def save_director_info(self, goals, character_names):
        """Save director information to the database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        # Convert character_names array to a JSON string if it's a list
        if isinstance(character_names, list):
            character_names = json.dumps(character_names)
        cursor.execute('INSERT OR REPLACE INTO director (id, goals, character_names) VALUES (1, ?, ?)', 
                      (goals, character_names))
        conn.commit()
        conn.close()
    
    def get_director_info(self):
        """Get director information from the database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('SELECT goals, character_names FROM director WHERE id = 1')
        director = cursor.fetchone()
        conn.close()
        
        if director:
            goals, character_names = director
            # Parse character_names back to a list if it's a JSON string
            try:
                character_names = json.loads(character_names)
            except (json.JSONDecodeError, TypeError):
                character_names = character_names.split(',') if character_names else []
            return {"goals": goals, "character_names": character_names}
        return None
    
    def get_characters(self):
        """Get all characters from the database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('SELECT id, name, description FROM characters')
        characters = cursor.fetchall()
        conn.close()
        return characters
    
    def save_character(self, name, description=""):
        """Save a character to the database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('INSERT INTO characters (name, description) VALUES (?, ?)', (name, description))
        char_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return char_id
    
    def update_character(self, character_id, name, description=""):
        """Update a character in the database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('UPDATE characters SET name = ?, description = ? WHERE id = ?', (name, description, character_id))
        conn.commit()
        conn.close()
    
    def delete_character(self, character_id):
        """Delete a character from the database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('DELETE FROM characters WHERE id = ?', (character_id,))
        conn.commit()
        conn.close()
    
    def clear_context_db(self):
        """Clear all context-related data from the database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Clear director table
        try:
            cursor.execute('DELETE FROM director')
        except sqlite3.OperationalError:
            # Table might not exist yet
            pass
            
        # Clear other tables
        cursor.execute('DELETE FROM context')
        cursor.execute('DELETE FROM characters')
        cursor.execute('DELETE FROM agents')
        
        conn.commit()
        conn.close()
    
    def save_instruction(self, instruction):
        """Save a user instruction to the database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute('INSERT INTO instructions (timestamp, instruction) VALUES (?, ?)', 
                       (timestamp, instruction))
        instruction_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return instruction_id
    
    def save_knowledge_context(self, topic, information, confidence=0.7):
        """Save learned information to the knowledge context database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        
        # Check if topic exists
        cursor.execute('SELECT id FROM knowledge_context WHERE topic = ?', (topic,))
        result = cursor.fetchone()
        
        if result:
            # Update existing topic if confidence is higher
            cursor.execute('UPDATE knowledge_context SET information = ?, confidence = ?, last_updated = ? WHERE topic = ? AND confidence < ?', 
                          (information, confidence, timestamp, topic, confidence))
        else:
            # Insert new topic
            cursor.execute('INSERT INTO knowledge_context (topic, information, confidence, last_updated) VALUES (?, ?, ?, ?)', 
                          (topic, information, confidence, timestamp))
        
        conn.commit()
        conn.close()
    
    def get_relevant_knowledge(self, query, threshold=0.5):
        """Get relevant knowledge from the context database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('SELECT topic, information FROM knowledge_context WHERE confidence >= ?', (threshold,))
        all_knowledge = cursor.fetchall()
        conn.close()
        
        # Simple keyword matching for now
        relevant_items = []
        query_words = set(query.lower().split())
        
        for topic, information in all_knowledge:
            topic_words = set(topic.lower().split())
            if query_words.intersection(topic_words):
                relevant_items.append((topic, information))
        
        return relevant_items
