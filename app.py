import streamlit as st
import requests
import json
from utils.retriever_pipeline import retrieve_documents
from utils.doc_handler import process_documents
from sentence_transformers import CrossEncoder
import torch
import os
import sqlite3
from dotenv import load_dotenv, find_dotenv
import re
from streamlit.components.v1 import html
import time
# Add the missing import
from ui.ui_manager import UIManager
from database.db_manager import DatabaseManager

# Set page configuration - MUST BE THE FIRST STREAMLIT COMMAND
st.set_page_config(page_title="FFXaI Interface", layout="wide")

torch.classes.__path__ = [os.path.join(torch.__path__[0], torch.classes.__file__)]  # Fix for torch classes not found error
load_dotenv(find_dotenv())  # Loads .env file contents into the application based on key-value pairs defined therein, making them accessible via 'os' module functions like os.getenv().

OLLAMA_BASE_URL = os.getenv("OLLAMA_API_URL", "http://localhost:11434")
OLLAMA_API_URL = f"{OLLAMA_BASE_URL}/api/generate"
MODEL= os.getenv("MODEL", "deepseek-r1:7b")                                                      #Make sure you have it installed in ollama
EMBEDDINGS_MODEL = "nomic-embed-text:latest"
CROSS_ENCODER_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"

device = "cuda" if torch.cuda.is_available() else "cpu"

reranker = None                                                        # 🚀 Initialize Cross-Encoder (Reranker) at the global level 
try:
    reranker = CrossEncoder(CROSS_ENCODER_MODEL, device=device)
except Exception as e:
    st.error(f"Failed to load CrossEncoder model: {str(e)}")

# Add a loading indicator
with st.spinner("Application loading... Please wait"):
    # This will create a visual spinner while the app loads
    pass

# Custom CSS
st.markdown("""
    <style>
        .stApp { background-color: #f4f4f9; }
        h1 { color: #00FF99; text-align: center; }
        .stChatMessage { border-radius: 10px; padding: 10px; margin: 10px 0; }
        .stChatMessage.user { background-color: #e8f0fe; }
        .stChatMessage.assistant { background-color: #d1e7dd; }
        .stButton>button { background-color: #00AAFF; color: white; }
        #toast {
            visibility: hidden;
            min-width: 250px;
            background-color: #333;
            color: #fff;
            text-align: center;
            border-radius: 8px;
            padding: 16px;
            position: fixed;
            z-index: 9999;
            top: 20px;
            right: 20px;
            font-size: 17px;
            white-space: nowrap;
            opacity: 0;
            transition: opacity 0.5s, visibility 0.5s;
            box-shadow: 0 4px 8px rgba(0,0,0,0.2);
        }
        #toast.show {
            visibility: visible;
            opacity: 1;
        }
        #toast.hide {
            visibility: visible;
            opacity: 0;
            transition: opacity 0.5s, visibility 0s 0.5s;
        }
        
        /* Add styles for a more compact header */
        header[data-testid="stHeader"] {
            background-color: #1E1E1E;
            color: #00AAFF;
            padding: 0.5rem;
            display: flex;
            align-items: center;
        }
        
        header[data-testid="stHeader"] h1 {
            font-size: 1.25rem;
            margin: 0;
        }
        
        /* Make sure the title is visible in header */
        .stApp header[data-testid="stHeader"] {
            display: flex !important;
        }
    </style>
""", unsafe_allow_html=True)

# Add a noscript tag to inform users that JavaScript is required
st.markdown("""
    <noscript>
        <div style="color: red; font-weight: bold; text-align: center;">
            You need to enable JavaScript to run this app.
        </div>
    </noscript>
""", unsafe_allow_html=True)

