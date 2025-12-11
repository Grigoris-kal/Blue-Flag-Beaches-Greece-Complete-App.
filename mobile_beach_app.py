#!/usr/bin/env python3
"""
Mobile-Optimized Beach Map using PyDeck
Run this on a different port for mobile users
"""

import streamlit as st
import pandas as pd
import pydeck as pdk
import json
import math
import base64
import requests
import time
from io import StringIO

# ======================
# WEATHER MATCHING UTILITIES
# ======================

def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate distance between two points in kilometers."""
    R = 6371.0  # Earth radius in km
    
    lat1_rad = math.radians(lat1)
    lon1_rad = math.radians(lon1)
    lat2_rad = math.radians(lat2)
    lon2_rad = math.radians(lon2)
    
    dlat = lat2_rad - lat1_rad
    dlon = lon2_rad - lon1_rad
    
    a = math.sin(dlat / 2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    
    return R * c

def approximate_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Fast approximate distance for short distances (< 100km)."""
    lat_diff = abs(lat2 - lat1) * 111.0
    lon_diff = abs(lon2 - lon1) * 111.0 * abs(math.cos(math.radians((lat1 + lat2) / 2)))
    return math.sqrt(lat_diff**2 + lon_diff**2)

def find_best_weather_match(lat: float, lon: float, weather_cache: dict, max_distance_km: float = 2.0):
    """
    Flexible weather data matching using multiple strategies.
    
    Strategies tried in order:
    1. Exact coordinate match
    2. 7-decimal rounded match (common cache precision)
    3. Find closest station within max_distance_km
    4. Progressive rounding (6, 5, 4, 3 decimals)
    
    Returns: (weather_data, cache_key_used) or ({}, None)
    """
    # Strategy 1: Exact match
    exact_key = f"{lat}_{lon}"
    if exact_key in weather_cache:
        return weather_cache[exact_key], exact_key
    
    # Strategy 2: 7-decimal rounded match
    lat_7 = round(lat, 7)
    lon_7 = round(lon, 7)
    rounded_key_7 = f"{lat_7}_{lon_7}"
    if rounded_key_7 in weather_cache:
        return weather_cache[rounded_key_7], rounded_key_7
    
    # Strategy 3: Find closest station
    closest_match = None
    closest_distance = float('inf')
    closest_key = None
    
    for cache_key, weather_data in weather_cache.items():
        try:
            cache_lat, cache_lon = map(float, cache_key.split('_'))
            distance = approximate_distance(lat, lon, cache_lat, cache_lon)
            
            if distance < closest_distance and distance <= max_distance_km:
                closest_distance = distance
                closest_match = weather_data
                closest_key = cache_key
        except:
            continue
    
    if closest_match:
        return closest_match, closest_key
    
    # Strategy 4: Progressive rounding
    for decimals in (6, 5, 4, 3):
        lat_rounded = round(lat, decimals)
        lon_rounded = round(lon, decimals)
        rounded_key = f"{lat_rounded}_{lon_rounded}"
        
        # Also try formatted version
        formatted_key = f"{lat_rounded:.{decimals}f}_{lon_rounded:.{decimals}f}"
        
        if rounded_key in weather_cache:
            return weather_cache[rounded_key], rounded_key
        elif formatted_key in weather_cache:
            return weather_cache[formatted_key], formatted_key
    
    return {}, None

# ======================
# ORIGINAL APP FUNCTIONS
# ======================

