#!/usr/bin/env python3
"""
Mobile-Optimized Beach Map using PyDeck
Run this on a different port for mobile users
"""

import streamlit as st
import pandas as pd
import pydeck as pdk
import json
import os
import base64
import requests
import time
from io import StringIO

# ======================
# CONFIGURATION (Updated URLs)
# ======================
# Tested and working URLs
RESOURCES = {
    "beach_data": "https://raw.githubusercontent.com/Grigoris-kal/Blue-Flag-Beaches-Greece-Complete-App./refs/heads/main/blueflag_greece_scraped.csv",  # ✓ Tested
    "weather_cache": "https://raw.githubusercontent.com/Grigoris-kal/Blue-Flag-Beaches-Greece-Complete-App./refs/heads/main/weather_cache.json",  # ✓ Tested
    "background_image": "https://raw.githubusercontent.com/Grigoris-kal/Blue-Flag-Beaches-Greece-Complete-App./refs/heads/main/voidokoilia_edited.jpg",  # ✓ Tested
    "flag_image": "https://raw.githubusercontent.com/Grigoris-kal/Blue-Flag-Beaches-Greece-Complete-App./refs/heads/main/blue_flag_image.png",  # ✓ Tested
    "depth_data": "https://raw.githubusercontent.com/Grigoris-kal/Blue-Flag-Beaches-Greece-Complete-App./refs/heads/main/beach_depth_database.json"  # Check if this exists
}

