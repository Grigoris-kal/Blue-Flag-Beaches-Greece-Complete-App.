#!/usr/bin/env python3
"""
Blue Flag Beaches Greece - Clean Landing Page with JavaScript Redirect
Detects device and redirects to independent Python apps - no contamination
"""

import streamlit as st
import streamlit.components.v1 as components
import base64

def main():
    """Clean landing page with JavaScript redirect and routing"""
    
    # Check if we need to route to a specific app
    query_params = st.query_params
    app = query_params.get('app')
    
    if app == 'flag':
        # Set wide layout for desktop and route
        st.set_page_config(
            page_title="Blue Flag Beaches of Greece",
            page_icon="🌊",
            layout="wide"
        )
        from flag import main as desktop_main
        desktop_main()
        return
    elif app == 'mobile_beach_app':
        # Set centered layout for mobile and route
        st.set_page_config(
            page_title="🏖️ Blue Flag Beaches Greece",
            page_icon="blue_flag_imagei.ico",
            layout="centered"
        )
        from mobile_beach_app import main as mobile_main
        mobile_main()
        return
    else:
        # Landing page display (when no app parameter)
        # Set centered layout for landing page
        st.set_page_config(
            page_title="🏖️ Blue Flag Beaches Greece",
            page_icon="blue_flag_imagei.ico",
            layout="centered"
        )
    
    
   
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
    
    # Pure JavaScript redirect - no Python imports
    redirect_script = """
    <script>
    function detectAndRedirect() {
        const userAgent = navigator.userAgent.toLowerCase();
        const isMobile = /android|webos|iphone|ipad|ipod|blackberry|iemobile|opera mini|mobile/.test(userAgent);
        const isTablet = /ipad|android(?!.*mobile)|tablet/.test(userAgent);
        
        const currentUrl = window.location.origin;
        
        if (isMobile || isTablet) {
            console.log('Mobile/Tablet detected - redirecting to mobile app');
            window.location.href = currentUrl + '/?app=mobile_beach_app';
        } else {
            console.log('Desktop detected - redirecting to desktop app');
            window.location.href = currentUrl + '/?app=flag';
        }
    }
    
    // Auto-redirect after 2 seconds
    setTimeout(detectAndRedirect, 2000);
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
    </div>
    """
    
    components.html(redirect_script, height=400)
    
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
