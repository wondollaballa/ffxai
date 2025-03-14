import streamlit as st
import time
import pandas as pd
from agents.health_agent import HealthAgent
from agents.ffxi_agent import FFXIAgent
from agents.state_store import state_store  # Import the state store
import os
import logging
from streamlit.components.v1 import html
import uuid
import json
from ui.ui_helpers import UIComponents, UIStyles

logger = logging.getLogger("health_dashboard")

# Add a filter to suppress specific log messages
class MessageFilter(logging.Filter):
    def __init__(self, excluded_messages):
        self.excluded_messages = excluded_messages

    def filter(self, record):
        return not any(message in record.getMessage() for message in self.excluded_messages)

# Apply the filter to the logger
excluded_messages = ["missing ScriptRunContext! This warning can be ignored when running in bare mode."]
message_filter = MessageFilter(excluded_messages)
logger.addFilter(message_filter)

class HealthDashboard:
    """Dashboard to display character health and status information"""
    
    def __init__(self):
        """Initialize the health dashboard"""
        # Initialize health_agents from session state if it exists
        if "health_agents" in st.session_state:
            self.health_agents = st.session_state.health_agents
        else:
            self.health_agents = {}
        
        # Initialize session state variables explicitly
        if "refresh_counter" not in st.session_state:
            st.session_state.refresh_counter = 0
        
        if "reactive_update_counter" not in st.session_state:
            st.session_state.reactive_update_counter = 0
            
        if "reactive_updates" not in st.session_state:
            st.session_state.reactive_updates = {}
        
        if "last_reactive_update" not in st.session_state:
            st.session_state.last_reactive_update = time.time()
                
        # Initialize last data state for change detection
        if "last_data_state" not in st.session_state:
            st.session_state.last_data_state = {}

        self.last_refresh = time.time()
        self.refresh_interval = 3  # Set 3 second refresh interval
        
        if "last_data_read" not in st.session_state:
            st.session_state.last_data_read = {}

    def initialize_agents(self, character_names):
        """Initialize health agents for all characters"""
        if not character_names:
            logger.warning("No character names provided to initialize_agents")
            return
        
        # Log the character names being initialized
        logger.info(f"Initializing health agents for characters: {character_names}")
        
        for name in character_names:
            if name.strip():  # Skip empty names
                if name not in self.health_agents:
                    logger.info(f"Creating health agent for: {name}")
                    self.health_agents[name] = HealthAgent(name, cadence=3)  # Initialize with cadence
                else:
                    logger.info(f"Health agent for {name} already exists")
        
        # Log summary of initialized agents
        logger.info(f"Total health agents initialized: {len(self.health_agents)}")
        logger.info(f"Active agents: {list(self.health_agents.keys())}")
        
        # Set up our reactive callbacks for real-time UI updates
        self._setup_reactive_callbacks()
        
        # Store health_agents in session state
        st.session_state.health_agents = self.health_agents

    def _setup_reactive_callbacks(self):
        """Set up reactive callbacks for data updates"""
        # Remove all subscriber callbacks
        pass

    def _stream_health_data(self):
        """Stream health data from JSON files"""
        for char_name, agent in self.health_agents.items():
            try:
                data = agent.read_health_data()
                if data and char_name in data:
                    # Update the timestamp for this character
                    st.session_state.last_data_read[char_name] = {
                        "timestamp": data[char_name].get("timestamp", time.time()),
                        "formatted": UIComponents.format_timestamp(data[char_name].get("timestamp", time.time()))
                    }
            except Exception as e:
                logger.debug(f"Could not read data for {char_name}: {e}")
                continue

    def render_dashboard(self):
        """Render the health dashboard with tabs for each character"""
        # Display refresh message
        st.warning("Please manually refresh or upgrade Streamlit for auto-refresh.")

        if not self.health_agents:
            st.warning("No character health data available. Please set up your characters first.")
            return
        
        # Check for updates in the state store and update session state
        updates, had_updates = state_store.get_pending_updates()
        if had_updates:
            if "reactive_updates" not in st.session_state:
                st.session_state.reactive_updates = {}
                
            # Add new updates to session state
            for key, update in updates.items():
                st.session_state.reactive_updates[key] = update
            
            # Increment counter for UI updates
            if "reactive_update_counter" not in st.session_state:
                st.session_state.reactive_update_counter = 0
            st.session_state.reactive_update_counter += 1
            
            # Update timestamp
            st.session_state.last_reactive_update = time.time()
            logger.info(f"Updated session state with {len(updates)} pending updates")
        
        # Stream data if enough time has passed
        current_time = time.time()
        if current_time - self.last_refresh >= self.refresh_interval:
            self._stream_health_data()
            self.last_refresh = current_time

        # Create tabs for all characters + overview
        tabs = ["Overview"] + list(self.health_agents.keys())
        selected_tab = st.tabs(tabs)
        
        # Overview tab shows all characters in a compact format
        with selected_tab[0]:
            self._render_overview_tab()
        
        # Individual character tabs
        for i, char_name in enumerate(self.health_agents.keys(), 1):
            with selected_tab[i]:
                self._render_character_tab(char_name)
    
    def _refresh_data(self, force=False):
        """Basic data refresh without auto-refresh logic"""
        agent_count = len(self.health_agents)
        logger.debug(f"Refreshing health data for {agent_count} agents")
        
        current_state = {}
        
        for char_name, agent in self.health_agents.items():
            try:
                data = agent.read_health_data()
                if data and char_name in data:
                    # Extract basic data
                    char_data = data[char_name]
                    vitals = char_data.get("vitals", {})
                    current_state[char_name] = {
                        "hp": vitals.get("hp", 0),
                        "mp": vitals.get("mp", 0),
                        "tp": vitals.get("tp", 0),
                        "timestamp": char_data.get("timestamp", 0),
                        "refresh_time": time.time()
                    }
            except Exception as e:
                logger.error(f"Error refreshing {char_name}: {e}")
        
        st.session_state.last_data_state = current_state

    def _render_overview_tab(self):
        """Render an overview of all characters"""
        st.subheader("Character Overview")
        
        # Create a table for basic info
        overview_data = []
        has_errors = False
        
        # Add last update information
        if "last_reactive_update" in st.session_state:
            last_update = time.time() - st.session_state.last_reactive_update
            if last_update < 60:
                st.caption(f"Last data update: {int(last_update)} seconds ago")
        
        # Create a container for the refreshable content with a data attribute
        with st.container():
            st.markdown(f'<div data-health-agent="overview" data-refresh-count="{st.session_state.get("reactive_update_counter", 0)}">', unsafe_allow_html=True)
            
            for char_name, agent in self.health_agents.items():
                # Get data from agent and state store
                status = agent.get_status_summary()
                character_data = state_store.get_state(f"character:{char_name}", {})
                
                # Get timestamp from the most recent source
                timestamp = None
                if character_data and "timestamp" in character_data:
                    timestamp = character_data["timestamp"]
                elif agent.last_timestamp:
                    timestamp = agent.last_timestamp
                
                formatted_timestamp = UIComponents.format_timestamp(timestamp)
                
                # Build overview data with formatted timestamp
                if status.get("status") == "No data available":
                    overview_data.append({
                        "Name": char_name,
                        "Status": "Offline",
                        "HP": "N/A",
                        "MP": "N/A", 
                        "TP": "N/A",
                        "Zone": "Unknown",
                        "Last Update": formatted_timestamp,
                        "Error": status.get("error", "")
                    })
                    continue
                    
                overview_data.append({
                    "Name": char_name,
                    "Status": "Online" if status.get("is_running", False) else "Stale data",
                    "HP": status.get("hp", "N/A"),
                    "MP": status.get("mp", "N/A"),
                    "TP": str(status.get("tp", 0)),
                    "Zone": status.get("zone", "Unknown"),
                    "Last Update": formatted_timestamp,
                    "Error": status.get("error", "")
                })
            
            # Show error message if any characters have errors
            if has_errors:
                st.warning("Some characters have errors. Check the 'Error' column or individual tabs for details.")
            
            # Convert to DataFrame for display
            if overview_data:
                df = pd.DataFrame(overview_data)
                st.dataframe(df, use_container_width=True)
                
                # Display visual health bars below the table
                st.subheader("Health & MP Status")
                cols = st.columns(len(self.health_agents))
                
                for i, (char_name, agent) in enumerate(self.health_agents.items()):
                    with cols[i]:
                        st.subheader(char_name)
                        # Get status directly from state store for most recent data
                        character_data = state_store.get_state(f"character:{char_name}", {})
                        if character_data and "vitals" in character_data:
                            # Build a hybrid status object with fresh data
                            fresh_status = agent.get_status_summary()
                            vitals = character_data.get("vitals", {})
                            
                            # Update vitals in fresh_status
                            self._update_status_with_vitals(fresh_status, vitals)
                            
                            # Render with fresh data
                            self._render_character_bars(char_name, fresh_status)
                        else:
                            # Fall back to agent data
                            status = agent.get_status_summary()
                            self._render_character_bars(char_name, status)
            
            # Close the refreshable container
            st.markdown('</div>', unsafe_allow_html=True)
            
    def _update_status_with_vitals(self, status, vitals):
        """Update status object with vitals data for rendering"""
        if "hp" in vitals and "hp_max" in vitals:
            hp = vitals.get("hp", 0)
            hp_max = vitals.get("hp_max", 1) 
            hp_percent = round((hp / hp_max) * 100) if hp_max > 0 else 0
            status["hp"] = f"{hp}/{hp_max} ({hp_percent}%)"
        
        if "mp" in vitals and "mp_max" in vitals:
            mp = vitals.get("mp", 0)
            mp_max = vitals.get("mp_max", 1)
            mp_percent = round((mp / mp_max) * 100) if mp_max > 0 else 0
            status["mp"] = f"{mp}/{mp_max} ({mp_percent}%)"
        
        if "tp" in vitals:
            status["tp"] = vitals.get("tp", 0)

    def _render_character_tab(self, char_name):
        """Render detailed information for a single character"""
        # Create a container for the refreshable character content with a data attribute
        st.markdown(f'<div data-health-agent="{char_name}">', unsafe_allow_html=True)
        
        agent = self.health_agents[char_name]
        status = agent.get_status_summary()
        
        # Character header and basic info
        st.subheader(f"{char_name}")
        
        # Show errors if any
        if status.get("error"):
            st.error(f"Error: {status.get('error')}")
        
        # Visual indicators for online status
        UIComponents.render_status_indicator(
            status.get("is_running", False),
            status.get('last_update_dt', 'Unknown')
        )
            
        # Character information in columns
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("### Character Info")
            if status.get("status") == "No data available" or status.get("error"):
                st.info("No data available for this character. Make sure the HealthCheck addon is running.")
                st.markdown("#### Data Path")
                st.code(agent.json_file, language=None)
            else:
                st.markdown(f"**Job:** {status.get('jobs', 'Unknown')}")
                st.markdown(f"**Location:** {status.get('zone', 'Unknown')}")
                st.markdown(f"**Status:** {status.get('status', 'Unknown')}")
                if status.get("target") and status.get("target") != "None":
                    st.markdown(f"**Target:** {status.get('target', 'None')}")
        
        with col2:
            # Render health bars
            self._render_character_bars(char_name, status, large=True)
        
        # Display buffs
        if status.get("status") != "No data available":
            st.markdown("### Active Buffs")
            buffs = status.get("buffs", [])
            if buffs:
                # Create a DataFrame with a single column for buffs
                buff_data = pd.DataFrame(buffs, columns=["Buff"])
                st.dataframe(buff_data, use_container_width=True)
            else:
                st.markdown("No buffs active.")
        
        # Combat information (if available)
        st.markdown("### Location")
        st.markdown(f"**Position:** {status.get('position', 'Unknown')}")
        
        # Display a map or placeholder for map
        if status.get("zone") != "Unknown":
            st.markdown("#### Zone Map")
            map_placeholder = st.empty()
            # For now we just display a placeholder - in a real app you might
            # show an actual zone map with the character's position
            map_placeholder.info(f"Map for {status.get('zone', 'Unknown')} would be displayed here")
        
        # Advanced actions
        st.markdown("### Actions")
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button(f"Send Warp Command to {char_name}", key=f"warp_{char_name}"):
                agent.send_command("/warp")
                st.success(f"Warp command sent to {char_name}")
        
        with col2:
            if st.button(f"Refresh {char_name} Data", key=f"refresh_{char_name}"):
                agent.read_health_data()
                st.success(f"Refreshed data for {char_name}")
        
        # Close the refreshable container
        st.markdown('</div>', unsafe_allow_html=True)
        
        # Debug info (outside the refreshable container)
        with st.expander("Debug Information"):
            st.markdown("#### JSON File Path")
            st.code(agent.json_file, language=None)
            
            st.markdown("#### Last Timestamp")
            st.text(f"Last timestamp: {agent.last_timestamp}")
            
            st.markdown("#### Raw Data (if available)")
            if agent.last_data and char_name in agent.last_data:
                st.json(agent.last_data[char_name])
            else:
                st.text("No raw data available")

    def _render_character_bars(self, char_name, status, large=False):
        """Render HP/MP/TP bars for a character"""
        if status.get("status") == "No data available" or status.get("error"):
            if large:
                st.info("No health data available")
            return
            
        # Get HP/MP values and percentages
        try:
            hp_value = status.get("hp", "0/0")
            mp_value = status.get("mp", "0/0")
            tp_value = status.get("tp", 0)
            
            # Force int conversion for TP to ensure correct type
            try:
                tp_value = int(tp_value)
            except (TypeError, ValueError):
                tp_value = 0
            
            # Log TP values at debug level to reduce spam
            logger.debug(f"TP for {char_name}: {tp_value}")
            
            # Extract percentages from HP/MP strings
            hp_pct = int(hp_value.split('(')[1].split('%')[0]) if '(' in hp_value else 0
            mp_pct = int(mp_value.split('(')[1].split('%')[0]) if '(' in mp_value else 0
            
            # Set bar height based on size parameter
            bar_height = '24px' if large else '16px'
            
            # Use our UI components to render bars
            container = st.container()
            
            # Create horizontal bars with improved text positioning and reactive data attributes
            container.markdown("**HP:**")
            container.markdown(
                f"""<div style="width:100%; background-color:#444; height:{bar_height}; border-radius:10px; position:relative;">
                    <div style="width:{hp_pct}%; background-color:{UIStyles.get_bar_colors(hp_pct)}; height:100%; border-radius:10px;"></div>
                    <div style="position:absolute; top:0; left:0; width:100%; height:100%; display:flex; align-items:center; justify-content:center; color:white; font-weight:bold; text-shadow: 1px 1px 2px #000;">
                        {hp_value}
                    </div>
                </div>""", 
                unsafe_allow_html=True
            )
            
            container.markdown("**MP:**")
            container.markdown(
                f"""<div style="width:100%; background-color:#444; height:{bar_height}; border-radius:10px; position:relative;">
                    <div style="width:{mp_pct}%; background-color:{UIStyles.get_bar_colors(mp_pct, "blue")}; height:100%; border-radius:10px;"></div>
                    <div style="position:absolute; top:0; left:0; width:100%; height:100%; display:flex; align-items:center; justify-content:center; color:white; font-weight:bold; text-shadow: 1px 1px 2px #000;">
                        {mp_value}
                    </div>
                </div>""", 
                unsafe_allow_html=True
            )
            
            # Render TP bar using our component
            UIComponents.render_tp_bar(tp_value, char_name, bar_height)
            
        except Exception:
            # Default values if parsing fails
            st.error("Error parsing character status data")

