#!/usr/bin/env python3
"""
Blue Flag Beaches Greece - Landing Page with URL-internal Redirects
User sees 1 URL, system uses URL-internal for routing
"""

import streamlit as st
import streamlit.components.v1 as components
import base64

# Set page config for landing page
st.set_page_config(
    page_title="🏖️ Blue Flag Beaches Greece",
    page_icon="🌊",
    layout="centered"
)

def detect_and_redirect():
    """Auto-detect device and redirect to appropriate URL-internal"""
    
    redirect_script = """
    <script>
    function detectDeviceAndRedirect() {
        const userAgent = navigator.userAgent.toLowerCase();
        const isMobile = /android|webos|iphone|ipad|ipod|blackberry|iemobile|opera mini|mobile/.test(userAgent);
        const isTablet = /ipad|android(?!.*mobile)|tablet/.test(userAgent);
        
        // Get current URL base
        const currentUrl = window.location.origin;
        
        // Define URL-internal paths (using query parameters - no folder changes needed)
        const mobileUrlInternal = currentUrl + '/?app=mobile_beach_app';  // -> mobile_beach_app.py
        const desktopUrlInternal = currentUrl + '/?app=flag';             // -> flag.py
        
        // Redirect based on device type to URL-internal
        if (isMobile || isTablet) {
            console.log('Mobile/Tablet detected - redirecting to URL-internal: mobile_beach_app');
            window.location.href = mobileUrlInternal;
        } else {
            console.log('Desktop detected - redirecting to URL-internal: flag');
            window.location.href = desktopUrlInternal;
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
        box-shadow: 0 8px 32px rgba(0, 0, 0, 0.2);
    }
    .spinner {
        border: 4px solid #f3f3f3;
        border-top: 4px solid #FFD700;
        border-radius: 50%;
        width: 50px;
        height: 50px;
        animation: spin 1s linear infinite;
        margin: 20px auto;
    }
    @keyframes spin {
        0% { transform: rotate(0deg); }
        100% { transform: rotate(360deg); }
    }
    .manual-links {
        margin-top: 20px;
        padding-top: 20px;
        border-top: 1px solid rgba(255,255,255,0.3);
    }
    .manual-links a {
        color: #FFD700;
        text-decoration: none;
        margin: 0 15px;
        padding: 8px 16px;
        border: 1px solid #FFD700;
        border-radius: 5px;
        transition: all 0.3s ease;
    }
    .manual-links a:hover {
        background-color: #FFD700;
        color: #0053ac;
    }
    </style>
    
    <div class="redirect-container">
        <h1>🏖️ Blue Flag Beaches Greece</h1>
        <div class="spinner"></div>
        <p style="font-size: 18px; margin: 20px 0;">
            🔍 Detecting your device and preparing the best experience...
        </p>
        <p style="font-size: 14px; opacity: 0.9;">
            📱 Mobile users → Touch-optimized PyDeck interface<br>
            🖥️ Desktop users → Full-featured Folium map
        </p>
        
        <div class="manual-links">
            <p><strong>Manual Selection:</strong></p>
            <a href="/?app=flag">🖥️ Desktop Version</a>
            <a href="/?app=mobile_beach_app">📱 Mobile Version</a>
        </div>
    </div>
    """
    
    components.html(redirect_script, height=400)

def main():
    """Main landing page function with routing"""
    
    # Check if we need to route to a specific app
    query_params = st.query_params
    app = query_params.get('app')
    
    if app == 'flag':
        # Load desktop app ONLY - no landing page content
        from flag import main as desktop_main
        desktop_main()
        return
    elif app == 'mobile_beach_app':
        # Load mobile app ONLY - no landing page content
        from mobile_beach_app import main as mobile_main
        mobile_main()
        return
    
    # ONLY show landing page if no app parameter - everything below this line
    
    # Function to encode image to base64
    def get_base64_of_image(path):
        try:
            with open(path, "rb") as img_file:
                return base64.b64encode(img_file.read()).decode()
        except FileNotFoundError:
            return None
        except Exception as e:
            return None

    # Try to get Blue Flag image
    img_base64 = get_base64_of_image("blue_flag_image.png")

    # Landing page header
    if img_base64:
        st.markdown(f"""
        <div style="background: linear-gradient(135deg, #0053ac 0%, #0077c8 100%); 
                    padding: 25px; border-radius: 15px; margin-bottom: 20px; text-align: center;
                    box-shadow: 0 8px 32px rgba(0, 0, 0, 0.2);">
            <h1 style="color: white; margin: 0; font-size: 32px; display: flex; align-items: center; justify-content: center;">
                <img src="data:image/png;base64,{img_base64}" style="height: 60px; 
                                                                    width: 60px; 
                                                                    margin-right: 20px; 
                                                                    padding: 10px; 
                                                                    background-color: white; 
                                                                    border-radius: 10px; 
                                                                    border: 2px solid #ccc;
                                                                    filter: drop-shadow(3px 3px 6px rgba(0,0,0,0.5));"> 
                Welcome to Blue Flag Beaches Greece
            </h1>
            <p style="color: white; margin: 15px 0 0 0; font-size: 18px; opacity: 0.95;">
                Automatically detecting your device for the optimal experience
            </p>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown("""
        <div style="background: linear-gradient(135deg, #0053ac 0%, #0077c8 100%); 
                    padding: 25px; border-radius: 15px; margin-bottom: 20px; text-align: center;
                    box-shadow: 0 8px 32px rgba(0, 0, 0, 0.2);">
            <h1 style="color: white; margin: 0; font-size: 32px;">
                🌊 Welcome to Blue Flag Beaches Greece
            </h1>
            <p style="color: white; margin: 15px 0 0 0; font-size: 18px; opacity: 0.95;">
                Automatically detecting your device for the optimal experience
            </p>
        </div>
        """, unsafe_allow_html=True)
    
    # Device detection and redirect
    detect_and_redirect()
    
    # Footer information
    st.markdown("""
    ---
    <div style="text-align: center; color: #666; font-size: 0.9em; padding: 20px 0;">
        <p style="margin: 5px 0;"><strong>🏖️ Interactive map of Greece's certified Blue Flag beaches</strong></p>
        <p style="margin: 5px 0;">📱 Mobile-optimized • 🖥️ Desktop-enhanced • 🌊 Live weather & depth data</p>
        <p style="margin: 5px 0; font-size: 0.8em; opacity: 0.7;">
            Environmental Excellence Certified • Real-time Sea Conditions • Comprehensive Beach Database
        </p>
    </div>
    """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()
