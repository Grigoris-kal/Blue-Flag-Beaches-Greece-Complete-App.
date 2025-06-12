#!/usr/bin/env python3
"""
Minimal Landing Page - Device Detection and Routing ONLY
"""

import streamlit as st

def main():
    # Check if we need to route to a specific app
    query_params = st.query_params
    app = query_params.get('app')
    
    if app == 'flag':
        # Import and run flag.py directly - let it handle everything
        from flag import main as desktop_main
        desktop_main()
        return
    elif app == 'mobile_beach_app':
        # Import and run mobile app directly - let it handle everything  
        from mobile_beach_app import main as mobile_main
        mobile_main()
        return
    
    # ONLY if no app specified - show device detection
    st.set_page_config(
        page_title="Device Detection",
        layout="centered"
    )
    
    # Pure JavaScript device detection and redirect
    st.components.v1.html("""
    <script>
    function detectAndRedirect() {
        const userAgent = navigator.userAgent.toLowerCase();
        const isMobile = /android|webos|iphone|ipad|ipod|blackberry|iemobile|opera mini|mobile/.test(userAgent);
        const isTablet = /ipad|android(?!.*mobile)|tablet/.test(userAgent);
        
        const currentUrl = window.location.origin;
        
        if (isMobile || isTablet) {
            window.location.href = currentUrl + '/?app=mobile_beach_app';
        } else {
            window.location.href = currentUrl + '/?app=flag';
        }
    }
    
    // Immediate redirect - no delay
    detectAndRedirect();
    </script>
    
    <div style="text-align: center; padding: 2rem;">
        <h2>🔍 Detecting device...</h2>
        <p>Redirecting to optimal experience...</p>
    </div>
    """, height=200)

if __name__ == "__main__":
    main()
