#!/usr/bin/env python3
"""
Blue Flag Beaches Greece - Smart Device Detection Landing Page
Main entry point that detects device and shows appropriate interface
"""

import streamlit as st
import streamlit.components.v1 as components
import base64
import os

# Configure the landing page
st.set_page_config(
    page_title="🏖️ Blue Flag Beaches Greece",
    page_icon="🏖️",
    layout="wide"
)

def get_base64_of_image(path):
    """Get base64 encoded image - deployment safe"""
    try:
        if os.path.exists(path):
            with open(path, "rb") as img_file:
                return base64.b64encode(img_file.read()).decode()
    except:
        pass
    return None

def auto_detect_and_redirect():
    """Auto-detect device and redirect to appropriate version"""
    
    # Get Blue Flag image
    img_base64 = get_base64_of_image("blue_flag_image.ico")
    
    # Landing page header with auto-redirect message
    if img_base64:
        st.markdown(f"""
        <div style="background: linear-gradient(135deg, #0053ac 0%, #0077c8 100%); 
                    padding: 30px; border-radius: 15px; margin-bottom: 30px; text-align: center;">
            <h1 style="color: white; margin: 0; font-size: 36px; display: flex; align-items: center; justify-content: center;">
                <img src="data:image/png;base64,{img_base64}" style="height: 70px; 
                                                                    width: 70px; 
                                                                    margin-right: 15px; 
                                                                    padding: 10px; 
                                                                    background-color: white; 
                                                                    border-radius: 10px; 
                                                                    border: 3px solid #ccc;"> 
                Blue Flag Beaches Greece
            </h1>
            <p style="color: white; margin: 15px 0 0 0; font-size: 18px;">
                Interactive map of Greece's certified Blue Flag beaches with live conditions
            </p>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown("""
        <div style="background: linear-gradient(135deg, #0053ac 0%, #0077c8 100%); 
                    padding: 30px; border-radius: 15px; margin-bottom: 30px; text-align: center;">
            <h1 style="color: white; margin: 0; font-size: 36px;">
                🌊 Blue Flag Beaches Greece
            </h1>
            <p style="color: white; margin: 15px 0 0 0; font-size: 18px;">
                Interactive map of Greece's certified Blue Flag beaches with live conditions
            </p>
        </div>
        """, unsafe_allow_html=True)

    # Auto-detection script that sets session state
    detection_script = """
    <script>
    function detectDeviceAndSetState() {
        const userAgent = navigator.userAgent.toLowerCase();
        const isMobile = /android|webos|iphone|ipad|ipod|blackberry|iemobile|opera mini|mobile/.test(userAgent);
        const isTablet = /ipad|android(?!.*mobile)|tablet/.test(userAgent);
        
        if (isMobile || isTablet) {
            console.log('Mobile/Tablet detected - setting mobile version');
            // Use Streamlit's method to set session state
            window.parent.postMessage({
                type: 'streamlit:setSessionState',
                data: {selected_version: 'mobile'}
            }, '*');
        } else {
            console.log('Desktop detected - setting desktop version');
            // Use Streamlit's method to set session state  
            window.parent.postMessage({
                type: 'streamlit:setSessionState', 
                data: {selected_version: 'desktop'}
            }, '*');
        }
    }
    
    // Run detection immediately
    detectDeviceAndSetState();
    
    // Also trigger after a short delay to ensure Streamlit is ready
    setTimeout(detectDeviceAndSetState, 1000);
    </script>
    
    <div style="text-align: center; padding: 20px;">
        <div style="display: inline-block; width: 40px; height: 40px; border: 4px solid #f3f3f3; border-top: 4px solid #0066cc; border-radius: 50%; animation: spin 1s linear infinite; margin-bottom: 15px;"></div>
        <h3>🔍 Detecting Your Device</h3>
        <p>Please wait while we determine the best experience for you...</p>
    </div>
    
    <style>
    @keyframes spin {
        0% { transform: rotate(0deg); }
        100% { transform: rotate(360deg); }
    }
    </style>
    """
    
    components.html(detection_script, height=200)
    
    # Auto-trigger session state check
    if 'device_detected' not in st.session_state:
        st.session_state.device_detected = True
        st.rerun()

def show_desktop_app():
    """Show desktop version"""
    try:
        # Import and run desktop app
        exec(open('flag.py').read())
    except Exception as e:
        st.error(f"Error loading desktop app: {e}")
        st.info("Please try refreshing the page or contact support.")

def show_mobile_app():
    """Show mobile version"""
    try:
        # Import and run mobile app  
        exec(open('mobile_beach_app.py').read())
    except Exception as e:
        st.error(f"Error loading mobile app: {e}")
        st.info("Please try refreshing the page or contact support.")

def main():
    """Main application logic"""
    
    # Initialize session state
    if 'selected_version' not in st.session_state:
        st.session_state.selected_version = None
    
    # Show appropriate interface based on selection
    if st.session_state.selected_version == "desktop":
        # Add back button
        if st.button("← Back to Home", type="secondary"):
            st.session_state.selected_version = None
            st.rerun()
        
        st.markdown("---")
        show_desktop_app()
        
    elif st.session_state.selected_version == "mobile":
        # Add back button
        if st.button("← Back to Home", type="secondary"):
            st.session_state.selected_version = None
            st.rerun()
            
        st.markdown("---")
        show_mobile_app()
        
    else:
        # Show landing page with auto-detection
        auto_detect_and_redirect()

    # Footer
    if st.session_state.selected_version is None:
        st.markdown("""
        ---
        <div style="text-align: center; color: #666; font-size: 0.9em; padding: 20px;">
            <p><strong>Blue Flag Beaches Greece</strong></p>
            <p>Environmental Excellence Certified • Live Weather Conditions • Comprehensive Database</p>
            <p>🇬🇷 Explore the best beaches in Greece with confidence</p>
        </div>
        """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()
