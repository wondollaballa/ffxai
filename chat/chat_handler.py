import streamlit as st
import requests
import json
import re
import random
import time
from agents.ffxi_agent import FFXIAgent  # Updated import path

class ChatHandler:
    """Class to handle chat interactions and LLM responses"""
    
    def __init__(self, db_manager, ollama_api_url, model="deepseek-r1:7b"):
        """Initialize the chat handler"""
        self.db_manager = db_manager
        self.ollama_api_url = ollama_api_url
        self.model = model
        self.agents = {}  # Store character agents
    
    def get_or_create_agent(self, character_name):
        """Get an existing agent or create a new one for a character"""
        if character_name not in self.agents:
            self.agents[character_name] = FFXIAgent(character_name=character_name)
        return self.agents[character_name]
    
    def handle_command(self, prompt):
        """Handle a command directed at a specific character"""
        # Extract character and command
        match = re.search(r"tell\s+(\w+)\s+to\s+(.*)", prompt, re.IGNORECASE)
        if match:
            character_name = match.group(1)
            command = match.group(2)
            
            # Get agent for this character
            agent = self.get_or_create_agent(character_name)
            
            # Execute command
            result = agent.execute_command(command)
            
            # Format response
            if command.lower().startswith(("status", "check", "health", "vitals")):
                health = result.get("data", {})
                
                # Format health status as a nice message
                response = f"### Status for {character_name}\n"
                response += f"**{health.get('jobs', '??')}** in *{health.get('zone', 'Unknown')}*\n"
                response += f"HP: {health.get('hp', '??')} | MP: {health.get('mp', '??')} | TP: {health.get('tp', 0)}\n"
                response += f"Status: {health.get('status', 'Unknown')}"
                
                # Add warning if data is stale
                if not health.get("is_running", False):
                    response += f"\n\n⚠️ *Warning: HealthCheck addon appears to be inactive. Data from {health.get('last_update', 'unknown')}*"
                
                return response
            
            return f"Command sent to {character_name}: {command}\nResult: {result.get('status', 'unknown')}"
        
        return None  # Not a command
    
    def extract_topic(self, message):
        """Extract topic from a message"""
        words = message.split()
        if len(words) > 3:
            return " ".join(words[:3]).lower()
        return message.lower()
    
    def has_sufficient_information(self, topic):
        """Check if we have sufficient information about a topic"""
        # ...existing code...
    
    def get_response(self, prompt, chat_history):
        """Get a response from the LLM based on the prompt and chat history"""
        # First check if this is a command for a character
        command_response = self.handle_command(prompt)
        if command_response:
            return command_response
        
        # ... rest of existing get_response method ...