# Define the improved toast component with self-executing JavaScript
def show_toast(message):
    toast_html = f"""
    <div id="toast-container">
        <div id="toast">{message}</div>
    </div>
    <script>
        (function() {{
            // Remove any existing toast
            var existingToast = document.getElementById("toast");
            if (existingToast && existingToast.parentNode) {{
                existingToast.parentNode.removeChild(existingToast);
            }}
            
            // Create new toast and add to body
            var toast = document.createElement("div");
            toast.id = "toast";
            toast.innerText = "{message}";
            document.body.appendChild(toast);
            
            // Show the toast (delay slightly to ensure DOM update)
            setTimeout(function() {{
                toast.className = "show";
            }}, 10);
            
            // Set a timeout to hide the toast
            setTimeout(function(){{ 
                toast.className = "hide";
                
                // After the fade-out animation completes, remove the element
                setTimeout(function() {{
                    if (toast.parentNode) {{
                        toast.parentNode.removeChild(toast);
                    }}
                }}, 500);
            }}, 5000);
        }})();
    </script>
    """
    html(toast_html, height=0)

# Manage Session state
if "messages" not in st.session_state:
    st.session_state.messages = []
if "retrieval_pipeline" not in st.session_state:
    st.session_state.retrieval_pipeline = None
if "rag_enabled" not in st.session_state:
    st.session_state.rag_enabled = False
if "documents_loaded" not in st.session_state:
    st.session_state.documents_loaded = False
if "context" not in st.session_state:
    st.session_state.context = {}
if "context_step" not in st.session_state:
    st.session_state.context_step = 0
if "waiting_for_next" not in st.session_state:
    st.session_state.waiting_for_next = False

# Add to session state initialization
if "learning_mode" not in st.session_state:
    st.session_state.learning_mode = True  # Default to learning mode
if "conversation_topics" not in st.session_state:
    st.session_state.conversation_topics = {}  # Track topics and knowledge state
if "inquiry_depth" not in st.session_state:
    st.session_state.inquiry_depth = 0  # Track how many questions deep we are
if "current_topic" not in st.session_state:
    st.session_state.current_topic = None

# Check and create context
DB_FILE = "context/context.db"

def create_tables():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS context (
            id INTEGER PRIMARY KEY,
            job TEXT NOT NULL,
            name TEXT NOT NULL
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS characters (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT
        )
    ''')
    # Create the new director table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS director (
            id INTEGER PRIMARY KEY,
            goals TEXT NOT NULL,
            character_names TEXT NOT NULL
        )
    ''')
    # Add a new table for conversation history
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS conversation_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL
        )
    ''')
    
    # Add tables for instructions and context tracking
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS instructions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            instruction TEXT NOT NULL,
            status TEXT DEFAULT 'pending'
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS knowledge_context (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            topic TEXT NOT NULL,
            information TEXT NOT NULL,
            confidence REAL DEFAULT 0.0,
            last_updated TEXT
        )
    ''')
    
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

# Add functions to track instructions and context
def save_instruction(instruction):
    """Save a user instruction to the database"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute('INSERT INTO instructions (timestamp, instruction) VALUES (?, ?, ?)', 
                   (timestamp, instruction))
    instruction_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return instruction_id

def save_knowledge_context(topic, information, confidence=0.7):
    """Save learned information to the knowledge context database"""
    conn = sqlite3.connect(DB_FILE)
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

def get_relevant_knowledge(query, threshold=0.5):
    """Get relevant knowledge from the context database"""
    conn = sqlite3.connect(DB_FILE)
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

def create_agent(name, character_id, capabilities="basic"):
    """Create a new agent for a character"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('INSERT INTO agents (name, character_id, capabilities, status) VALUES (?, ?, ?, ?)', 
                   (name, character_id, capabilities, 'ready'))
    agent_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return agent_id

# Add function to save prompt and response to history
def save_to_conversation_history(role, content):
    """Save a message to the conversation history database"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute('INSERT INTO conversation_history (timestamp, role, content) VALUES (?, ?, ?)', (timestamp, role, content))
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

def save_director_info(goals, character_names):
    """Save director information to the database"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    # Convert character_names array to a JSON string if it's a list
    if isinstance(character_names, list):
        character_names = json.dumps(character_names)
    cursor.execute('INSERT OR REPLACE INTO director (id, goals, character_names) VALUES (1, ?, ?)', 
                  (goals, character_names))
    conn.commit()
    conn.close()

