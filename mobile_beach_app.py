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

st.markdown("""
<style>
/* Mobile styles (default) */
.main-container { width: 100%; }
.map-container { height: 400px; }

/* Desktop styles */
@media (min-width: 768px) {
    .main-container { max-width: 1200px; margin: 0 auto; }
    .map-container { height: 600px; }
    .sidebar { display: block; }
}

/* Large desktop */
@media (min-width: 1200px) {
    .map-container { height: 800px; }
}
</style>
""", unsafe_allow_html=True)

if 'app' not in st.query_params:
    st.set_page_config(
        page_title="Blue Flag Beaches Greece - Mobile",
        page_icon="blue_flag_image.ico",
        layout="centered",  # Different from desktop
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

def load_beach_data():
    """Load beach data from the same source as main app"""
    save_dir = "."  # Current directory (same as Python files)
    csv_path = os.path.join(save_dir, "blueflag_greece_scraped.csv")
    
    if os.path.exists(csv_path):
        df = pd.read_csv(csv_path)
        # Clean coordinates
        df["Latitude"] = pd.to_numeric(df["Latitude"], errors="coerce")
        df["Longitude"] = pd.to_numeric(df["Longitude"], errors="coerce")
        df = df.dropna(subset=["Latitude", "Longitude"])
        
        # Add English translations
        df['Name_English'] = df['Name'].apply(transliterate_greek_to_latin)
        df['Municipality_English'] = df['Municipality'].str.replace('Δήμος ', '').apply(transliterate_greek_to_latin)
        
        return df
    else:
        st.error("Beach data not found!")
        return pd.DataFrame()

@st.cache_data
def load_weather_cache():
    """Load weather data from cache"""
    try:
        save_dir = os.path.dirname(os.path.abspath(__file__))
        cache_path = os.path.join(save_dir, "weather_cache.json")
        
        if os.path.exists(cache_path):
            with open(cache_path, 'r', encoding='utf-8') as f:
                return json.load(f)
    except:
        pass
    return {}

def get_weather_for_beach(lat, lon, weather_cache):
    """Get weather data for a beach"""
    # Try different coordinate formats
    keys_to_try = [
        f"{lat}_{lon}",
        f"{float(lat)}_{float(lon)}",
        f"{round(lat, 6)}_{round(lon, 6)}"
    ]
    
    for key in keys_to_try:
        if key in weather_cache:
            return weather_cache[key]
    
    # Try nearby coordinates
    for cache_key, weather_data in weather_cache.items():
        if '_' in cache_key:
            try:
                cache_lat, cache_lon = map(float, cache_key.split('_'))
                if abs(cache_lat - lat) < 0.001 and abs(cache_lon - lon) < 0.001:
                    return weather_data
            except:
                continue
    return None

def create_mobile_map(df, weather_cache):
    """Create mobile-optimized PyDeck map"""
    
    # Load depth database
    try:
        save_dir = os.path.dirname(os.path.abspath(__file__))
        depth_path = os.path.join(save_dir, "beach_depth_database.json")
        
        if os.path.exists(depth_path):
            with open(depth_path, 'r', encoding='utf-8') as f:
                depth_database = json.load(f)
        else:
            depth_database = {}
    except:
        depth_database = {}
    
    # Prepare data for PyDeck
    map_data = []
    for _, row in df.iterrows():
        # Get weather data
        weather = get_weather_for_beach(row['Latitude'], row['Longitude'], weather_cache)
        
        # Get depth data
        lat, lon = row['Latitude'], row['Longitude']
        beach_key = f"{lat}_{lon}"
        depth_info = None
        
        # Try to find depth data
        if 'beaches' in depth_database and beach_key in depth_database['beaches']:
            depth_info = depth_database['beaches'][beach_key]['depth_info']
        else:
            # Try to find nearby beach (within 0.001 degrees ~ 100m)
            for key, beach_data in depth_database.get('beaches', {}).items():
                beach_lat = beach_data['lat']
                beach_lon = beach_data['lon']
                if abs(beach_lat - lat) < 0.001 and abs(beach_lon - lon) < 0.001:
                    depth_info = beach_data['depth_info']
                    break
        
# Replace the tooltip creation section (around line 108-115) with this:

        # Create detailed tooltip text with more data
        tooltip_text = f"📌 GPS: {lat:.4f}, {lon:.4f}"
        
        # Add depth information
        if depth_info and depth_info.get("depth_5m") != "Unknown" and depth_info.get("depth_5m") != "Error":
            if isinstance(depth_info["depth_5m"], (int, float)):
                depth_text = f"{depth_info['depth_5m']}m"
            else:
                depth_text = str(depth_info["depth_5m"])
            tooltip_text += f"\n🏊 Depth (5m from shore): {depth_text}"
        
        if weather:
            tooltip_text += f"\n🌡️ Air: {weather.get('air_temp', 'N/A')}°C"
            tooltip_text += f"\n🌊 Waves: {weather.get('wave_height', 'N/A')}m"
            tooltip_text += f"\n💨 Wind: {weather.get('wind_speed', 'N/A')} km/h"
            
            # Add sea temperature if available
            sea_temp = weather.get('sea_temp', 'N/A')
            if sea_temp != 'N/A' and sea_temp is not None:
                tooltip_text += f"\n🌡️ Sea: {sea_temp}°C"
                
            # Add wave conditions
            wave_height = weather.get('wave_height', 0)
            if wave_height != 'N/A' and wave_height is not None:
                try:
                    height = float(wave_height)
                    if height < 0.5:
                        conditions = "Calm"
                    elif height < 1.0:
                        conditions = "Moderate"
                    elif height < 2.0:
                        conditions = "Choppy"
                    else:
                        conditions = "Rough"
                    tooltip_text += f"\n🏄 {conditions}"
                except:
                    pass        
        map_data.append({
            'lat': row['Latitude'],
            'lon': row['Longitude'],
            'name': row['Name_English'],  # Use English name
            'municipality': row.get('Municipality_English', ''),  # Use English municipality
            'tooltip': tooltip_text,
            'color': [0, 100, 200, 200],  # Blue color for markers
            'icon': {
                'url': 'https://img.icons8.com/color/48/beach-ball.png',
                'width': 150,
                'height': 150,
                'anchorY': 150,
                'fillColor': '#FF6B35',
                'strokeColor': '#FFB830',
                'strokeWeight': 2,
                'scale': 1
            }
        })
    # Create PyDeck layer
    layer = pdk.Layer(
        'IconLayer',
        data=map_data,
        get_position=['lon', 'lat'],
        get_icon='icon',
        get_size=25,
        size_scale=1,
        pickable=True
    )
    
    # Set the viewport location to center of Greece
    view_state = pdk.ViewState(
        latitude=39.0742,
        longitude=21.8243,
        zoom=6,
        bearing=0,
        pitch=0
    )
    
    # Create the deck with background
    deck = pdk.Deck(
        map_style='mapbox://styles/mapbox/outdoors-v11',
        initial_view_state=view_state,
        layers=[layer],
        tooltip={
            "html": """
            <div style="font-family: Arial;">
                <b style='font-size: 18px;'>{name}</b><br/>
                <small style='font-size: 14px;'>{municipality}</small><br/>
                <pre style='white-space: pre-wrap; font-family: Arial; font-size: 16px; line-height: 1.4;'>{tooltip}</pre>
                
            </div>
            """,
            "style": {
                "backgroundColor": "rgba(0, 83, 156, 0.95)",
                "color": "white",
                "fontSize": "16px",
                "padding": "15px",
                "borderRadius": "8px",
                "maxWidth": "350px",
                "border": "2px solid #FFD700"
            }
        },
        # ADD THESE PARAMETERS FOR BETTER FULLSCREEN CONTROL:
        parameters={
            'pickingRadius': 10,
            'useDevicePixels': True
        }
    )
    
    return deck
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

    # Mobile-optimized header with Blue Flag image
   # Mobile-optimized header with Blue Flag image
    if img_base64:
        st.markdown(f"""
        <div style="background: linear-gradient(135deg, #0053ac 0%, #0077c8 100%); 
                    padding: 15px; border-radius: 10px; margin-bottom: 15px; text-align: center;">
            <h1 style="color: white; margin: 0; font-size: 24px; display: flex; align-items: center; justify-content: center;">
                <img src="data:image/png;base64,{img_base64}" style="height: 60px; 
                                                                    width: 60px; 
                                                                    margin-right: 15px; 
                                                                    padding: 8px; 
                                                                    background-color: white; 
                                                                    border-radius: 8px; 
                                                                    border: 2px solid #ccc;
                                                                    filter: drop-shadow(2px 2px 4px rgba(0,0,0,0.5));"> 
                Blue Flag Beaches Greece
            </h1>
            <p style="color: white; margin: 5px 0 0 0; font-size: 14px;">
                📱 Mobile Optimized Version
            </p>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown("""
        <div style="background: linear-gradient(135deg, #0053ac 0%, #0077c8 100%); 
                    padding: 15px; border-radius: 10px; margin-bottom: 15px; text-align: center;">
            <h1 style="color: white; margin: 0; font-size: 24px;">
                Blue Flag Beaches Greece
            </h1>
            <p style="color: white; margin: 5px 0 0 0; font-size: 14px;">
                📱 Mobile Optimized Version
            </p>
        </div>
        """, unsafe_allow_html=True)

    # Add same background as main app
    try:
        save_dir = os.path.dirname(os.path.abspath(__file__))
        bg_path = os.path.join(save_dir, "voidokoilia_edited.jpg")
        
        if os.path.exists(bg_path):
            with open(bg_path, "rb") as f:
                bg_data = base64.b64encode(f.read()).decode()
            
            st.markdown(f"""
            <style>
            .stApp {{
                background-image: url('data:image/jpeg;base64,{bg_data}');
                background-size: cover;
                background-position: center;
                background-repeat: no-repeat;
                background-attachment: fixed;
            }}
            </style>
            """, unsafe_allow_html=True)
    except:
        pass

    # Load data
    with st.spinner("📱 Loading mobile-optimized beach map..."):
        df = load_beach_data()
        weather_cache = load_weather_cache()
    
    if len(df) == 0:
        st.error("No beach data available!")
        return
    
    # Style the search input to be more visible on mobile
    st.markdown("""
    <style>
    .stTextInput > div > div > input {
        background-color: white !important;
        border: 2px solid #0077c8;
        border-radius: 10px;
        color: #333;
        font-size: 16px;
        padding: 12px;
    }
    .stTextInput > div > div > input::placeholder {
        color: #666 !important;
        font-weight: bold;
        opacity: 1 !important;
    }
    .stButton > button {
        background-color: white;
        border: 2px solid #0077c8;
        border-radius: 10px;
        color: #0077c8;
        font-size: 18px;
        padding: 10px 20px;
        width: 50%;
        margin: 10px auto;
        display: block;
    }
    .stButton > button:hover {
        background-color: #f0f8ff;
        border-color: #0053ac;
        color: #0053ac;
    }
    </style>
    """, unsafe_allow_html=True)

    # Search input (full width)
    search = st.text_input("🔍 Search beaches", placeholder="Type beach name here...", label_visibility="collapsed")
    
    # Centered search button (50% width, below text input)
    st.button("🔍 Search")
        
    # Filter data
    if search:
        # Search in both Greek and English names
        mask = (df['Name'].str.contains(search, case=False, na=False) | 
                df['Name_English'].str.contains(search, case=False, na=False))
        display_df = df[mask]
        if len(display_df) == 0:
            st.markdown(f"""
            <div style="background-color: white; 
                        border: 2px solid #ffc107; 
                        border-radius: 10px; 
                        padding: 12px; 
                        color: #856404;
                        text-align: center;
                        font-size: 16px;
                        margin: 10px 0;">
            ⚠️ No beaches found matching '{search}'
            </div>
            """, unsafe_allow_html=True)
            display_df = df
    else:
        display_df = df

    # Create and display mobile map
    mobile_map = create_mobile_map(display_df, weather_cache)
    
    # Display map with full screen height
    st.pydeck_chart(
        mobile_map, 
        use_container_width=True,
        height=650
    )
    
    # Beach count with white background
    st.markdown(f"""
    <div style="background-color: white; 
                border: 1px solid #d4edda; 
                border-radius: 5px; 
                padding: 10px; 
                color: #155724;
                text-align: center;">
    🏖️ {len(display_df)} beaches loaded!
    </div>
    """, unsafe_allow_html=True)


if __name__ == "__main__":
    main()