# Tested and working URLs
RESOURCES = {
    "beach_data": "https://raw.githubusercontent.com/Grigoris-kal/Blue-Flag-Beaches-Greece-Complete-App./main/blueflag_greece_scraped.csv",
    "weather_cache": "https://raw.githubusercontent.com/Grigoris-kal/Blue-Flag-Beaches-Greece-Complete-App./main/weather_cache.json",
    "background_image": "https://raw.githubusercontent.com/Grigoris-kal/Blue-Flag-Beaches-Greece-Complete-App./main/voidokoilia_edited.jpg",
    "flag_image": "https://raw.githubusercontent.com/Grigoris-kal/Blue-Flag-Beaches-Greece-Complete-App./main/blue_flag_image.png",
    "depth_data": "https://raw.githubusercontent.com/Grigoris-kal/Blue-Flag-Beaches-Greece-Complete-App./main/beach_depth_database.json"
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

def find_depth_data(lat: float, lon: float, depth_data: dict):
    """Find depth data for given coordinates"""
    if 'beaches' not in depth_data:
        return None
    
    # Try exact match first
    exact_key = f"{lat}_{lon}"
    if exact_key in depth_data['beaches']:
        return depth_data['beaches'][exact_key].get('depth_info')
    
    # Try progressive rounding
    for decimals in (7, 6, 5, 4, 3):
        lat_rounded = round(lat, decimals)
        lon_rounded = round(lon, decimals)
        rounded_key = f"{lat_rounded}_{lon_rounded}"
        
        if rounded_key in depth_data['beaches']:
            return depth_data['beaches'][rounded_key].get('depth_info')
    
    return None



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

def get_wind_arrow(direction):
    """Convert wind direction to arrow emoji and direction name"""
    if direction == 'N/A' or direction is None:
        return 'N/A'
    try:
        dir_val = float(direction)
        
        # Define direction names and arrows
        directions = [
            (0, 'North', '↓'),      # Wind FROM North (arrow points down)
            (45, 'Northeast', '↙'),
            (90, 'East', '←'),
            (135, 'Southeast', '↖'),
            (180, 'South', '↑'),
            (225, 'Southwest', '↗'),
            (270, 'West', '→'),
            (315, 'Northwest', '↘')
        ]
        
        # Find closest direction
        index = int((dir_val + 22.5) / 45) % 8
        _, name, arrow = directions[index]
        
        return f"{name} {arrow}"
    except:
        return 'N/A'

def get_sea_conditions(wave_height):
    """Convert wave height to sea conditions"""
    if wave_height == 'N/A' or wave_height is None:
        return 'N/A'
    try:
        height = float(wave_height)
        if height < 0.5:
            return "Calm"
        elif height < 1.0:
            return "Moderate"
        elif height < 1.5:
            return "Choppy"
        else:
            return "Rough"
    except:
        return 'N/A'

@st.cache_data(persist="disk")
def load_resource(resource_name):
    """Universal loader for all resources"""
    url = RESOURCES.get(resource_name)
    if not url:
        st.error(f"Unknown resource: {resource_name}")
        return None

    for attempt in range(3):  # 3 retries
        try:
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            
            if resource_name == 'beach_data':
                try:
                    return pd.read_csv(StringIO(response.text), engine='python')
                except pd.errors.ParserError:
                    # Fallback if there are still parsing issues
                    return pd.read_csv(StringIO(response.text), engine='python', error_bad_lines=False, warn_bad_lines=False)
            elif resource_name in ['weather_cache', 'depth_data']:
                return response.json()
            else:  # Images
                return base64.b64encode(response.content).decode('utf-8')
                
        except Exception as e:
            if attempt == 2:  # Final attempt
                st.error(f"Failed to load {resource_name}\nURL: {url}\nError: {str(e)}")
                return None
            time.sleep(3)
    return None

# ======================
# UPDATED MAP CREATION
# ======================
def create_mobile_map(df, weather_cache, depth_data):
    """Create mobile-optimized PyDeck map with flexible weather matching"""
    
    map_data = []
    matched_count = 0
    total_count = len(df)
    depth_matched_count = 0  # Track depth matches
    
    for _, row in df.iterrows():
        lat = row['Latitude']
        lon = row['Longitude']
        
        # Use flexible matching for weather
        weather, matched_key = find_best_weather_match(lat, lon, weather_cache, max_distance_km=1.0)
        
        if weather:
            matched_count += 1
        
        # Build tooltip
        tooltip_text = f"📌 GPS: {lat:.4f}, {lon:.4f}"
        
        # Depth data - use separate matching function
        depth_info = find_depth_data(lat, lon, depth_data)
        
        if depth_info and depth_info.get("depth_5m") not in ["Unknown", "Error", None]:
            tooltip_text += f"\n🏊 Depth (5m from shore): {depth_info['depth_5m']}m"
            depth_matched_count += 1
        
        # Add weather data if available
        if weather:
            tooltip_text += f"\n🌡️ Air: {weather.get('air_temp', 'N/A')}°C"
            tooltip_text += f"\n🌊 Sea: {weather.get('sea_temp', 'N/A')}°C"
            tooltip_text += f"\n🌊 Waves: {weather.get('wave_height', 'N/A')}m"
            tooltip_text += f"\n💨 Wind: {weather.get('wind_speed', 'N/A')} km/h"
            tooltip_text += f"\n🧭 Wind Direction: {get_wind_arrow(weather.get('wind_direction', 'N/A'))}"
            tooltip_text += f"\n🌊 Sea Conditions: {get_sea_conditions(weather.get('wave_height', 'N/A'))}"
            
            # Indicate if it's an approximate match
            exact_key = f"{lat}_{lon}"
            if matched_key != exact_key:
                tooltip_text += f"\nℹ️ Approximate weather data"
        
        map_data.append({
            'lat': lat,
            'lon': lon,
            'name': transliterate_greek_to_latin(row['Name']),
            'municipality': transliterate_greek_to_latin(row.get('Municipality', '')),
            'tooltip': tooltip_text,
            'color': [0, 100, 200, 200],
            'icon': {
                'url': 'https://img.icons8.com/color/48/beach-ball.png',
                'width': 150,
                'height': 150,
                'anchorY': 150,
            }
        })
    
    # Show matching statistics
    match_rate = (matched_count / total_count * 100) if total_count > 0 else 0
    depth_rate = (depth_matched_count / total_count * 100) if total_count > 0 else 0
    
    st.sidebar.metric("Beaches with weather", f"{matched_count}/{total_count}", f"{match_rate:.1f}%")
    st.sidebar.metric("Beaches with depth data", f"{depth_matched_count}/{total_count}", f"{depth_rate:.1f}%")
    
    if matched_count < total_count:
        st.sidebar.warning(f"{total_count - matched_count} beaches without weather data")
    
    if depth_matched_count < total_count:
        st.sidebar.info(f"{total_count - depth_matched_count} beaches without depth data")
    
    # Create the map
    layer = pdk.Layer(
        'IconLayer',
        data=map_data,
        get_position=['lon', 'lat'],
        get_icon='icon',
        get_size=25,
        pickable=True
    )
    
    return pdk.Deck(
        map_style='https://basemaps.cartocdn.com/gl/voyager-gl-style/style.json',
        initial_view_state=pdk.ViewState(
            latitude=39.0742,
            longitude=21.8243,
            zoom=5.2,
            pitch=0
        ),
        layers=[layer],
        tooltip={
            "html": "<b>{name}</b><br/><i>{municipality}</i><br/><div style='white-space: pre-line;'>{tooltip}</div>",
            "style": {
                "backgroundColor": "rgba(0, 83, 156, 0.95)",
                "color": "white",
                "fontSize": "20px",
                "padding": "14px",
                "borderRadius": "7px",
                "maxWidth": "425px",
                "lineHeight": "1.4"
            }
        }
    )
# ======================
# MAIN APP
# ======================
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
    
    # Background from GitHub
    if bg_img:
        st.markdown(f"""
        <style>
        .stApp {{
            background-image: url('data:image/jpeg;base64,{bg_img}');
            background-size: cover;
            background-position: center;
            background-attachment: fixed;
        }}
        .stApp > .main {{
            background: rgba(255,255,255,0.1);
        }}
        </style>
        """, unsafe_allow_html=True)
    
    # Load data from GitHub
    with st.spinner("Loading beach data..."):
        df = load_resource("beach_data")
        weather_cache = load_resource("weather_cache")
        depth_data = load_resource("depth_data")
        
        if df is None:
            df = pd.DataFrame()
        if weather_cache is None:
            weather_cache = {}
        if depth_data is None:
            depth_data = {}

    # Search functionality
    st.markdown('<div class="search-container">', unsafe_allow_html=True)
    col1, col2 = st.columns([8, 2])
    
    with col1:
        st.markdown("<div style='margin-top: 17px;'></div>", unsafe_allow_html=True)
        search = st.text_input("🔍 Search beaches", placeholder="Type beach name...", label_visibility="collapsed")
    
    with col2:
        st.markdown("<div style='margin-top: 17px;'></div>", unsafe_allow_html=True)
        search_button = st.button("🔍 Search", use_container_width=True)
    
    st.markdown('</div>', unsafe_allow_html=True)
    
    # Search styling
    st.markdown("""
    <style>
    .stTextInput > div > div > input {
        background-color: white !important;
        border: 2px solid #0053ac !important;
        border-radius: 8px !important;
        color: black !important;
        height: 55px !important;
        padding: 12px !important;
    }
    
    .stTextInput > div > div > input::placeholder {
        color: #555555 !important;
        opacity: 1 !important;
    }
    
    .stButton > button {
        background-color: #0053ac !important;
        color: white !important;
        border: none !important;
        border-radius: 8px !important;
        font-weight: bold !important;
        height: 55px !important;
    }
    
    .stButton > button:hover {
        background-color: #0077c8 !important;
    }
    
    /* Desktop styling for wider map */
    @media (min-width: 768px) {
        .main .block-container {
            max-width: none !important;
            padding-left: 1rem !important;
            padding-right: 1rem !important;
            padding-top: 1rem !important;
            padding-bottom: 4rem !important;
        }
        
        .stDeckGlJsonChart {
            width: 160% !important;
            margin-left: -30% !important;
            position: relative !important;
            margin-top: -2rem !important;
        }
        
        .stDeckGlJsonChart > div {
            height: 71.5vh !important;
            width: 100% !important;
            margin-bottom: 4rem !important;
        }
        
        .search-container {
            width: 160% !important;
            margin-left: -30% !important;
            margin-top: -50% !important;
            margin-bottom: 2rem !important;
            position: relative !important;
            z-index: 10 !important;
        }
    }
    </style>
    """, unsafe_allow_html=True)
    
    if search and not df.empty:
        mask = (df['Name'].str.contains(search, case=False, na=False))
        df = df[mask]

    # Display results
    if not df.empty:
        st.pydeck_chart(create_mobile_map(df, weather_cache, depth_data), use_container_width=True)
        
        
    else:
        st.markdown("""
        <div style="
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