def get_director_info():
    """Get director information from the database"""
    conn = sqlite3.connect(DB_FILE)
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

def get_characters():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('SELECT id, name, description FROM characters')
    characters = cursor.fetchall()
    conn.close()
    return characters

def save_character(name, description=""):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('INSERT INTO characters (name, description) VALUES (?, ?)', (name, description))
    conn.commit()
    conn.close()

def update_character(character_id, name, description=""):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('UPDATE characters SET name = ?, description = ? WHERE id = ?', (name, description, character_id))
    conn.commit()
    conn.close()

def delete_character(character_id):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('DELETE FROM characters WHERE id = ?', (character_id,))
    conn.commit()
    conn.close()

def clear_context_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # Clear director table first (now our primary source of truth)
    try:
        cursor.execute('DELETE FROM director')
    except sqlite3.OperationalError:
        # Table might not exist yet
        pass
        
    # Clear legacy tables for backward compatibility
    cursor.execute('DELETE FROM context')
    cursor.execute('DELETE FROM characters')
    
    conn.commit()
    conn.close()

create_tables()

def handle_initial_context():
    # Ensure context is always initialized
    if 'context' not in st.session_state or st.session_state.context is None:
        st.session_state.context = {}
        
    print(f"DEBUG: Initial context - Step: {st.session_state.context_step}, Waiting: {st.session_state.waiting_for_next}")
    
    # Step 0: Initial greeting
    if st.session_state.context_step == 0:
        print("DEBUG: Executing step 0 - Initial greeting")
        st.session_state.messages = []  # Clear any existing messages
        greeting = "Hello! This looks like it's your first visit. Can you describe my purpose in assisting you?"
        st.session_state.messages.append({"role": "assistant", "content": greeting})
        save_to_conversation_history("assistant", greeting)
        st.session_state.context_step = 1
        return  # Return after setting up the initial greeting
    
    # Step 1a: Process user's purpose response
    elif st.session_state.context_step == 1 and not st.session_state.waiting_for_next:
        print("DEBUG: Executing step 1a - Processing user purpose")
        # Get the last user message (their response to the purpose question)
        user_messages = [msg for msg in st.session_state.messages if msg["role"] == "user"]
        if user_messages:
            goals = user_messages[-1]["content"]  # Get the last user message
            
            # Store the goals in session state
            st.session_state.context["goals"] = goals
            
            # Save to the director table immediately - store goals with empty characters list initially
            save_director_info(goals, [])
            
            # Save the user's purpose response to conversation history
            save_to_conversation_history("user", goals)
            
            # Mark that we're waiting to show the next question
            st.session_state.waiting_for_next = True
            
            # Ask character question immediately instead of rerunning
            char_question = "What are the names of your FFXI characters? Enter ONLY the character names separated by commas (Example: Wondolio, Sintaroh, Timbearu)."
            st.session_state.messages.append({"role": "assistant", "content": char_question})
            save_to_conversation_history("assistant", char_question)
            st.session_state.context_step = 2
            st.session_state.waiting_for_next = False
            
            print("DEBUG: Asked for character names, moved to step 2")
            return  # Return after asking for character names
    
    # Step 1b is removed - we now handle this directly in Step 1a above
    
    # Step 2a: Get character names from user response
    elif st.session_state.context_step == 2 and not st.session_state.waiting_for_next:
        print("DEBUG: Executing step 2a - Processing character names")
        # Find the last user message (their response to the character names question)
        user_messages = [msg for msg in st.session_state.messages if msg["role"] == "user"]
        if user_messages and len(user_messages) >= 1:
            # Get the last user message (character names)
            character_input = user_messages[-1]["content"]
            
            # Save the user's prompt to conversation history
            save_to_conversation_history("user", character_input)
            
            # NO VALIDATION - Accept any input that's not empty
            if not character_input.strip():
                message = "Please enter at least one character name. You can separate multiple names with commas."
                st.session_state.messages.append({"role": "assistant", "content": message})
                save_to_conversation_history("assistant", message)
                return  # Stay on the same step, wait for proper names
                
            # Process character names - very permissive approach
            if ',' in character_input:
                # Multiple character names separated by commas
                character_names = [name.strip() for name in character_input.split(",") if name.strip()]
            else:
                # Single character name
                character_names = [character_input.strip()]
            
            if character_names:
                # Print debug message
                print(f"DEBUG: Setting session character names to: {character_names}")
                
                # Save to session state
                st.session_state.context["character_names"] = character_names
                
                # Save to the director table - user goals and character names
                save_director_info(st.session_state.context.get("goals", ""), character_names)
                
                # Also save to the old context system (can be removed later)
                save_context(st.session_state.context.get("goals", ""), character_input)
                
                # Log successful saving for debugging
                print(f"Saved character names to director table: {character_names}")
                print(f"Current goals: {st.session_state.context.get('goals', '')}")
                
                # Show confirmation immediately instead of rerunning
                char_list = ", ".join(character_names)
                confirmation_message = f"Thank you! I'll keep track of your character(s): {char_list}. I'll help you manage and monitor their activity in the game. Your goal is: '{st.session_state.context.get('goals', '')}'. How can I get started?"
                
                st.session_state.messages.append({"role": "assistant", "content": confirmation_message})
                save_to_conversation_history("assistant", confirmation_message)
                
                # Save the characters to the characters table for backward compatibility
                for name in character_names:
                    save_character(name)
                st.session_state.characters = get_characters()
                
                # Mark as complete
                st.session_state.context_step = 4
                
                print("DEBUG: Completed initial setup, ready for general conversation")
                return  # Return after completing the setup
            else:
                # Empty input - ask again
                message = "Please enter at least one character name. You can separate multiple names with commas."
                st.session_state.messages.append({"role": "assistant", "content": message})
                save_to_conversation_history("assistant", message)
    
    # Step 2b is removed - we now handle this directly in Step 2a above

