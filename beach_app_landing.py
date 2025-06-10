#!/usr/bin/env python3
"""
Blue Flag Beaches Greece - Smart Device Detection Landing Page  
Uses URL parameters for reliable device detection and automatic app switching
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

def show_device_detection():
    """Show device detection interface with automatic redirect"""
    
    # Get Blue Flag image
    img_base64 = get_base64_of_image("blue_flag_image.ico")
    
    # Landing page header
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

    # Auto-detection script using URL parameters (reliable method)
    detection_script = """
    <script>
    function detectDeviceAndRedirect() {
        const userAgent = navigator.userAgent.toLowerCase();
        const isMobile = /android|webos|iphone|ipad|ipod|blackberry|iemobile|opera mini|mobile/.test(userAgent);
        const isTablet = /ipad|android(?!.*mobile)|tablet/.test(userAgent);
        
        // Get current URL without parameters
        const baseUrl = window.location.origin + window.location.pathname;
        
        if (isMobile || isTablet) {
            console.log('Mobile/Tablet detected - redirecting with mobile parameter');
            window.location.href = baseUrl + '?device=mobile';
        } else {
            console.log('Desktop detected - redirecting with desktop parameter');
            window.location.href = baseUrl + '?device=desktop';
        }
    }
    
    // Run detection after a brief delay to show the detection message
    setTimeout(detectDeviceAndRedirect, 1500);
    </script>
    
    <div style="text-align: center; padding: 40px;">
        <div style="display: inline-block; width: 50px; height: 50px; border: 4px solid #f3f3f3; border-top: 4px solid #0066cc; border-radius: 50%; animation: spin 1s linear infinite; margin-bottom: 20px;"></div>
        <h3 style="color: #0066cc;">🔍 Detecting Your Device</h3>
        <p style="color: #666; font-size: 16px;">Please wait while we determine the best experience for you...</p>
        <p style="color: #999; font-size: 14px; margin-top: 20px;">This will only take a moment</p>
    </div>
    
    <style>
    @keyframes spin {
        0% { transform: rotate(0deg); }
        100% { transform: rotate(360deg); }
    }
    </style>
    """
    
    components.html(detection_script, height=300)

def show_desktop_app():
    """Show desktop version"""
    try:
        # Import desktop app functions and run them
        exec(open('flag.py').read(), {'__name__': '__main__'})
    except Exception as e:
        st.error(f"Error loading desktop app: {e}")
        st.info("Please try refreshing the page.")
        if st.button("🔄 Retry"):
            st.rerun()

def show_mobile_app():
    """Show mobile version"""
    try:
        # Import mobile app functions and run them
        exec(open('mobile_beach_app.py').read(), {'__name__': '__main__'})
    except Exception as e:
        st.error(f"Error loading mobile app: {e}")
        st.info("Please try refreshing the page.")
        if st.button("🔄 Retry"):
            st.rerun()

def main():
    """Main application logic with URL parameter detection"""
    
    # Check URL parameters for device type
    device_type = st.query_params.get("device")
    
    if device_type == "desktop":
        # Show desktop app
        st.markdown("### 🖥️ Desktop Version")
        show_desktop_app()
        
    elif device_type == "mobile":
        # Show mobile app  
        st.markdown("### 📱 Mobile Version")
        show_mobile_app()
        
    else:
        # Show device detection page (first visit)
        show_device_detection()
        
        # Footer for detection page
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
