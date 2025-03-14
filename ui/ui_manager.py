import streamlit as st
from streamlit.components.v1 import html
import time
from ui.health_dashboard import HealthDashboard

class UIManager:
    """Class to handle UI components and styling"""
    
    def __init__(self):
        """Initialize the UI manager"""
        self.apply_css()
        self.health_dashboard = HealthDashboard()
    
    def apply_css(self):
        """Apply custom CSS styling to the application"""
        st.markdown("""
            <style>
                .stApp { background-color: #f4f4f9; }
                h1 { color: #00FF99; text-align: center; }
                .stChatMessage { border-radius: 10px; padding: 10px; margin: 10px 0; }
                .stChatMessage.user { background-color: #e8f0fe; }
                .stChatMessage.assistant { background-color: #d1e7dd; }
                .stButton>button { background-color: #00AAFF; color: white; }
                .stMainBlockContainer.st-emotion-cache-b499ls {padding: 0 1rem !important;}
                .st-emotion-cache-b499ls { padding: unset !important;}
                .st-emotion-cache-1y34ygi.eht7o1d7 {padding: 1rem !important;}
                .stBottom { box-shadow: 0 -4px 6px -2px rgba(0,0,0,0.1); }
            
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
                
                /* Character status styles */
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
                
                .status-active { color: green; }
                .status-idle { color: orange; }
                
                /* Custom tab styling */
                .stTabs [data-baseweb="tab-list"] {
                    gap: 10px;
                }
                
                .stTabs [data-baseweb="tab"] {
                    padding: 10px 20px;
                    border-radius: 5px 5px 0px 0px;
                }
                
                /* Health bar and status styling */
                .health-container {
                    margin-bottom: 15px;
                }
                
                .status-badge {
                    display: inline-block;
                    padding: 3px 8px;
                    border-radius: 9999px;
                    font-size: 0.8rem;
                    font-weight: bold;
                    margin-right: 10px;
                }
                
                .status-online {
                    background-color: #2ECC40;
                    color: white;
                }
                
                .status-offline {
                    background-color: #FF4136;
                    color: white;
                }
                
                .status-stale {
                    background-color: #FF851B;
                    color: white;
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
    
    def show_toast(self, message):
        """Display a toast notification"""
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
    
    def setup_sidebar(self, db_manager, reranker, embeddings_model, ollama_base_url):
        """Set up the sidebar with all components"""
        with st.sidebar:
            st.header("📁 Document Management")
            uploaded_files = st.file_uploader(
                "Upload documents (PDF/DOCX/TXT)",
                type=["pdf", "docx", "txt"],
                accept_multiple_files=True
            )
            
            if uploaded_files and not st.session_state.documents_loaded:
                with st.spinner("Processing documents..."):
                    from utils.doc_handler import process_documents
                    process_documents(uploaded_files, reranker, embeddings_model, ollama_base_url)
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
                db_manager.clear_context_db()
                st.session_state.context = {}
                st.session_state.context_step = 0
                self.show_toast("Chat history and context have been successfully cleared.")
                st.session_state.retrieval_pipeline = None
                st.session_state.rag_enabled = False
                st.session_state.documents_loaded = False
                st.success("Chat history and context have been successfully cleared.")

            # Credits footer
            st.sidebar.markdown("""
                <div style="position: absolute; top: 20px; right: 10px; font-size: 12px; color: gray;">
                    <b>Developed by:</b> onedough83 &copy; All Rights Reserved 2025
                </div>
            """, unsafe_allow_html=True)

            st.markdown("---")
            st.header("🧠 Learning Style")
            st.session_state.learning_mode = st.checkbox("Learning Mode", value=st.session_state.learning_mode, 
                                                        help="When enabled, the AI will act like it knows nothing and ask questions to learn")
            
            if st.button("Reset Learned Topics"):
                st.session_state.conversation_topics = {}
                st.session_state.inquiry_depth = 0
                st.session_state.current_topic = None
                self.show_toast("Reset all learning progress!")

    def display_main_interface(self, db_manager):
        """Display the main interface with tabs for chat and dashboard"""
        # Get character names from the database
        director_info = db_manager.get_director_info()
        character_names = []
        
        if director_info and "character_names" in director_info:
            character_names = director_info["character_names"]
            
            # Only initialize agents if not already done to prevent repeated initialization
            if "health_agents_initialized" not in st.session_state:
                # Log once during initial setup
                print(f"Initializing health monitoring for characters: {character_names}")
                
                # Initialize health agents for all characters
                if character_names:
                    self.health_dashboard.initialize_agents(character_names)
                    # Mark as initialized in session state to prevent future repetition
                    st.session_state.health_agents_initialized = True
        else:
            print("No director info found, cannot initialize health agents")
        
        # Add the title in the header area before the tabs
        st.markdown('<h1 style="font-size:1.5rem; margin-bottom:0.5rem;">FFXaI Interface</h1>', unsafe_allow_html=True)
        
        # Create tabs for main content
        tab_chat, tab_dashboard = st.tabs(["💬 Chat", "📊 Character Dashboard"])
        
        # Chat tab content - Keep content minimal to save space
        with tab_chat:
            # Only show caption, not full title
            # st.caption("Advanced RAG System with GraphRAG, Hybrid Retrieval, Neural Reranking and Chat History")
            
            # This container will be used for messages
            message_container = st.container()
            
            # Return the message container for the main app to use for displaying messages
            return message_container, tab_dashboard
        
    def display_dashboard(self, tab_dashboard):
        """Display the health dashboard in the specified tab"""
        with tab_dashboard:
            # Keep title in dashboard tab
            st.title("Character Status Dashboard")
            st.caption("Real-time monitoring of your FFXI characters")
            
            # Add debug toggle
            debug_mode = st.checkbox("Show debug info", value=False)
            if debug_mode:
                st.code("TP values update in real-time. Last updated values are shown in the debug expander below.")
                
                with st.expander("Debug - Current session values"):
                    if "last_data_state" in st.session_state:
                        for char, data in st.session_state.last_data_state.items():
                            st.write(f"{char}: TP = {data.get('tp', 'N/A')}, Last update: {time.strftime('%H:%M:%S', time.localtime(data.get('refresh_time', 0)))}")
                    else:
                        st.write("No data collected yet")
            
            # Render the dashboard
            self.health_dashboard.render_dashboard()
    
    def display_messages(self, message_container):
        """Display all messages in the chat history within the given container"""
        with message_container:
            for message in st.session_state.messages:
                with st.chat_message(message["role"]):
                    st.markdown(message["content"])