def check_and_create_context():
    # First ensure context is initialized
    if 'context' not in st.session_state or st.session_state.context is None:
        st.session_state.context = {}
    
    # Check for director info - primary source of truth
    director_info = get_director_info()
    
    if director_info:
        # Director table has data, use it as the source of truth
        st.session_state.context["goals"] = director_info["goals"]
        st.session_state.context["character_names"] = director_info["character_names"]
        
        # Load characters for backward compatibility
        st.session_state.characters = get_characters()
        return True  # Context successfully loaded from director table
    else:
        # Also check legacy context table for backward compatibility
        context = get_context()
        if context:
            st.session_state.context["job"] = context[0]
            st.session_state.context["name"] = context[1]
            st.session_state.characters = get_characters()
            return True  # Context loaded from legacy table
    
    return False  # No context found in any table

# Modify how we determine if initial context is needed
has_context = check_and_create_context()

# Only trigger initial context flow if director table is empty and only do it once
if not has_context:
    handle_initial_context()

# Update the CSS to remove right sidebar styling but keep other improvements
st.markdown("""
    <style>
        /* Main layout fixes */
        .main .block-container {
            padding-bottom: 80px; /* Space for chat input */
        }
        
        /* Chat input fix - ensure it stays at bottom */
        .stChatInputContainer {
            position: fixed !important;
            bottom: 0 !important;
            left: 0 !important;
            right: 0 !important;
            padding: 1rem !important;
            background-color: #f4f4f9 !important;
            z-index: 1000 !important;
            border-top: 1px solid #ddd !important;
            margin-left: 260px !important; /* Match sidebar width */
        }
        
        /* Left sidebar styling */
        [data-testid="stSidebar"] {
            background-color: #f4f4f9;
            border-left: 1px solid #ddd;
        }
        
        /* Character status styles kept for future use */
        .character-header {
            font-weight: bold;
            color: #2c3e50;
            font-size: 1.1rem;
        }
        
        .character-content {
            background-color: #ffffff;
            border-radius: 5px;
            padding: 10px;
            margin-top: 5px;
            border: 1px solid #e0e0e0;
        }
        
        .character-status {
            font-style: italic;
            color: #555;
        }
        
        .status-active {
            color: green;
        }
        
        .status-idle {
            color: orange;
        }
    </style>
""", unsafe_allow_html=True)