def main():
    # Initialize and render the UI using our helpers
    UIComponents.render_header()
    
    # Add refresh button at the top of the dashboard
    col1, col2 = st.columns([3, 1])
    with col1:
        st.header("Character Health Status")
    with col2:
        # Add the refresh button from the state store
        refresh_clicked = state_store.add_refresh_button("Refresh Health Data", key="health_refresh")
        if refresh_clicked:
            st.info("Refreshing character data...")
    
    # Get any pending updates
    updates, had_updates = state_store.get_pending_updates()
    logger.info(f"Health dashboard received: had_updates={had_updates}, updates count={len(updates)}")
    
    # Process and display character health data
    if had_updates or updates:
        logger.info("Processing new updates in health dashboard")
        display_character_health(updates)
    else:
        # Still display whatever data we have in the state store
        display_character_health({})
        
def display_character_health(updates):
    """Display character health information from state store"""
    # Get all state to look for character data
    all_state = state_store.get_all_state()
    
    # Find all character data in the state
    character_keys = [k for k in all_state.keys() if k.startswith("character:")]
    
    if not character_keys:
        st.warning("No character data available. Please ensure data is being collected.")
        return
    
    # Display each character's health information
    for char_key in character_keys:
        char_name = char_key.split(":")[1]
        char_data = state_store.get_state(char_key)
        
        if not char_data:
            continue
            
        with st.expander(f"{char_name}", expanded=True):
            col1, col2, col3 = st.columns(3)
            
            # Display vitals if available
            if "vitals" in char_data:
                vitals = char_data["vitals"]
                with col1:
                    hp = vitals.get("hp", {})
                    st.metric("HP", f"{hp.get('current', 0)}/{hp.get('max', 0)}")
                    
                    # Create a progress bar for HP
                    if "current" in hp and "max" in hp and hp["max"] > 0:
                        hp_percent = min(100, max(0, (hp["current"] / hp["max"]) * 100))
                        st.progress(hp_percent / 100)
                
                with col2:
                    mp = vitals.get("mp", {})
                    st.metric("MP", f"{mp.get('current', 0)}/{mp.get('max', 0)}")
                    
                    # Create a progress bar for MP
                    if "current" in mp and "max" in mp and mp["max"] > 0:
                        mp_percent = min(100, max(0, (mp["current"] / mp["max"]) * 100))
                        st.progress(mp_percent / 100)
                
                with col3:
                    tp = vitals.get("tp", {})
                    if tp:  # Some characters might not have TP
                        st.metric("TP", f"{tp.get('current', 0)}/{tp.get('max', 0)}")
                        
                        # Create a progress bar for TP
                        if "current" in tp and "max" in tp and tp["max"] > 0:
                            tp_percent = min(100, max(0, (tp["current"] / tp["max"]) * 100))
                            st.progress(tp_percent / 100)
            
            # Display other character information if available
            if "status" in char_data:
                st.subheader("Status Effects")
                status_effects = char_data["status"]
                if status_effects:
                    for effect in status_effects:
                        st.text(f"• {effect}")
                else:
                    st.text("No status effects")

if __name__ == "__main__":
    main()
