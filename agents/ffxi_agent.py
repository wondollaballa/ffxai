import sqlite3
import time
import json
import re
import os
from .health_agent import HealthAgent

class FFXIAgent:
    def __init__(self, agent_id=None, character_name=None, db_path="context/context.db"):
        self.db_path = db_path
        self.agent_id = agent_id
        self.character_name = character_name
        self.status = "initializing"
        self.capabilities = []
        self.health_agent = None
        
        # Load or create agent
        if agent_id:
            self.load_agent(agent_id)
        elif character_name:
            self.create_agent(character_name)
            self.setup_health_agent()
    
    def load_agent(self, agent_id):
        """Load agent data from the database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('SELECT name, character_id, capabilities, status FROM agents WHERE id = ?', (agent_id,))
        result = cursor.fetchone()
        conn.close()
        
        if result:
            name, character_id, capabilities, status = result
            self.agent_id = agent_id
            self.character_name = self.get_character_name(character_id)
            self.capabilities = json.loads(capabilities) if capabilities else []
            self.status = status
            return True
        return False
    
    def create_agent(self, character_name):
        """Create a new agent for a character"""
        character_id = self.get_character_id(character_name)
        if not character_id:
            return False
            
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        capabilities = json.dumps(["basic"])
        cursor.execute(
            'INSERT INTO agents (name, character_id, capabilities, status) VALUES (?, ?, ?, ?)',
            (f"Agent-{character_name}", character_id, capabilities, "ready")
        )
        self.agent_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        self.character_name = character_name
        self.capabilities = ["basic"]
        self.status = "ready"
        return True
    
    def get_character_id(self, character_name):
        """Get character ID from name"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('SELECT id FROM characters WHERE name = ?', (character_name,))
        result = cursor.fetchone()
        conn.close()
        return result[0] if result else None
    
    def get_character_name(self, character_id):
        """Get character name from ID"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('SELECT name FROM characters WHERE id = ?', (character_id,))
        result = cursor.fetchone()
        conn.close()
        return result[0] if result else None
    
    def add_capability(self, capability):
        """Add a new capability to the agent"""
        if capability not in self.capabilities:
            self.capabilities.append(capability)
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            capabilities_json = json.dumps(self.capabilities)
            cursor.execute('UPDATE agents SET capabilities = ? WHERE id = ?', 
                          (capabilities_json, self.agent_id))
            conn.commit()
            conn.close()
            return True
        return False
    
    def setup_health_agent(self):
        """Set up the health agent for this character"""
        if self.character_name:
            self.health_agent = HealthAgent(self.character_name)
            # Start monitoring in background
            self.health_agent.start_monitoring()
            print(f"Health agent set up for character: {self.character_name}")
            return True
        return False
    
    def get_health_status(self):
        """Get the current health status of the character"""
        if not self.health_agent:
            if not self.setup_health_agent():
                return {"status": "error", "message": "No health agent available"}
        
        return self.health_agent.get_status_summary()
    
    def execute_command(self, command):
        """Execute a command for this agent"""
        # Check if this is a health status request
        if re.search(r"status|health|check|vitals", command, re.IGNORECASE):
            health_status = self.get_health_status()
            return {
                "status": "success", 
                "message": f"Health status for {self.character_name}",
                "data": health_status
            }
        
        # If it's a game command to be sent to the character
        if re.match(r"^/", command):  # Commands starting with /
            if self.health_agent:
                return self.health_agent.send_command(command)
                
        # This would be where we implement actual command execution
        # For now, we'll just log the command
        log_entry = {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "agent_id": self.agent_id,
            "character": self.character_name,
            "command": command,
            "status": "simulated"
        }
        
        print(f"AGENT LOG: {log_entry}")
        return {"status": "success", "message": f"Simulated command '{command}' for {self.character_name}"}


def get_all_agents(db_path="context/context.db"):
    """Get all agents from the database"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT a.id, a.name, c.name as character_name, a.status 
        FROM agents a
        JOIN characters c ON a.character_id = c.id
    ''')
    agents = cursor.fetchall()
    conn.close()
    return agents

def process_instruction(instruction, db_path="context/context.db"):
    """Process an instruction and assign it to the appropriate agent"""
    # Extract character name from instruction
    char_match = re.search(r"for\s+(\w+)", instruction, re.IGNORECASE)
    character_name = char_match.group(1) if char_match else None
    
    if not character_name:
        return {"status": "error", "message": "No character specified in instruction"}
    
    # Create or load agent
    agent = FFXIAgent(character_name=character_name, db_path=db_path)
    
    # Process the instruction
    result = agent.execute_command(instruction)
    return result