# Add a custom header that maintains the title but is more compact
st.markdown("""
<style>
    /* Add styles for a more compact header */
    header[data-testid="stHeader"] {
        background-color: #fff;  /* Changed from #1E1E1E to light gray */
        color: #00AAFF;
        padding: 0.5rem;
        display: flex;
        align-items: center;
    }

</style>
""", unsafe_allow_html=True)

# Initialize character status information in session state if it doesn't exist
if "character_status" not in st.session_state:
    st.session_state.character_status = {}

def update_character_status(character_name, status, location=None, activity=None, health=None, mana=None):
    """Update a character's status information"""
    if character_name not in st.session_state.character_status:
        st.session_state.character_status[character_name] = {}
    
    status_info = st.session_state.character_status[character_name]
    if status:
        status_info["status"] = status
    if location:
        status_info["location"] = location
    if activity:
        status_info["activity"] = activity
    if health is not None:
        status_info["health"] = health
    if mana is not None:
        status_info["mana"] = mana
    
    # Add timestamp of last update
    status_info["last_update"] = time.strftime("%H:%M:%S")

# Regular sidebar (left side only)
with st.sidebar:
    st.header("📁 Document Management")
    uploaded_files = st.file_uploader(
        "Upload documents (PDF/DOCX/TXT)",
        type=["pdf", "docx", "txt"],
        accept_multiple_files=True
    )
    
    if uploaded_files and not st.session_state.documents_loaded:
        with st.spinner("Processing documents..."):
            process_documents(uploaded_files,reranker,EMBEDDINGS_MODEL, OLLAMA_BASE_URL)
            st.success("Documents processed!")
    
    st.markdown("---")
    st.header("⚙️ RAG Settings")
    
    st.session_state.rag_enabled = st.checkbox("Enable RAG", value=True)
    st.session_state.enable_hyde = st.checkbox("Enable HyDE", value=True)
    st.session_state.enable_reranking = st.checkbox("Enable Neural Reranking", value=True)
    st.session_state.enable_graph_rag = st.checkbox("Enable GraphRAG", value=True)
    st.session_state.temperature = st.slider("Temperature", 0.0, 1.0, 0.3, 0.05)
    st.session_state.max_contexts = st.slider("Max Contexts", 1, 5, 3)
    
    if st.button("Clear Chat History"):
        st.session_state.messages = []
        clear_context_db()  # Clear the context database
        st.session_state.context = {}
        st.session_state.context_step = 0
        # Show toast using the proper method
        show_toast("Chat history and context have been successfully cleared.")
        # Reinitialize session state
        st.session_state.messages = []
        st.session_state.retrieval_pipeline = None
        st.session_state.rag_enabled = False
        st.session_state.documents_loaded = False
        st.session_state.context = {}
        st.session_state.context_step = 0
        
        # Also add a visible notification for redundancy
        st.success("Chat history and context have been successfully cleared.")

    # 🚀 Footer (Bottom Right in Sidebar) For some Credits :)
    st.sidebar.markdown("""
        <div style="position: absolute; top: 20px; right: 10px; font-size: 12px; color: gray;">
            <b>Developed by:</b> onedough83 &copy; All Rights Reserved 2025
        </div>
    """, unsafe_allow_html=True)

    st.markdown("---")
    st.header("🧠 Learning Style")
    st.session_state.learning_mode = st.checkbox("Learning Mode", value=st.session_state.learning_mode, 
                                                 help="When enabled, the AI will act like it knows nothing and ask questions to learn")
    
    # Add option to reset learned topics
    if st.button("Reset Learned Topics"):
        st.session_state.conversation_topics = {}
        st.session_state.inquiry_depth = 0
        st.session_state.current_topic = None
        show_toast("Reset all learning progress!")