# ======================
# PAGE CONFIG
# ======================
st.set_page_config(
    page_title="Blue Flag Beaches Greece - Mobile",
    page_icon="🌊",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# ======================
# CORE FUNCTIONS
# ======================
@st.cache_data
def transliterate_greek_to_latin(text):
    """Convert Greek text to Latin characters"""
    if pd.isna(text):
        return ""
    
    greek_to_latin = {
        'Α': 'A', 'α': 'a', 'Ά': 'A', 'ά': 'a',
        'Β': 'V', 'β': 'v',
        'Γ': 'G', 'γ': 'g',
        'Δ': 'D', 'δ': 'd',
        'Ε': 'E', 'ε': 'e', 'Έ': 'E', 'έ': 'e',
        'Ζ': 'Z', 'ζ': 'z',
        'Η': 'I', 'η': 'i', 'Ή': 'I', 'ή': 'i',
        'Θ': 'Th', 'θ': 'th',
        'Ι': 'I', 'ι': 'i', 'Ί': 'I', 'ί': 'i',
        'Κ': 'K', 'κ': 'k',
        'Λ': 'L', 'λ': 'l',
        'Μ': 'M', 'μ': 'm',
        'Ν': 'N', 'ν': 'n',
        'Ξ': 'X', 'ξ': 'x',
        'Ο': 'O', 'ο': 'o', 'Ό': 'O', 'ό': 'o',
        'Π': 'P', 'π': 'p',
        'Ρ': 'R', 'ρ': 'r',
        'Σ': 'S', 'σ': 's', 'ς': 's',
        'Τ': 'T', 'τ': 't',
        'Υ': 'Y', 'υ': 'y', 'Ύ': 'Y', 'ύ': 'y',
        'Φ': 'F', 'φ': 'f',
        'Χ': 'Ch', 'χ': 'ch',
        'Ψ': 'Ps', 'ψ': 'ps',
        'Ω': 'O', 'ω': 'o', 'Ώ': 'O', 'ώ': 'o'
    }
    return ''.join([greek_to_latin.get(char, char) for char in str(text)])

@st.cache_data(ttl=3600)
def load_resource(resource_name):
    """Universal loader for all resources"""
    url = RESOURCES.get(resource_name)
    if not url:
        st.error(f"Unknown resource: {resource_name}")
        return None

    for attempt in range(3):  # 3 retries
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            
            if resource_name == 'beach_data':
                return pd.read_csv(StringIO(response.text))
            elif resource_name in ['weather_cache', 'depth_data']:
                return response.json()
            else:  # Images
                return base64.b64encode(response.content).decode('utf-8')
                
        except Exception as e:
            if attempt == 2:  # Final attempt
                st.error(f"Failed to load {resource_name}\nURL: {url}\nError: {str(e)}")
                return None
            time.sleep(1)
    return None

# ======================
# MAIN APP LOGIC
# ======================
def create_mobile_map(df, weather_cache):
    """Create mobile-optimized PyDeck map"""
    depth_data = load_resource("depth_data") or {}
    
    map_data = []
    for _, row in df.iterrows():
        # Round coordinates to match weather cache format (6 decimal places)
        lat_rounded = round(row['Latitude'], 6)
        lon_rounded = round(row['Longitude'], 6)
        weather_key = f"{lat_rounded}_{lon_rounded}"
        weather = weather_cache.get(weather_key, {})
        
        tooltip_text = f"📌 GPS: {row['Latitude']:.4f}, {row['Longitude']:.4f}"
        
        # Depth data logic
        beach_key = f"{lat_rounded}_{lon_rounded}"
        depth_info = None
        if 'beaches' in depth_data and beach_key in depth_data['beaches']:
            depth_info = depth_data['beaches'][beach_key]['depth_info']
        
        if depth_info and depth_info.get("depth_5m") not in ["Unknown", "Error"]:
            tooltip_text += f"\n🏊 Depth (5m from shore): {depth_info['depth_5m']}m"
        
        if weather:
            tooltip_text += f"\n🌡️ Air: {weather.get('air_temp', 'N/A')}°C"
            tooltip_text += f"\n🌊 Sea: {weather.get('sea_temp', 'N/A')}°C"
            tooltip_text += f"\n🌊 Waves: {weather.get('wave_height', 'N/A')}m"
            tooltip_text += f"\n💨 Wind: {weather.get('wind_speed', 'N/A')} km/h"
        
        map_data.append({
            'lat': row['Latitude'],
            'lon': row['Longitude'],
            'name': transliterate_greek_to_latin(row['Name']),  # Convert Greek to Latin
            'municipality': transliterate_greek_to_latin(row.get('Municipality', '')),  # Convert Greek to Latin
            'tooltip': tooltip_text,
            'color': [0, 100, 200, 200],
            'icon': {
                'url': 'https://img.icons8.com/color/48/beach-ball.png',
                'width': 150,
                'height': 150,
                'anchorY': 150,
            }
        })
    
    layer = pdk.Layer(
        'IconLayer',
        data=map_data,
        get_position=['lon', 'lat'],
        get_icon='icon',
        get_size=25,
        pickable=True
    )
    
    return pdk.Deck(
        map_style='mapbox://styles/mapbox/outdoors-v11',
        initial_view_state=pdk.ViewState(
            latitude=39.0742,
            longitude=21.8243,
            zoom=6,
            pitch=0
        ),
        layers=[layer],
        tooltip={
            "html": "<b>{name}</b><br/><i>{municipality}</i><br/><div style='white-space: pre-line;'>{tooltip}</div>",
            "style": {
                "backgroundColor": "rgba(0, 83, 156, 0.95)",
                "color": "white",
                "fontSize": "12px",
                "padding": "8px",
                "borderRadius": "4px",
                "maxWidth": "250px"
            }
        }
    )

def main():
    # Load all resources
    flag_img = load_resource("flag_image")
    bg_img = load_resource("background_image")
    
    # Header with GitHub-hosted image
    if flag_img:
        st.markdown(f"""
        <div style="background: linear-gradient(135deg, #0053ac 0%, #0077c8 100%); 
                    padding: 15px; border-radius: 10px; margin-bottom: 15px; text-align: center;">
            <h1 style="color: white; margin: 0; font-size: 24px; display: flex; align-items: center; justify-content: center;">
                <img src="data:image/png;base64,{flag_img}" style="height: 60px; margin-right: 15px;">
                Blue Flag Beaches Greece
            </h1>
            <p style="color: white; margin: 5px 0 0 0; font-size: 14px;">
                📱 Mobile Optimized Version
            </p>
        </div>
        """, unsafe_allow_html=True)
    
    # Background from GitHub
    if bg_img:
        st.markdown(f"""
        <style>
        .stApp {{
            background-image: url('data:image/jpeg;base64,{bg_img}');
            background-size: cover;
            background-position: center;
            background-attachment: fixed;
            background-color: rgba(255,255,255,0.8);
            background-blend-mode: overlay;
        }}
        </style>
        """, unsafe_allow_html=True)
    
    # Load data from GitHub
    with st.spinner("Loading beach data..."):
        df = load_resource("beach_data")
        weather_cache = load_resource("weather_cache")
        
        if df is None:
            df = pd.DataFrame()
        if weather_cache is None:
            weather_cache = {}

    # Search functionality
    search = st.text_input("🔍 Search beaches", placeholder="Type beach name...")
    if search and not df.empty:
        mask = (df['Name'].str.contains(search, case=False, na=False))
        df = df[mask]

    # Display results
    if not df.empty:
        st.pydeck_chart(create_mobile_map(df, weather_cache), use_container_width=True)
        st.success(f"Showing {len(df)} beaches from GitHub data")
    else:
        st.warning("No beach data found or failed to load data")

if __name__ == "__main__":
    main()
