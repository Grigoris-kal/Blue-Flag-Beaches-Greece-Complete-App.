#!/usr/bin/env python3
"""
Mobile-Optimized Beach Map using PyDeck
Run this on a different port for mobile users
"""

import streamlit as st
import pandas as pd
import pydeck as pdk  # Fixed typo (was 'pak')
import json
import os
import base64
import requests
import time

# GitHub file paths (EXACTLY as in your repo)
BEACH_DATA_URL = "https://raw.githubusercontent.com/Grigoris-kal/Blue-Flag-Beaches-Greece-Complete-App/main/blueflag_greece_scraped.csv"
WEATHER_CACHE_URL = "https://raw.githubusercontent.com/Grigoris-kal/Blue-Flag-Beaches-Greece-Complete-App/main/weather_cache.json"
DEPTH_DATA_URL = "https://raw.githubusercontent.com/Grigoris-kal/Blue-Flag-Beaches-Greece-Complete-App/main/beach_depth_database.json"
BLUE_FLAG_IMAGE_URL = "https://raw.githubusercontent.com/Grigoris-kal/Blue-Flag-Beaches-Greece-Complete-App/main/blue_flag_image.png"
BACKGROUND_IMAGE_URL = "https://raw.githubusercontent.com/Grigoris-kal/Blue-Flag-Beaches-Greece-Complete-App/main/voidokoilia_edited.jpg"

st.set_page_config(
    page_title="Blue Flag Beaches Greece - Mobile",
    page_icon="🌊",  # Fixed from '@'
    layout="centered",
    initial_sidebar_state="collapsed"
)

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

def get_base64_of_image_from_github(url):
    """Fetch image from GitHub and convert to base64"""
    try:
        response = requests.get(url)
        if response.status_code == 200:
            return base64.b64encode(response.content).decode()
        return ""
    except:
        return ""

@st.cache_data(ttl=3600)
def load_beach_data():
    """Load beach data from GitHub (original logic preserved)"""
    try:
        df = pd.read_csv(BEACH_DATA_URL)
        df["Latitude"] = pd.to_numeric(df["Latitude"], errors="coerce")
        df["Longitude"] = pd.to_numeric(df["Longitude"], errors="coerce")
        df = df.dropna(subset=["Latitude", "Longitude"])
        
        df['Name_English'] = df['Name'].apply(transliterate_greek_to_latin)
        df['Municipality_English'] = df['Municipality'].str.replace('Δήμος ', '').apply(transliterate_greek_to_latin)
        return df
    except Exception as e:
        st.error(f"Failed to load beach data: {str(e)}")
        return pd.DataFrame()

@st.cache_data(ttl=3600)
def load_weather_cache():
    """Load weather cache from GitHub (original logic preserved)"""
    try:
        response = requests.get(WEATHER_CACHE_URL)
        if response.status_code == 200:
            return response.json()
        return {}
    except Exception as e:
        st.error(f"Weather cache loading failed: {str(e)}")
        return {}

def create_mobile_map(df, weather_cache):
    """Create mobile-optimized PyDeck map (original logic preserved)"""
    try:
        response = requests.get(DEPTH_DATA_URL)
        depth_database = response.json() if response.status_code == 200 else {}
    except:
        depth_database = {}
    
    map_data = []
    for _, row in df.iterrows():
        weather = weather_cache.get(f"{row['Latitude']}_{row['Longitude']}", {})
        
        tooltip_text = f"📌 GPS: {row['Latitude']:.4f}, {row['Longitude']:.4f}"
        
        # Depth data logic (original)
        beach_key = f"{row['Latitude']}_{row['Longitude']}"
        depth_info = None
        if 'beaches' in depth_database and beach_key in depth_database['beaches']:
            depth_info = depth_database['beaches'][beach_key]['depth_info']
        
        if depth_info and depth_info.get("depth_5m") not in ["Unknown", "Error"]:
            tooltip_text += f"\n🏊 Depth (5m from shore): {depth_info['depth_5m']}m"
        
        if weather:
            tooltip_text += f"\n🌡️ Air: {weather.get('air_temp', 'N/A')}°C"
            tooltip_text += f"\n🌊 Waves: {weather.get('wave_height', 'N/A')}m"
            tooltip_text += f"\n💨 Wind: {weather.get('wind_speed', 'N/A')} km/h"
        
        map_data.append({
            'lat': row['Latitude'],
            'lon': row['Longitude'],
            'name': row['Name_English'],
            'municipality': row.get('Municipality_English', ''),
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
            "html": "<b>{name}</b><br/>{municipality}<br/>{tooltip}",
            "style": {
                "backgroundColor": "rgba(0, 83, 156, 0.95)",
                "color": "white"
            }
        }
    )

def main():
    # Load images from GitHub
    img_base64 = get_base64_of_image_from_github(BLUE_FLAG_IMAGE_URL)
    bg_data = get_base64_of_image_from_github(BACKGROUND_IMAGE_URL)
    
    # Header with GitHub-hosted image
    if img_base64:
        st.markdown(f"""
        <div style="background: linear-gradient(135deg, #0053ac 0%, #0077c8 100%); 
                    padding: 15px; border-radius: 10px; margin-bottom: 15px; text-align: center;">
            <h1 style="color: white; margin: 0; font-size: 24px; display: flex; align-items: center; justify-content: center;">
                <img src="data:image/png;base64,{img_base64}" style="height: 60px; margin-right: 15px;">
                Blue Flag Beaches Greece
            </h1>
            <p style="color: white; margin: 5px 0 0 0; font-size: 14px;">
                📱 Mobile Optimized Version
            </p>
        </div>
        """, unsafe_allow_html=True)
    
    # Background from GitHub
    if bg_data:
        st.markdown(f"""
        <style>
        .stApp {{
            background-image: url('data:image/jpeg;base64,{bg_data}');
            background-size: cover;
        }}
        </style>
        """, unsafe_allow_html=True)
    
    # Load data from GitHub
    with st.spinner("Loading data from GitHub..."):
        df = load_beach_data()
        weather_cache = load_weather_cache()
    
    # Rest of your original logic
    search = st.text_input("🔍 Search beaches", placeholder="Type beach name...")
    if search:
        mask = (df['Name'].str.contains(search, case=False) | 
               df['Name_English'].str.contains(search, case=False)
        df = df[mask]
    
    if not df.empty:
        st.pydeck_chart(create_mobile_map(df, weather_cache), use_container_width=True)
        st.success(f"Showing {len(df)} beaches from GitHub data")
    else:
        st.warning("No beach data found")

if __name__ == "__main__":
    main()
