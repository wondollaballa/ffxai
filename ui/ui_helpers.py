"""
UI helpers for FFXAI dashboards - centralizes UI components and styles
"""
import streamlit as st
import logging
import time

logger = logging.getLogger("ui_helpers")

class UIStyles:
    """
    Class containing stylesheet definitions and UI styling helpers
    """
    @staticmethod
    def apply_base_styles():
        """Apply base styles to the streamlit app - using all available whitespace"""
        st.markdown(
            """
            <style>
            .main { margin: 0; padding: 0; }
            .main .block-container { margin: 0 !important; padding: 0 !important; }
            </style>
            """,
            unsafe_allow_html=True
        )
    
    @staticmethod
    def get_bar_colors(percentage, base_color="red"):
        """Generate color based on percentage value"""
        if base_color == "red":
            # Red (low) to green (high)
            if percentage < 25:
                return "#FF4136"  # Red
            elif percentage < 50:
                return "#FF851B"  # Orange
            elif percentage < 75:
                return "#FFDC00"  # Yellow
            else:
                return "#2ECC40"  # Green
        elif base_color == "blue":
            # Light blue (low) to deep blue (high)
            if percentage < 25:
                return "#7FDBFF"  # Light blue
            elif percentage < 50:
                return "#39CCCC"  # Teal
            elif percentage < 75:
                return "#0074D9"  # Blue
            else:
                return "#001f3f"  # Navy
        elif base_color == "gold":
            return "#FFD700" if percentage >= 100 else "#DAA520"  # Gold when full, darker gold otherwise
        return "#777777"  # Default gray

class UIComponents:
    """
    Reusable UI components for FFXAI dashboards
    """
    @staticmethod
    def render_header():
        """Render the main header with set page config"""
        st.set_page_config(layout="wide")
        UIStyles.apply_base_styles()
        st.title("FFXIV Character Health Dashboard")

    @staticmethod
    def render_health_bar(value, max_value, label, height='16px', color_base="red"):
        """Render a health/mana/resource bar"""
        container = st.container()
        
        # Calculate percentage
        if max_value > 0:
            percentage = min(100, max(0, (value / max_value) * 100))
        else:
            percentage = 0
            
        # Get color based on percentage
        color = UIStyles.get_bar_colors(percentage, color_base)
        
        # Create the bar
        container.markdown(f"**{label}:**")
        container.markdown(
            f"""<div style="width:100%; background-color:#444; height:{height}; border-radius:10px; position:relative;">
                <div style="width:{percentage}%; background-color:{color}; height:100%; border-radius:10px;"></div>
                <div style="position:absolute; top:0; left:0; width:100%; height:100%; display:flex; align-items:center; justify-content:center; color:white; font-weight:bold; text-shadow: 1px 1px 2px #000;">
                    {value}/{max_value} ({int(percentage)}%)
                </div>
            </div>""", 
            unsafe_allow_html=True
        )
        
        return container
    
    @staticmethod
    def render_tp_bar(tp_value, char_name, height='16px'):
        """Render a TP bar with special styling"""
        container = st.container()
        
        # TP is 0-3000
        tp_pct = min(int(tp_value / 30), 100)
        tp_color = UIStyles.get_bar_colors(tp_pct, "gold")
        
        # Create the TP bar with reactive data attributes
        container.markdown(f"**TP: <span data-tp-value='{char_name}'>{tp_value}</span>/3000**", unsafe_allow_html=True)
        container.markdown(
            f"""<div style="width:100%; background-color:#444; height:{height}; border-radius:10px; position:relative;">
                <div data-tp-bar="{char_name}" style="width:{tp_pct}%; background-color:{tp_color}; height:100%; border-radius:10px; transition: width 0.3s ease;"></div>
                <div style="position:absolute; top:0; left:0; width:100%; height:100%; display:flex; align-items:center; justify-content:center; color:white; font-weight:bold; text-shadow: 1px 1px 2px #000;">
                    <span data-tp-value='{char_name}'>{tp_value}</span>/3000
                </div>
            </div>""", 
            unsafe_allow_html=True
        )
        
        return container
        
    @staticmethod
    def format_timestamp(timestamp):
        """Convert timestamp to human readable format"""
        try:
            return time.strftime("%m/%d/%Y %I:%M:%S %p", time.localtime(float(timestamp)))
        except (ValueError, TypeError):
            return "Never"
            
    @staticmethod
    def render_status_indicator(is_online, last_update_dt):
        """Render an online/offline status indicator"""
        if is_online:
            return st.markdown(f"<span style='color:green; font-weight:bold;'>● ONLINE</span> - Last updated: {last_update_dt}", unsafe_allow_html=True)
        else:
            return st.markdown(f"<span style='color:orange; font-weight:bold;'>● OFFLINE</span> - Last seen: {last_update_dt}", unsafe_allow_html=True)