# Main content area with tabbed interface
ui_manager = UIManager()
db_manager = DatabaseManager(DB_FILE)

# Set up the tabbed interface
message_container, dashboard_tab = ui_manager.display_main_interface(db_manager)

# Display messages in the chat tab
ui_manager.display_messages(message_container)

# Display the dashboard in its tab
ui_manager.display_dashboard(dashboard_tab)

# Chat input handling
if prompt := st.chat_input("Ask about your documents..."):
    # Display the user's input
    with st.chat_message("user"):
        st.markdown(prompt)
    
    # Save every user prompt to conversation history immediately
    save_to_conversation_history("user", prompt)
    
    # Check if we're in the initial context flow or normal flow
    if not has_context or st.session_state.context_step in [1, 2]:
        print(f"DEBUG: Processing in setup flow - Step: {st.session_state.context_step}")
        # Add to messages first so handle_initial_context can access it
        st.session_state.messages.append({"role": "user", "content": prompt})
        # Then process through the initial context handler
        handle_initial_context()
        st.rerun()  # Force a rerun to update the UI
    else:
        # Regular flow - add the user's message to history
        st.session_state.messages.append({"role": "user", "content": prompt})
        
        # Check if the user wants to update or add characters
        update_pattern = re.compile(r"update (?:my )?characters", re.IGNORECASE)
        add_pattern = re.compile(r"add (?:a|another) character", re.IGNORECASE)
        
        # Handle other system responses
        message_response = None
        
        if update_pattern.search(prompt):
            # Get existing characters
            characters = get_characters()
            director_info = get_director_info()
            
            # Get character names from director table for display
            if director_info and "character_names" in director_info:
                char_names = ", ".join(director_info["character_names"])
                message = f"Your current character names are: {char_names}\n\nTo update them, reply with: 'set characters to: Name1, Name2, Name3'"
            else:
                character_list = ", ".join([f"{char[0]}: {char[1]}" for char in characters])
                message = f"Here are your current characters:\n{character_list}\n\nTo update all characters at once, reply with: 'set characters to: Name1, Name2, Name3'"
            
            st.session_state.messages.append({"role": "assistant", "content": message})
            with st.chat_message("assistant"):
                st.markdown(message)
            message_response = message
        elif add_pattern.search(prompt):
            message = "What's the name of the character you'd like to add?"
            st.session_state.messages.append({"role": "assistant", "content": message})
            with st.chat_message("assistant"):
                st.markdown(message)
            st.session_state.adding_character = True
            message_response = message
        elif hasattr(st.session_state, 'adding_character') and st.session_state.adding_character:
            st.session_state.messages.append({"role": "user", "content": prompt})
            with st.chat_message("user"):
                st.markdown(prompt)
            save_character(prompt.strip())
            message = f"I've added {prompt.strip()} to your characters!"
            st.session_state.messages.append({"role": "assistant", "content": message})
            with st.chat_message("assistant"):
                st.markdown(message)
            st.session_state.adding_character = False
            message_response = message
        elif re.match(r"update character (\d+) to (.+)", prompt, re.IGNORECASE):
            st.session_state.messages.append({"role": "user", "content": prompt})
            with st.chat_message("user"):
                st.markdown(prompt)
            match = re.match(r"update character (\d+) to (.+)", prompt, re.IGNORECASE)
            char_id = int(match.group(1))
            new_name = match.group(2).strip()
            update_character(char_id, new_name)
            message = f"I've updated character {char_id} to {new_name}."
            st.session_state.messages.append({"role": "assistant", "content": message})
            with st.chat_message("assistant"):
                st.markdown(message)
            message_response = message
        elif re.match(r"delete character (\d+)", prompt, re.IGNORECASE):
            st.session_state.messages.append({"role": "user", "content": prompt})
            with st.chat_message("user"):
                st.markdown(prompt)
            match = re.match(r"delete character (\d+)", prompt, re.IGNORECASE)
            char_id = int(match.group(1))
            delete_character(char_id)
            message = f"I've deleted character {char_id}."
            st.session_state.messages.append({"role": "assistant", "content": message})
            with st.chat_message("assistant"):
                st.markdown(message)
            message_response = message
        else:
            if st.session_state.context_step == 5:
                # Save the provided purpose context
                job = prompt
                st.session_state.context["job"] = job
                save_context(st.session_state.context["job"], st.session_state.context.get("name", ""))
                message = f"Thank you! I've saved my purpose as {job}."
                st.session_state.messages.append({"role": "assistant", "content": message})
                save_to_conversation_history("assistant", message)
                st.session_state.context_step = 0  # Reset the context step
            else:
                chat_history = "\n".join([msg["content"] for msg in st.session_state.messages[-5:]])  # Last 5 messages
                st.session_state.messages.append({"role": "user", "content": prompt})
                with st.chat_message("user"):
                    st.markdown(prompt)
                
                # Get data from DB or model
                response = get_data_from_db_or_model(prompt, chat_history)
                st.session_state.messages.append({"role": "assistant", "content": response})
                with st.chat_message("assistant"):
                    st.markdown(response)
                # When adding assistant's response, save it to conversation history too
                if "assistant" in locals() and response:
                    save_to_conversation_history("assistant", response)

        # Save assistant's response to conversation history for command-based responses
        if message_response:
            save_to_conversation_history("assistant", message_response)

    # Keep the character status update command handling for future use
    update_status_pattern = re.compile(r"update status for ([a-zA-Z]+):(.*)", re.IGNORECASE)
    if update_status_pattern.search(prompt):
        match = update_status_pattern.search(prompt)
        char_name = match.group(1).strip()
        status_info = match.group(2).strip()
        
        # Parse status info (simplified example)
        status_parts = status_info.split(',')
        status_dict = {}
        for part in status_parts:
            if ':' in part:
                key, value = part.split(':', 1)
                status_dict[key.strip().lower()] = value.strip()
        
        # Update character status
        update_character_status(
            char_name,
            status_dict.get('status'),
            status_dict.get('location'),
            status_dict.get('activity'),
            int(status_dict.get('health', '100')) if 'health' in status_dict else None,
            int(status_dict.get('mana', '100')) if 'mana' in status_dict else None
        )
        
        message = f"Updated status for {char_name}!"
        st.session_state.messages.append({"role": "assistant", "content": message})
        with st.chat_message("assistant"):
            st.markdown(message)
        # Show a toast notification instead of rerunning since we don't have the sidebar to update
        show_toast(f"Status updated for {char_name}")

