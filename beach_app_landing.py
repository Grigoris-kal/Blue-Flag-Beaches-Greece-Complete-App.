#!/usr/bin/env python3
"""
Blue Flag Beaches Greece - Smart Device Detection & Redirect Landing Page
Main entry point that detects device and redirects to appropriate version
"""

import streamlit as st
import streamlit.components.v1 as components
import base64

# Configure the landing page
st.set_page_config(
    page_title="🏖️ Blue Flag Beaches Greece",
    page_icon="blue_flag_image.png",  # Use Blue Flag image
    layout="centered"
)

def detect_and_redirect():
    """Auto-detect device and redirect to appropriate app"""
    
    # JavaScript for device detection and auto-redirect
    redirect_script = """
    <script>
    function detectDeviceAndRedirect() {
        const userAgent = navigator.userAgent.toLowerCase();
        const isMobile = /android|webos|iphone|ipad|ipod|blackberry|iemobile|opera mini|mobile/.test(userAgent);
        const isTablet = /ipad|android(?!.*mobile)|tablet/.test(userAgent);
        
        // Get current URL base (works for any hosting platform)
        const currentUrl = window.location.origin;
        
        // Define redirect URLs (hosting-ready)
        const mobileUrl = currentUrl + '/mobile';
        const desktopUrl = currentUrl + '/desktop';
        
        // Redirect based on device type
        if (isMobile || isTablet) {
            console.log('Mobile/Tablet detected - redirecting to mobile version');
            window.location.href = mobileUrl;
        } else {
            console.log('Desktop detected - redirecting to desktop version');
            window.location.href = desktopUrl;
        }
    }
    
    // Auto-redirect after 2 seconds
    setTimeout(detectDeviceAndRedirect, 2000);
    </script>
    
    <style>
    .redirect-container {
        text-align: center;
        padding: 2rem;
        background: linear-gradient(135deg, #0053ac 0%, #0077c8 100%);
        border-radius: 15px;
        margin: 2rem 0;
        color: white;
    }
    .spinner {
        border: 4px solid #f3f3f3;
        border-top: 4px solid #0077c8;
        border-radius: 50%;
        width: 40px;
        height: 40px;
        animation: spin 1s linear infinite;
        margin: 20px auto;
    }
    @keyframes spin {
        0% { transform: rotate(0deg); }
        100% { transform: rotate(360deg); }
    }
    </style>
    
    <div class="redirect-container">
        <h1>🏖️ Blue Flag Beaches Greece</h1>
        <div class="spinner"></div>
        <p>Detecting your device and redirecting to the best experience...</p>
        <hr style="margin: 2rem 0; border-color: rgba(255,255,255,0.3);">
        <p><strong>Manual Selection:</strong></p>
        <p>
            <a href="/desktop" style="color: #FFD700; text-decoration: none; margin: 0 10px;">
               🖥️ Desktop Version
            </a> | 
            <a href="/mobile" style="color: #FFD700; text-decoration: none; margin: 0 10px;">
               📱 Mobile Version
            </a>
        </p>
    </div>
    """
    
    components.html(redirect_script, height=400)

def main():
    # Function to encode image to base64
    def get_base64_of_image(path):
        with open(path, "rb") as img_file:
            return base64.b64encode(img_file.read()).decode()

    # Get base64 string of your Blue Flag image
    try:
        img_base64 = get_base64_of_image("blue_flag_image.png")
    except:
        img_base64 = ""

    # Landing page header with Blue Flag image
    if img_base64:
        st.markdown(f"""
        <div style="background: linear-gradient(135deg, #0053ac 0%, #0077c8 100%); 
                    padding: 20px; border-radius: 15px; margin-bottom: 20px; text-align: center;">
            <h1 style="color: white; margin: 0; font-size: 28px; display: flex; align-items: center; justify-content: center;">
                <img src="data:image/png;base64,{img_base64}" style="height: 50px; 
                                                                    width: 50px; 
                                                                    margin-right: 15px; 
                                                                    padding: 8px; 
                                                                    background-color: white; 
                                                                    border-radius: 8px; 
                                                                    border: 2px solid #ccc;
                                                                    filter: drop-shadow(2px 2px 4px rgba(0,0,0,0.5));"> 
                🌊 Welcome to Blue Flag Beaches Greece
            </h1>
            <p style="color: white; margin: 10px 0 0 0; font-size: 16px;">
                Automatically detecting your device for the best experience...
            </p>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown("""
        <div style="background: linear-gradient(135deg, #0053ac 0%, #0077c8 100%); 
                    padding: 20px; border-radius: 15px; margin-bottom: 20px; text-align: center;">
            <h1 style="color: white; margin: 0; font-size: 28px;">
                🌊 Welcome to Blue Flag Beaches Greece
            </h1>
            <p style="color: white; margin: 10px 0 0 0; font-size: 16px;">
                Automatically detecting your device for the best experience...
            </p>
        </div>
        """, unsafe_allow_html=True)
    
    # Auto-detection and redirect
    detect_and_redirect()
    
    # Footer info
    st.markdown("""
    ---
    <div style="text-align: center; color: #666; font-size: 0.9em;">
        <p>🏖️ Interactive map of Greece's certified Blue Flag beaches</p>
        <p>📱 Mobile-optimized • 🖥️ Desktop-enhanced • 🌊 Live weather data</p>
    </div>
    """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()