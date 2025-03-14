import streamlit as st
from database.db_manager import DatabaseManager

class ContextManager:
    """Class to handle application context management"""
    
    def __init__(self, db_manager=None):
        """Initialize the context manager"""
        self.db_manager = db_manager or DatabaseManager()
        self.initialize_session_state()
        
    def initialize_session_state(self):
        """Initialize all session state variables"""
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
        if "learning_mode" not in st.session_state:
            st.session_state.learning_mode = True
        if "conversation_topics" not in st.session_state:
            st.session_state.conversation_topics = {}
        if "inquiry_depth" not in st.session_state:
            st.session_state.inquiry_depth = 0
        if "current_topic" not in st.session_state:
            st.session_state.current_topic = None
        if "character_status" not in st.session_state:
            st.session_state.character_status = {}
    
    def check_and_create_context(self):
        """Check if context exists and create it if not"""
        # First ensure context is initialized
        if 'context' not in st.session_state or st.session_state.context is None:
            st.session_state.context = {}
        
        # Check for director info - primary source of truth
        director_info = self.db_manager.get_director_info()
        
        if director_info:
            # Director table has data, use it as the source of truth
            st.session_state.context["goals"] = director_info["goals"]
            st.session_state.context["character_names"] = director_info["character_names"]
            
            # Load characters for backward compatibility
            st.session_state.characters = self.db_manager.get_characters()
            return True  # Context successfully loaded from director table
        else:
            # Also check legacy context table for backward compatibility
            context = self.db_manager.get_context()
            if context:
                st.session_state.context["job"] = context[0]
                st.session_state.context["name"] = context[1]
                st.session_state.characters = self.db_manager.get_characters()
                return True  # Context loaded from legacy table
        
        return False  # No context found in any table
    
    def handle_initial_context(self):
        """Handle the initial context setup flow"""
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
            self.db_manager.save_to_conversation_history("assistant", greeting)
            st.session_state.context_step = 1
            return  # Return after setting up the initial greeting
        
        # Step 1a: Process user's purpose response
        elif st.session_state.context_step == 1 and not st.session_state.waiting_for_next:
            print("DEBUG: Executing step 1a - Processing user purpose")
            # Get the last user message
            user_messages = [msg for msg in st.session_state.messages if msg["role"] == "user"]
            if user_messages:
                goals = user_messages[-1]["content"]  # Get the last user message
                
                # Store the goals in session state
                st.session_state.context["goals"] = goals
                
                # Save to the director table immediately - store goals with empty characters list initially
                self.db_manager.save_director_info(goals, [])
                
                # Save the user's purpose response to conversation history
                self.db_manager.save_to_conversation_history("user", goals)
                
                # Ask character question immediately
                char_question = "What are the names of your FFXI characters? Enter ONLY the character names separated by commas (Example: Wondolio, Sintaroh, Timbearu)."
                st.session_state.messages.append({"role": "assistant", "content": char_question})
                self.db_manager.save_to_conversation_history("assistant", char_question)
                st.session_state.context_step = 2
                st.session_state.waiting_for_next = False
                
                print("DEBUG: Asked for character names, moved to step 2")
                return  # Return after asking for character names
        
        # Step 2a: Get character names from user response
        elif st.session_state.context_step == 2 and not st.session_state.waiting_for_next:
            print("DEBUG: Executing step 2a - Processing character names")
            # Get the last user message
            user_messages = [msg for msg in st.session_state.messages if msg["role"] == "user"]
            if user_messages and len(user_messages) >= 1:
                # Get the last user message (character names)
                character_input = user_messages[-1]["content"]
                
                # Save the user's prompt to conversation history
                self.db_manager.save_to_conversation_history("user", character_input)
                
                # Process character names - very permissive approach
                if not character_input.strip():
                    message = "Please enter at least one character name. You can separate multiple names with commas."
                    st.session_state.messages.append({"role": "assistant", "content": message})
                    self.db_manager.save_to_conversation_history("assistant", message)
                    return
                    
                # Parse character names
                if ',' in character_input:
                    character_names = [name.strip() for name in character_input.split(",") if name.strip()]
                else:
                    character_names = [character_input.strip()]
                
                if character_names:
                    # Save character names
                    st.session_state.context["character_names"] = character_names
                    self.db_manager.save_director_info(st.session_state.context.get("goals", ""), character_names)
                    self.db_manager.save_context(st.session_state.context.get("goals", ""), character_input)
                    
                    # Show confirmation
                    char_list = ", ".join(character_names)
                    confirmation_message = f"Thank you! I'll keep track of your character(s): {char_list}. I'll help you manage and monitor their activity in the game. Your goal is: '{st.session_state.context.get('goals', '')}'. How can I get started?"
                    
                    st.session_state.messages.append({"role": "assistant", "content": confirmation_message})
                    self.db_manager.save_to_conversation_history("assistant", confirmation_message)
                    
                    # Save characters for backward compatibility
                    for name in character_names:
                        self.db_manager.save_character(name)
                    st.session_state.characters = self.db_manager.get_characters()
                    
                    # Mark as complete
                    st.session_state.context_step = 4
                    print("DEBUG: Completed initial setup, ready for general conversation")
                    return
                else:
                    # Empty input - ask again
                    message = "Please enter at least one character name. You can separate multiple names with commas."
                    st.session_state.messages.append({"role": "assistant", "content": message})
                    self.db_manager.save_to_conversation_history("assistant", message)
    
    def update_character_status(self, character_name, status, location=None, activity=None, health=None, mana=None):
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