# Add function to determine if we have enough information on a topic
def has_sufficient_information(topic):
    """Check if we have gathered enough information about a topic"""
    if topic not in st.session_state.conversation_topics:
        return False
    
    # If we've asked at least 3 follow-up questions on this topic
    if st.session_state.conversation_topics[topic].get('inquiry_count', 0) >= 3:
        return True
    
    # Or if we explicitly marked it as understood
    return st.session_state.conversation_topics[topic].get('understood', False)

# Function to extract topics from user messages
def extract_topic(message):
    """Simple topic extraction - can be extended with NLP"""
    # For now just use first few words as topic identifier
    words = message.split()
    if len(words) > 3:
        return " ".join(words[:3]).lower()
    return message.lower()

# Modify the get_data_from_db_or_model function to implement the learning-focused approach
def get_data_from_db_or_model(prompt, chat_history):
    # First check if this is a question about goals or characters
    is_about_goals = re.search(r"goal|purpose|assist", prompt, re.IGNORECASE)
    is_about_characters = re.search(r"character|party|member", prompt, re.IGNORECASE)
    
    # Default response type is learning/questioning
    response_type = "inquiry"
    
    # Context from database when needed
    db_context = ""
    if is_about_goals:
        director_info = get_director_info()
        if director_info and "goals" in director_info:
            db_context = f"USER GOALS: {director_info['goals']}\n"
            response_type = "contextual"
    
    if is_about_characters:
        director_info = get_director_info()
        if director_info and "character_names" in director_info:
            char_names = ", ".join(director_info["character_names"])
            db_context = f"CHARACTERS: {char_names}\n"
            response_type = "contextual"
    
    # Extract topic for tracking conversation state
    topic = extract_topic(prompt)
    
    # Update topic tracking
    if topic not in st.session_state.conversation_topics:
        st.session_state.conversation_topics[topic] = {
            'inquiry_count': 0,
            'understood': False,
            'last_question': None
        }
    
    st.session_state.current_topic = topic
    
    # Check if we need more information or can provide a summary
    if has_sufficient_information(topic):
        response_type = "summary"
    else:
        # Increment inquiry count for this topic
        st.session_state.conversation_topics[topic]['inquiry_count'] += 1
    
    # If it's a simple command or instruction, acknowledge it
    if prompt.strip().endswith("?") == False and len(prompt.split()) < 8:
        return "Understood."
    
    # Custom system prompts based on response type
    if response_type == "inquiry":
        system_prompt = f"""You are in LEARNING MODE. You know NOTHING about the topic.
        
        Your ONLY goal is to understand by asking clarifying questions.
        
        Previous conversation:
        {chat_history}
        
        User's message: {prompt}
        
        DO NOT provide information. DO NOT pretend to know things.
        DO NOT apologize for not knowing.
        
        ONLY RESPOND WITH:
        1. "I don't know" if you truly can't understand the message
        2. A short, focused follow-up question to understand better
        3. "Yes" or "No" if it's a yes/no question and you're certain
        4. "Understood." if it's a command or instruction
        
        Keep your response under 30 words. Be humble and curious."""
    
    elif response_type == "summary":
        system_prompt = f"""You are in SUMMARY MODE. Summarize your understanding.
        
        Previous conversation:
        {chat_history}
        
        Based on our conversation about "{topic}", provide a brief summary of your understanding.
        
        Start with "I understand that..." and keep it concise (maximum 3 sentences).
        
        After this summary, ask if your understanding is correct."""
    
    else:  # contextual - for character/goal specific questions
        system_prompt = f"""You are in CONTEXTUAL MODE.
        
        Context information from database:
        {db_context}
        
        Previous conversation:
        {chat_history}
        
        User's message: {prompt}
        
        Respond ONLY with:
        1. Facts directly from the context above
        2. "I don't know" if the context doesn't contain relevant information
        3. A clarifying question if you need more specific information
        
        Keep your response under 50 words. Don't fabricate information."""
    
    # Stream response
    response = requests.post(
        OLLAMA_API_URL,
        json={
            "model": MODEL,
            "prompt": system_prompt,
            "stream": True,
            "options": {
                "temperature": 0.2,  # Lower temperature for more consistent responses
                "num_ctx": 4096
            }
        },
        stream=True
    )
    
    full_response = ""
    try:
        for line in response.iter_lines():
            if line:
                data = json.loads(line.decode())
                token = data.get("response", "")
                full_response += token
                # Stop if we detect the end token
                if data.get("done", False):
                    break
        
        # If response indicates understanding, mark topic as understood
        if "i understand" in full_response.lower() or "understood" in full_response.lower():
            if st.session_state.current_topic:
                st.session_state.conversation_topics[st.session_state.current_topic]['understood'] = True
        
        # Save the response to conversation history
        save_to_conversation_history("assistant", full_response)
        
        return full_response
    except Exception as e:
        error_message = f"I don't know. Can you explain further?"
        save_to_conversation_history("assistant", error_message)
        st.error(f"Generation error: {str(e)}")
        return error_message

