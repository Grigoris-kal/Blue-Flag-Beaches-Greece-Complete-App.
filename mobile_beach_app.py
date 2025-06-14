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
def find_closest_weather_match(lat, lon, weather_cache, tolerance=0.01):
    """Find the closest weather data match within tolerance"""
    if not weather_cache:
        return {}
    
    # First try exact match with different rounding levels
    for decimals in [6, 5, 4, 3]:
        lat_rounded = round(lat, decimals)
        lon_rounded = round(lon, decimals)
        weather_key = f"{lat_rounded}_{lon_rounded}"
        if weather_key in weather_cache:
            return weather_cache[weather_key]
    
    # If no exact match, find closest within tolerance
    closest_distance = float('inf')
    closest_weather = {}
    
    for weather_key, weather_data in weather_cache.items():
        try:
            cache_lat, cache_lon = map(float, weather_key.split('_'))
            distance = ((lat - cache_lat) ** 2 + (lon - cache_lon) ** 2) ** 0.5
            
            if distance < tolerance and distance < closest_distance:
                closest_distance = distance
                closest_weather = weather_data
        except:
            continue
    
    return closest_weather

def get_wind_arrow(direction):
    """Convert wind direction to arrow emoji"""
    if direction == 'N/A' or direction is None:
        return ''
    try:
        dir_val = float(direction)
        arrows = ['↓', '↙', '←', '↖', '↑', '↗', '→', '↘']
        index = int((dir_val + 22.5) / 45) % 8
        return arrows[index]
    except:
        return ''

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
        # Skip rows with missing coordinates
        if pd.isna(row['Latitude']) or pd.isna(row['Longitude']):
            continue
            
        lat = row['Latitude']
        lon = row['Longitude']
        
        # Use flexible weather matching
        weather = find_closest_weather_match(lat, lon, weather_cache)
        
        tooltip_text = f"📌 GPS: {row['Latitude']:.4f}, {row['Longitude']:.4f}"
        
        # Depth data logic - also use flexible matching
        depth_info = None
        if depth_data and 'beaches' in depth_data:
            # Try different rounding levels for depth data too
            for decimals in [6, 5, 4, 3]:
                lat_rounded = round(lat, decimals)
                lon_rounded = round(lon, decimals)
                beach_key = f"{lat_rounded}_{lon_rounded}"
                if beach_key in depth_data['beaches']:
                    depth_info = depth_data['beaches'][beach_key]['depth_info']
                    break
        
        if depth_info and depth_info.get("depth_5m") not in ["Unknown", "Error"]:
            tooltip_text += f"\n🏊 Depth (5m from shore): {depth_info['depth_5m']}m"
        
        if weather:
            tooltip_text += f"\n🌡️ Air: {weather.get('air_temp', 'N/A')}°C"
            tooltip_text += f"\n🌊 Sea: {weather.get('sea_temp', 'N/A')}°C"
            tooltip_text += f"\n🌊 Waves: {weather.get('wave_height', 'N/A')}m"
            tooltip_text += f"\n💨 Wind: {weather.get('wind_speed', 'N/A')} km/h"
            tooltip_text += f"\n🧭 Wind Direction: {get_wind_arrow(weather.get('wind_direction', 'N/A'))}"
        
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
            latitude=39.0742,   # Center of Greece
            longitude=21.8243,  # Center of Greece  
            zoom=5.2,           # Perfect zoom to see all Greece + islands on mobile too
            pitch=0
        ),
        layers=[layer],
        tooltip={
            "html": "<b>{name}</b><br/><i>{municipality}</i><br/><div style='white-space: pre-line;'>{tooltip}</div>",
            "style": {
                "backgroundColor": "rgba(0, 83, 156, 0.95)",
                "color": "white",
                "fontSize": "20px",  # 70% bigger than 12px for mobile
                "padding": "14px",   # 70% bigger padding
                "borderRadius": "7px",
                "maxWidth": "425px", # 70% bigger than 250px
                "lineHeight": "1.4"
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
        <style>
        /* Mobile styles (default) */
        .beach-header {{
            background: linear-gradient(135deg, #0053ac 0%, #0077c8 100%); 
            padding: 15px; 
            border-radius: 10px; 
            margin-bottom: 15px; 
            text-align: center;
        }}
        .beach-header h1 {{
            color: white; 
            margin: 0; 
            font-size: 24px; 
            display: flex; 
            align-items: center; 
            justify-content: center;
        }}
        .beach-header img {{
            height: 60px; 
            margin-right: 15px;
            background: white;
            padding: 8px;
            border-radius: 10px;
        }}
        
        /* Desktop/Laptop styles */
        @media (min-width: 768px) {{
            .beach-header {{
                padding: 25px;
                width: 160% !important;  /* 60% wider (40% more than current 140%) */
                margin-left: -30% !important;  /* Center the wider header */
                transform: none !important;
            }}
            .beach-header h1 {{
                font-size: 43px;  /* 20% larger than 36px */
            }}
            .beach-header img {{
                height: 96px;   /* 20% larger than 80px */
                margin-right: 20px;
                background: white;
                padding: 10px;
                border-radius: 12px;
            }}
        }}
        }}
        </style>
        <div class="beach-header">
            <h1>
                <img src="data:image/png;base64,{flag_img}">
                Blue Flag Beaches Greece
            </h1>
        </div>
        """, unsafe_allow_html=True)
    
    # Background from GitHub - clearer image
    if bg_img:
        st.markdown(f"""
        <style>
        .stApp {{
            background-image: url('data:image/jpeg;base64,{bg_img}');
            background-size: cover;
            background-position: center;
            background-attachment: fixed;
        }}
        /* Remove hazy overlay and make background clearer */
        .stApp > .main {{
            background: rgba(255,255,255,0.1);
        }}
        </style>
        """, unsafe_allow_html=True)
    
    # Load data from GitHub
    with st.spinner("Loading beach data..."):
        df = load_resource("beach_data")
        weather_cache = load_resource("weather_cache")
        
        # Debug information
        if df is None:
            st.error("❌ Failed to load beach data!")
            df = pd.DataFrame()
        else:
            st.success(f"✅ Loaded {len(df)} beaches successfully!")
            
        if weather_cache is None:
            st.warning("⚠️ Weather data not available")
            weather_cache = {}
        else:
            st.success(f"✅ Weather cache loaded with {len(weather_cache)} entries")

    # Search functionality with button layout - make wider to match map
    st.markdown('<div class="search-container">', unsafe_allow_html=True)
    col1, col2 = st.columns([10, 2])  # Much wider ratio - 83% text, 17% button
    
    with col1:
        search = st.text_input("🔍 Search beaches", placeholder="Type beach name...", label_visibility="collapsed")
    
    with col2:
        # Move button DOWN to align with text input (negative margin moves UP, positive moves DOWN)
        st.markdown("<div style='margin-top: -25px;'></div>", unsafe_allow_html=True)
        search_button = st.button("🔍 Search", use_container_width=True)
    
    st.markdown('</div>', unsafe_allow_html=True)  # Close search-container
    
    # Add custom CSS for white background on search input and other styling
    st.markdown("""
    <style>
    /* White background for search input */
    .stTextInput > div > div > input {
        background-color: white !important;
        border: 2px solid #0053ac !important;
        border-radius: 8px !important;
        color: black !important;
        height: 50px !important;  /* Fixed height for both mobile and desktop */
        box-sizing: border-box !important;
        padding: 12px !important;
    }
    
    /* Darker placeholder text */
    .stTextInput > div > div > input::placeholder {
        color: #555555 !important;
        opacity: 1 !important;
    }
    
    /* Style the search button - simple dark blue box */
    .stButton > button {
        background-color: #0053ac !important;
        color: white !important;
        border: none !important;
        border-radius: 8px !important;
        font-weight: bold !important;
        height: 50px !important;  /* Exact same height as input */
        box-sizing: border-box !important;
        padding: 12px 20px !important;
    }
    
    .stButton > button:hover {
        background-color: #0077c8 !important;
    }
    
    /* Custom warning message styling - make completely transparent */
    .custom-warning {
        background-color: rgba(255, 255, 255, 0) !important;  /* Completely transparent */
        color: rgba(0, 0, 0, 0) !important;  /* Invisible text */
        padding: 0px !important;
        border: none !important;
        margin: 0px !important;
        height: 0px !important;
        overflow: hidden !important;
    }
    
    /* Hide regular success/info messages but allow custom ones */
    .stAlert:not(.custom-message) {
        background-color: rgba(0, 0, 0, 0) !important;
        color: rgba(0, 0, 0, 0) !important;
        border: none !important;
        padding: 0px !important;
        margin: 0px !important;
        height: 0px !important;
        overflow: hidden !important;
    }
    
    /* Desktop styling */
    @media (min-width: 768px) {
        .custom-warning {
            font-size: 72px;  /* 400% larger */
            padding: 30px;
        }
        
        /* Make search columns closer */
        .stTextInput {
            margin-bottom: -10px;
        }
    }
    
    /* Mobile styling */
    @media (max-width: 767px) {
        .custom-warning {
            font-size: 27px;  /* 50% larger */
            padding: 20px;
        }
    }
    </style>
    """, unsafe_allow_html=True)
    
    if search and not df.empty:
        mask = (df['Name'].str.contains(search, case=False, na=False))
        df = df[mask]
        st.info(f"🔍 Found {len(df)} beaches matching '{search}'")

    # Display results
    if not df.empty:
        # Add responsive styling for the map and layout
        st.markdown("""
        <style>
        /* Make map larger on desktop/laptop */
        @media (min-width: 768px) {
            /* Override Streamlit's container width restrictions */
            .main .block-container {
                max-width: none !important;
                padding-left: 1rem !important;
                padding-right: 1rem !important;
                padding-top: 1rem !important;
                padding-bottom: 4rem !important;
            }
            
            /* Make map 60% wider and move up more */
            .stDeckGlJsonChart {
                width: 160% !important;  /* 60% wider (40% more than current) */
                margin-left: -30% !important;  /* Center the wider map */
                position: relative !important;
                margin-top: -2rem !important;  /* Move map up more */
            }
            
            .stDeckGlJsonChart > div {
                height: 55vh !important;  /* Even shorter for more space below */
                width: 100% !important;
                margin-bottom: 4rem !important; /* Even more space below map */
            }
            
            /* Make tooltips much larger on desktop/laptop */
            .deck-tooltip {
                font-size: 24px !important;
                padding: 16px !important;
                max-width: 500px !important;
                border-radius: 8px !important;
            }
            
            /* Make search container wider and move higher */
            .search-container {
                width: 160% !important;  /* Match new map width */
                margin-left: -30% !important;  /* Center with map */
                margin-top: -50% !important;  /* Move 50% higher (25% more) */
                margin-bottom: 2rem !important;
                position: relative !important;
                z-index: 10 !important;
            }
            
            /* Override desktop search styling to ensure same height */
            .stTextInput > div > div > input {
                font-size: 20px !important;
                height: 55px !important;     /* Consistent height */
                box-sizing: border-box !important;
                padding: 15px !important;
            }
            
            .stButton > button {
                font-size: 20px !important;
                height: 55px !important;     /* Exact same height as input */
                box-sizing: border-box !important;
                padding: 15px 25px !important;
                margin-top: 0px !important;
                width: 100% !important;
            }
            
            /* Remove problematic margin adjustments */
            .search-container .stButton {
                margin-top: 0px !important;
            }
            
            /* Ensure search container uses full available width to match map */
            .search-container {
                width: 160% !important;  /* Same as map width */
                margin-left: -30% !important;  /* Center with map */
                margin-top: -50% !important;  /* Move higher */
                margin-bottom: 2rem !important;
                position: relative !important;
                z-index: 10 !important;
            }
            
            .search-container > div {
                width: 100% !important;
            }
            
            /* Make funny message 100% larger on desktop */
            .beach-not-found-message {
                font-size: 36px !important;  /* 100% larger than 18px */
                padding: 40px !important;    /* Larger padding too */
            }
        }
        </style>
        """, unsafe_allow_html=True)
        
        st.pydeck_chart(create_mobile_map(df, weather_cache), use_container_width=True)
        
        # Add some space and then show the message at the bottom
        st.markdown("<br>", unsafe_allow_html=True)
        st.success(f"Showing {len(df)} beaches")
    else:
        # Show the funny message in a dark blue box for visibility
        st.markdown("""
        <div class="beach-not-found-message" style="
            background-color: #0053ac; 
            color: white; 
            padding: 20px; 
            border-radius: 10px; 
            text-align: center; 
            font-size: 18px; 
            margin: 20px 0;
            font-weight: bold;
        ">
            Oooops, we don't know that beach. At least you have a great view 😊
        </div>
        """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()
