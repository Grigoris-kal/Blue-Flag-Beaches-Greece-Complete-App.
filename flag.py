import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
import os
import numpy as np
from dotenv import load_dotenv
from geopy.geocoders import Nominatim
from geopy.extra.rate_limiter import RateLimiter
import requests
import base64
from folium.plugins import MarkerCluster, MiniMap, Fullscreen
import json
from datetime import datetime

# ─────────────────────────────────────────────────────────────────────────────
# 1) Load environment variables and page config
# ─────────────────────────────────────────────────────────────────────────────
load_dotenv()
JAWG_TOKEN = os.getenv('JAWG_TOKEN') or "f2wwvI5p3NCM9DJXW3xs7LZLcaY6AM9HKMYxlxdZWOQ9UeuFGirPhlHYpaOcLtLV"
COPERNICUS_USERNAME = os.getenv('COPERNICUS_USERNAME')
COPERNICUS_PASSWORD = os.getenv('COPERNICUS_PASSWORD')

st.set_page_config(
    page_title="Blue Flag Beaches of Greece",
    page_icon="🌊",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ─────────────────────────────────────────────────────────────────────────────
# 2) Load pre-generated depth database
# ─────────────────────────────────────────────────────────────────────────────

@st.cache_data(ttl=3600)
def load_depth_database():
    """Load pre-generated depth database from JSON file"""
    depth_files = [
        "beach_depth_database.json",
        "./beach_depth_database.json",
    ]    
    github_url = "https://raw.githubusercontent.com/Grigoris-kal/Blue-Flag-Beaches-Greece-Complete-App/main/beach_depth_database.json"
    
    
    for filepath in depth_files:
        if os.path.exists(filepath):
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    database = json.load(f)
                print(f"✅ Loaded depth database from: {filepath}")
                return database, True
            except Exception as e:
                print(f"❌ Error loading depth database from {filepath}: {e}")
                continue
    
    print("⚠️ No depth database found. Run depth_data_generator.py first!")
    return {}, False

# Load depth database at startup
DEPTH_DATABASE, DEPTH_AVAILABLE = load_depth_database()

def get_depth_html_for_beach(lat, lon):
    """Get pre-generated depth HTML for a beach location"""
    if not DEPTH_AVAILABLE:
        return """
        <div style="background:rgba(255,245,230,0.9);padding:6px;margin:5px 0;border-radius:4px;border-left:3px solid #ff9900;">
            <div style="font-size:11px;color:#cc6600;">
                🏊 Depth database not available - run depth_data_generator.py
            </div>
        </div>
        """
    
    # Create lookup key
    beach_key = f"{lat}_{lon}"
    
    # Try to find exact match first
    if beach_key in DEPTH_DATABASE.get('beaches', {}):
        depth_info = DEPTH_DATABASE['beaches'][beach_key]['depth_info']
    else:
        # Try to find nearby beach (within 0.001 degrees ~ 100m)
        found_beach = None
        for key, beach_data in DEPTH_DATABASE.get('beaches', {}).items():
            beach_lat = beach_data['lat']
            beach_lon = beach_data['lon']
            if abs(beach_lat - lat) < 0.001 and abs(beach_lon - lon) < 0.001:
                found_beach = beach_data
                break
        
        if found_beach:
            depth_info = found_beach['depth_info']
        else:
            return """
            <div style="background:rgba(255,245,230,0.9);padding:6px;margin:5px 0;border-radius:4px;border-left:3px solid #ff9900;">
                <div style="font-size:11px;color:#cc6600;">
                    🏊 Depth data not available for this beach
                </div>
            </div>
            """
    
    # Generate HTML based on depth info
    if depth_info.get("depth_5m") != "Unknown" and depth_info.get("depth_5m") != "Error":
        if isinstance(depth_info["depth_5m"], (int, float)):
            depth_text = f"{depth_info['depth_5m']}m"
        else:
            depth_text = str(depth_info["depth_5m"])
        
        # Determine confidence indicator
        confidence_icon = "🎯" if "Manual research" in depth_info.get('source', '') else "🔮"
        
        html = f"""
        <div style="background:rgba(230,250,255,0.9);padding:12px;margin:8px 0;border-radius:6px;border-left:4px solid #0066cc;">
            <div style="font-size:18px;font-weight:bold;color:#0066cc;margin-bottom:8px;">{confidence_icon} Water Depth Info</div>
            <div style="font-size:16px;color:#004080;line-height:1.5;">
                <strong>5m from shore:</strong> {depth_text}
            </div>
        </div>
        """
        return html
    else:
        return """
        <div style="background:rgba(255,245,230,0.9);padding:6px;margin:5px 0;border-radius:4px;border-left:3px solid #ff9900;">
            <div style="font-size:11px;color:#cc6600;">
                🏊 Depth data not available for this beach
            </div>
        </div>
        """

# ─────────────────────────────────────────────────────────────────────────────
# 3) Helper functions: image→base64, transliteration, region translation, data load, geocoding, weather
# ─────────────────────────────────────────────────────────────────────────────

def get_base64_image(image_path):
    """Convert an image file to a base64 string for embedding."""
    try:
        with open(image_path, "rb") as img_file:
            return base64.b64encode(img_file.read()).decode()
    except:
        return None

@st.cache_data
def load_beach_background():
    """Load and cache the beach background image from GitHub repository."""
    try:
        # Try edited version first
        github_url = "https://raw.githubusercontent.com/Grigoris-kal/Blue-Flag-Beaches-Greece-Complete-App/main/voidokoilia_edited.jpg"
        response = requests.get(github_url)
        if response.status_code == 200:
            import base64
            base64_img = base64.b64encode(response.content).decode()
            return f"data:image/jpeg;base64,{base64_img}"
        
        # Try original version
        github_url = "https://raw.githubusercontent.com/Grigoris-kal/Blue-Flag-Beaches-Greece-Complete-App/main/voidokoilia.jpg"
        response = requests.get(github_url)
        if response.status_code == 200:
            import base64
            base64_img = base64.b64encode(response.content).decode()
            return f"data:image/jpeg;base64,{base64_img}"
        
        # Fallback remote URL
        return "https://images.unsplash.com/photo-1559827260-dc66d52bef19?w=800&q=80"
    except Exception as e:
        print(f"Error loading background from GitHub: {e}")
        return "https://images.unsplash.com/photo-1559827260-dc66d52bef19?w=800&q=80"
    
    for path in possible_paths:
        if os.path.exists(path):
            base64_img = get_base64_image(path)
            if base64_img:
                return f"data:image/jpeg;base64,{base64_img}"
    # Fallback remote URL
    return "https://images.unsplash.com/photo-1559827260-dc66d52bef19?w=800&q=80"

def create_transliteration_mapping():
    greek_to_latin = {
        'Α': 'A', 'α': 'a', 'Ά': 'A', 'ά': 'a',
        'Β': 'V', 'β': 'v',
        'Γ': 'G', 'γ': 'g',
        'Δ': 'D', 'δ': 'd',
        'Ε': 'E', 'ε': 'e', 'Έ': 'E', 'έ': 'e',
        'Ζ': 'Z', 'ζ': 'z',
        'Η': 'I', 'η': 'i', 'Ή': 'I', 'ή': 'i',
        'Θ': 'Th', 'θ': 'th',
        'Ι': 'I', 'ι': 'i', 'Ί': 'I', 'ί': 'i', 'Ϊ': 'I', 'ϊ': 'i', 'ΐ': 'i',
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
        'Υ': 'Y', 'υ': 'y', 'Ύ': 'Y', 'ύ': 'y', 'Ϋ': 'Y', 'ϋ': 'y', 'ΰ': 'y',
        'Φ': 'F', 'φ': 'f',
        'Χ': 'Ch', 'χ': 'ch',
        'Ψ': 'Ps', 'ψ': 'ps',
        'Ω': 'O', 'ω': 'o', 'Ώ': 'O', 'ώ': 'o'
    }
    return greek_to_latin

def transliterate_greek_to_latin(text):
    if pd.isna(text):
        return ""
    mapping = create_transliteration_mapping()
    return ''.join([mapping.get(char, char) for char in str(text)])

def create_region_translation_mapping():
    return {
        'Π.Ε. ΕΒΡΟY': 'Evros',
        'Π.Ε. ΡΟΔΟΠΗΣ': 'Rhodope',
        'Π.Ε. ΞΑΝΘΗΣ': 'Xanthi',
        'Π.Ε. ΚΑΒΑΛΑΣ': 'Kavala',
        'Π.Ε. ΘΑΣΟΥ': 'Thasos',
        'Π.Ε. ΘΕΣΣΑΛΟΝΙΚΗΣ': 'Thessaloniki',
        'Π.Ε. ΧΑΛΚΙΔΙΚΗΣ': 'Halkidiki',
        'Π.Ε. ΠΙΕΡΙΑΣ': 'Pieria',
        'Π.Ε. ΛΑΡΙΣΑΣ': 'Larissa',
        'Π.Ε. ΜΑΓΝΗΣΙΑΣ': 'Magnesia',
        'Π.Ε. ΣΠΟΡΑΔΩΝ': 'Sporades',
        'Π.Ε. ΦΘΙΩΤΙΔΑΣ': 'Phthiotis',
        'Π.Ε. ΦΩΚΙΔΑΣ': 'Phocis',
        'Π.Ε. ΒΟΙΩΤΙΔΑΣ': 'Boeotia',
        'Π.Ε. ΕΥΒΟΙΑΣ': 'Evia',
        'Π.Ε. ΚΟΡΙΝΘΙΑΣ': 'Corinthia',
        'Π.Ε. ΑΡΓΟΛΙΔΑΣ': 'Argolis',
        'Π.Ε. ΑΡΚΑΔΙΑΣ': 'Arcadia',
        'Π.Ε. ΛΑΚΩΝΙΑΣ': 'Laconia',
        'Π.Ε. ΜΕΣΣΗΝΙΑΣ': 'Messinia',
        'Π.Ε. ΗΛΕΙΑΣ': 'Ilia',
        'Π.Ε. ΑΧΑΪΑΣ': 'Achaia',
        'Π.Ε. ΑΙΤΩΛΟΑΚΑΡΝΑΝΙΑΣ': 'Aetolia-Acarnania',
        'Π.Ε. ΠΡΕΒΕΖΑΣ': 'Preveza',
        'Π.Ε. ΚΕΡΚΥΡΑΣ': 'Corfu',
        'Π.Ε. ΛΕΥΚΑΔΑΣ': 'Lefkada',
        'Π.Ε. ΙΘΑΚΗΣ': 'Ithaca',
        'Π.Ε. ΚΕΦΑΛΟΝΙΑΣ': 'Kefalonia',
        'Π.Ε. ΖΑΚΥΝΘΟΥ': 'Zakynthos',
        'Π.Ε. ΧΑΝΙΩΝ': 'Chania',
        'Π.Ε. ΡΕΘΥΜΝΟΥ': 'Rethymno',
        'Π.Ε. ΗΡΑΚΛΕΙΟΥ': 'Heraklion',
        'Π.Ε. ΛΑΣΙΘΙΟΥ': 'Lasithi',
        'Π.Ε. ΡΟΔΟΥ': 'Rhodes',
        'Π.Ε. ΚΩ': 'Kos',
        'Π.Ε. ΑΝΔΡΟΥ': 'Andros',
        'Π.Ε. ΣΥΡΟΥ': 'Syros',
        'Π.Ε. ΚΕΑΣ-ΚΥΘΝΟΥ': 'Kea-Kythnos',
        'Π.Ε. ΠΑΡΟΥ': 'Paros',
        'Π.Ε. ΘΗΡΑΣ': 'Santorini',
        'Π.Ε. ΜΗΛΟΥ': 'Milos',
        'Π.Ε. ΣΑΜΟΥ': 'Samos',
        'Π.Ε. ΧΙΟΥ': 'Chios',
        'Π.Ε. ΛΕΣΒΟΥ': 'Lesvos',
        'Π.Ε. ΛΗΜΝΟΥ': 'Limnos',
        'Π.Ε. ΚΑΛΥΜΝΟΥ': 'Kalymnos',
        'Π.Ε. ΝΑΞΟΥ': 'Naxos',
        'Π.Ε. ΚΥΚΛΑΔΩΝ': 'Cyclades'
    }

def translate_region_to_english(greek_region):
    if pd.isna(greek_region):
        return "Unknown Region"
    translations = create_region_translation_mapping()
    return translations.get(str(greek_region), "Unknown Region")

def create_english_beach_names(df):
    df['Name_English'] = df['Name'].apply(transliterate_greek_to_latin)
    return df

def create_searchable_columns(df):
    df = df.copy()
    df = create_english_beach_names(df)
    df['Name_Latin'] = df['Name'].apply(transliterate_greek_to_latin)
    df['Region_Latin'] = df['Region'].apply(transliterate_greek_to_latin)
    df['Municipality_Latin'] = df['Municipality'].apply(transliterate_greek_to_latin)
    df['Region_English'] = df['Region'].apply(translate_region_to_english)
    df['Municipality_English'] = df['Municipality'].str.replace('Δήμος ', '').apply(transliterate_greek_to_latin)
    df['Search_Text'] = (
        df['Name'].fillna('') + ' ' +
        df['Name_English'].fillna('') + ' ' +
        df['Name_Latin'].fillna('') + ' ' +
        df['Region'].fillna('') + ' ' +
        df['Region_Latin'].fillna('') + ' ' +
        df['Region_English'].fillna('') + ' ' +
        df['Municipality'].fillna('') + ' ' +
        df['Municipality_Latin'].fillna('')
    ).str.lower()
    return df

@st.cache_data(ttl=3600)
def load_cached_data():
    """Load beach data from GitHub repository"""
    try:
        github_url = "https://raw.githubusercontent.com/Grigoris-kal/Blue-Flag-Beaches-Greece-Complete-App/main/blueflag_greece_scraped.csv"
        response = requests.get(github_url)
        if response.status_code == 200:
            from io import StringIO
            df = pd.read_csv(StringIO(response.text))
            return create_searchable_columns(df), "scraped"
        else:
            return create_searchable_columns(create_sample_data()), "created_sample"
    except Exception as e:
        print(f"Error loading CSV from GitHub: {e}")
        return create_searchable_columns(create_sample_data()), "created_sample",
    
    for filename, data_type in files_to_try:
        filepath = os.path.join(save_dir, filename)
        if os.path.exists(filepath):
            df = pd.read_csv(filepath)
            return create_searchable_columns(df), data_type
    return create_searchable_columns(create_sample_data()), "created_sample"

def create_sample_data():
    return pd.DataFrame([
        {"Name":"Αμμουδάρα","Region":"Π.Ε. ΗΡΑΚΛΕΙΟΥ","Municipality":"Δήμος Μαλεβιζίου","Latitude":35.3387,"Longitude":24.9727},
        {"Name":"Φαληράκι","Region":"Π.Ε. ΡΟΔΟΥ","Municipality":"Δήμος Ρόδου","Latitude":36.3403,"Longitude":28.2039},
        {"Name":"Κουκουναριές","Region":"Π.Ε. ΣΠΟΡΑΔΩΝ","Municipality":"Δήμος Σκιάθου","Latitude":39.1286,"Longitude":23.4192},
        {"Name":"Μύρτος","Region":"Π.Ε. ΚΕΦΑΛΟΝΙΑΣ","Municipality":"Δήμος Σάμης","Latitude":38.3434,"Longitude":20.5575},
        {"Name":"Ελούντα","Region":"Π.Ε. ΛΑΣΙΘΙΟΥ","Municipality":"Δήμος Αγίου Νικολάου","Latitude":35.2631,"Longitude":25.7253}
    ])

def geocode_with_nominatim(df):
    """Geocode beaches with missing coordinates using Nominatim."""
    geolocator = Nominatim(user_agent="blue-flag-beaches-greece", timeout=10)
    geocode = RateLimiter(geolocator.geocode, min_delay_seconds=1.5, return_value_on_exception=None)
    df_copy = df.copy()
    missing_coords = df_copy[df_copy['Latitude'].isna() | df_copy['Longitude'].isna()]
    if len(missing_coords) == 0:
        return df_copy, 0, []
    success_count = 0
    failed_beaches = []
    progress_bar = st.progress(0)
    status_text = st.empty()
    for i, (idx, row) in enumerate(missing_coords.iterrows()):
        try:
            progress = (i + 1) / len(missing_coords)
            progress_bar.progress(progress)
            status_text.text(f"Geocoding {i+1}/{len(missing_coords)} ({progress*100:.1f}%): {row['Name']}...")
            clean_name = row['Name'].split('/')[0].split('(')[0].strip()
            clean_region = row['Region'].split('[')[0].replace('Π.Ε.', '').strip()
            clean_municipality = row['Municipality'].replace('Δήμος', '').strip()
            queries = [
                f"{clean_name} beach, {clean_municipality}, {clean_region}, Greece",
                f"{clean_name}, {clean_municipality}, Greece",
                f"{clean_name} beach, {row['Region_English']}, Greece",
                f"{clean_name}, {row['Region_English']}, Greece",
                f"{clean_name} beach, Greece",
                f"{row['Name_English']} beach, {row['Region_English']}, Greece",
                f"{row['Name_English']}, Greece"
            ]
            if 'Χαλκιδική' in row['Region'] or 'ΧΑΛΚΙΔΙΚΗΣ' in row['Region']:
                queries.insert(0, f"{clean_name} beach, Halkidiki, Greece")
                queries.insert(1, f"{clean_name}, Chalkidiki, Greece")
            if 'Κρήτη' in row['Region'] or 'ΗΡΑΚΛΕΙΟΥ' in row['Region'] or 'ΧΑΝΙΩΝ' in row['Region'] or 'ΛΑΣΙΘΙΟΥ' in row['Region'] or 'ΡΕΘΥΜΝΟΥ' in row['Region']:
                queries.insert(0, f"{clean_name} beach, Crete, Greece")
                queries.insert(1, f"{clean_name}, Crete, Greece")
            if 'ΡΟΔΟΥ' in row['Region'] or 'ΡΟΔΟΥ' in row['Region']:
                queries.insert(0, f"{clean_name} beach, Rhodes, Greece")
                queries.insert(1, f"{clean_name}, Rhodes island, Greece")
            found = False
            for query in queries:
                try:
                    location = geocode(query)
                    if location:
                        if 34.5 <= location.latitude <= 42.0 and 19.0 <= location.longitude <= 29.0:
                            df_copy.at[idx, 'Latitude'] = location.latitude
                            df_copy.at[idx, 'Longitude'] = location.longitude
                            success_count += 1
                            found = True
                            break
                except Exception:
                    continue
            if not found:
                failed_beaches.append(f"{row['Name']} ({row['Region_English']})")
        except Exception as e:
            failed_beaches.append(f"{row['Name']} - Error: {str(e)}")
    progress_bar.empty()
    status_text.empty()
    return df_copy, success_count, failed_beaches

# Helper functions for weather display
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

def get_wave_conditions(wave_height, wave_period):
    """Convert wave height and period into user-friendly conditions description"""
    if wave_height == 'N/A' or wave_period == 'N/A':
        return 'N/A'
    try:
        height = float(wave_height)
        period = float(wave_period)
        if height < 0.5:
            if period < 6:
                return "Calm"
            else:
                return "Very Calm"
        elif height < 1.0:
            if period < 6:
                return "Choppy"
            elif period < 10:
                return "Moderate"
            else:
                return "Gentle Swells"
        elif height < 1.5:
            if period < 6:
                return "Rough & Choppy"
            elif period < 10:
                return "Moderate Waves"
            else:
                return "Rolling Swells"
        elif height < 2.5:
            if period < 8:
                return "Rough"
            else:
                return "Large Swells"
        else:
            return "Very Rough"
    except:
        return 'N/A'

@st.cache_data(ttl=300)  # Cache for 5 minutes
def load_weather_cache():
    """Load pre-fetched weather data from cache file"""
    try:
       github_url = "https://raw.githubusercontent.com/Grigoris-kal/Blue-Flag-Beaches-Greece-Complete-App/main/weather_cache.json"
       response = requests.get(github_url)
        
        if os.path.exists(cache_path):
            with open(cache_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        else:
            return {}
    except Exception as e:
        print(f"Error loading weather cache: {e}")
        return {}

def find_weather_for_beach(lat, lon, weather_cache):
    """Find weather data for a beach with flexible coordinate matching"""
    
    # Try exact match first (original method)
    exact_key = f"{lat}_{lon}"
    if exact_key in weather_cache:
        return weather_cache[exact_key]
    
    # Try with full precision (new beaches use this format)
    full_precision_key = f"{float(lat)}_{float(lon)}"
    if full_precision_key in weather_cache:
        return weather_cache[full_precision_key]
    
    # Try finding nearby coordinates (within 0.001 degrees ~ 100m)
    for cache_key, weather_data in weather_cache.items():
        if '_' not in cache_key:
            continue
            
        try:
            cache_lat_str, cache_lon_str = cache_key.split('_')
            cache_lat = float(cache_lat_str)
            cache_lon = float(cache_lon_str)
            
            # Check if coordinates are very close (within ~100 meters)
            if abs(cache_lat - lat) < 0.001 and abs(cache_lon - lon) < 0.001:
                return weather_data
                
        except (ValueError, IndexError):
            continue
    
    return None

def create_beach_map(df):
    """Create Folium map with Jawg Sunny style and pre-loaded weather + depth data."""
    GREECE_BOUNDS = [
        [30.5, 16.0],  # Much more permissive bounds to include all of Crete
        [45.0, 35.0]   # Northern Greece
    ]
        
    m = folium.Map(
        location=[39.0742, 21.8243],
        zoom_start=6.0,
        min_zoom=4,    # Allow even more zoom out
        max_zoom=15,   
        max_bounds=True,
        tiles=f"https://tile.jawg.io/jawg-sunny/{'{z}'}/{'{x}'}/{'{y}'}.png?access-token={JAWG_TOKEN}",
        attr='© Jawg Maps | © OpenStreetMap | Weather data © Open-Meteo.com | Depth data © GEBCO/EMODnet',
        control_scale=True
    )
    m.fit_bounds(GREECE_BOUNDS)
    m.options['maxBounds'] = GREECE_BOUNDS

    # Use MarkerCluster to group nearby beaches
    cluster = MarkerCluster()
    cluster.add_to(m)

    icon_url = "https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-2x-blue.png"
    
    # Load weather cache
    weather_cache = load_weather_cache()

    for idx, row in df.iterrows():
        lat, lon = row['Latitude'], row['Longitude']
        
        # NEW: Use the improved weather lookup function
        weather = find_weather_for_beach(lat, lon, weather_cache)
        
        if weather:
            wind_arrow = get_wind_arrow(weather.get('wind_direction'))
            wave_conditions = get_wave_conditions(weather.get('wave_height'), weather.get('wave_period'))
            
            weather_html = f"""
            <div style="background:rgba(240,248,255,0.9);padding:10px;margin:10px 0;border-radius:5px;backdrop-filter:blur(5px)">
                <h4 style="margin:0 0 5px 0;color:#0066cc">Current Sea Conditions</h4>
                <div style="display:grid;grid-template-columns:1fr 1fr;gap:5px;font-size:14px">
                    <div>🌡️ Air: {weather.get('air_temp', 'N/A')}°C</div>
                    <div>💨 Wind: {weather.get('wind_speed', 'N/A')} km/h {wind_arrow}</div>
                    <div>🌊 Wave Height: {weather.get('wave_height', 'N/A')}m</div>
                    <div>🏖️ Sea: {wave_conditions}</div>
                    <div>🌡️ Sea Temp: {weather.get('sea_temp', 'N/A') if weather.get('sea_temp') is not None and str(weather.get('sea_temp')).lower() != 'nan' else 'N/A'}°C</div>
                </div>
                
            </div>
            """
        else:
            weather_html = f"""
            <div style="background:rgba(255,200,200,0.9);padding:10px;margin:10px 0;border-radius:5px;text-align:center">
                <p style="color:#cc0000;margin:0;">Weather data not available for this beach.</p>
                <p style="font-size:12px;margin:5px 0 0 0;">Run weather_updater.py to fetch latest data.</p>
            </div>
            """
        
        # Get pre-generated depth information (fast lookup)
        depth_html = get_depth_html_for_beach(lat, lon)
        
        # Enhanced popup with depth information
        popup_content = f"""
        <div style="width:300px;font-family:Arial,sans-serif">
            <h3 style="color:#0066cc;margin-bottom:5px">{row['Name_English']}</h3>
            <p style="margin:3px 0;"><b>Municipality:</b> {row['Municipality_English']}</p>
            {depth_html}
            {weather_html}
            <p style="margin:5px 0;font-size:0.9em;color:#666;">
                📍 {lat:.4f}, {lon:.4f}
            </p>
        </div>
        """

        icon = folium.CustomIcon(
            icon_image=icon_url,
            icon_size=(25, 41),
            icon_anchor=(12, 41),
            popup_anchor=(1, -34)
        )
        
        # Add marker to cluster instead of directly to map
        folium.Marker(
            location=[lat, lon],
            popup=folium.Popup(popup_content, max_width=350),
            icon=icon,
            tooltip=f"{row['Name_English']} ()"
        ).add_to(cluster)
    
    return m

@st.cache_data(ttl=3600)
def build_map_html(df_json, jawg_token):
    """Build and cache the map HTML"""
    from io import StringIO
    df = pd.read_json(StringIO(df_json), convert_dates=False)
    
    # Create the map using your existing create_beach_map logic
    beach_map = create_beach_map(df)
    
    # Return the HTML representation
    return beach_map._repr_html_()


def main():
    # Function to encode image to base64
    def get_base64_of_image(path):
        with open(path, "rb") as img_file:
            return base64.b64encode(img_file.read()).decode()

# Get base64 string of your Blue Flag image from GitHub
try:
    github_url = "https://raw.githubusercontent.com/Grigoris-kal/Blue-Flag-Beaches-Greece-Complete-App/main/blue_flag_image.png"
    response = requests.get(github_url)
    if response.status_code == 200:
        img_base64 = base64.b64encode(response.content).decode()
    else:
        img_base64 = ""
except:
    img_base64 = ""
    
    # Load and set background image
    beach_bg = load_beach_background()
    st.markdown(f"""
    <style>
    /* Main app background remains unchanged */
    
    .stApp {{
        background-image: url('{beach_bg}');
        background-size: cover;
        background-position: center;
        background-repeat: no-repeat;
        background-attachment: fixed;
    }}

    /* ─────── Change all "golden" containers to semi-opaque white ─────── */
    .main .block-container {{
        background-color: rgba(255, 255, 255, 0.65);  /* white @65% */
        padding: 2rem;
        border-radius: 10px;
        backdrop-filter: blur(5px);
        max-width: 100%;
    }}

    /* Metrics container backgrounds → white @65% */
    [data-testid="metric-container"] {{
        background-color: rgba(255, 255, 255, 0.65) !important;
        border-radius: 10px;
        padding: 10px;
        backdrop-filter: blur(5px);
    }}
    [data-testid="metric-container"] [data-testid="metric-value"],
    [data-testid="metric-container"] [data-testid="metric-label"] {{
        color: #FFD700 !important;  /* dark yellow */
        -webkit-text-stroke: 1px black;  /* black outline around each letter */
    }}

    /* All headings/text outside of containers now have white color + black outline */
    h1, h2, h3, p, label {{
        color: white !important;
        -webkit-text-stroke: 1px black;
    }}

    /* ─────── Search-input label now white @75% with blue text ─────── */
    .stTextInput label {{
        background-color: rgba(255, 255, 255, 0.75) !important;  /* white @75% */
        padding: 6px 12px;
        border-radius: 5px;
        display: inline-block;
        color: #0066cc !important;  /* blue color to match */
        font-family: 'Arial', sans-serif !important;
        font-weight: bold !important;
        font-size: 22px !important;
        -webkit-text-stroke: 0 !important;
    }}

    /* Search box input itself stays light for readability */
    .stTextInput > div > div {{
        background-color: rgba(255, 255, 255, 0.9);
    }}

    /* ─────── Spinner container stays white @65%, spinner text dark yellow + outline ─────── */
    .stSpinner > div {{
        background-color: rgba(255, 255, 255, 0.65) !important;  /* white @65% */
        padding: 10px 15px;
        border-radius: 8px;
    }}
    .stSpinner > div > div {{
        color: #FFD700 !important;  /* dark yellow */
        -webkit-text-stroke: 1px black;
    }}

    /* Remove extra padding/margin */
    .main .block-container {{
        padding-bottom: 0;
        margin-bottom: 0;
    }}

    /* AGGRESSIVE WHITE BOX REMOVAL - Multiple approaches */
    
    /* Remove blank space below map */
    iframe {{
        margin-bottom: 0 !important;
        padding-bottom: 0 !important;
    }}
    
    /* Hide any div after iframe */
    iframe + div {{
        display: none !important;
    }}
    
    /* Remove white box under map - more aggressive approach */
    .element-container:has(iframe) + .element-container {{
        display: none !important;
    }}
    
    /* Hide any empty containers after the map */
    div[data-testid="stVerticalBlock"] > div:has(iframe) ~ div:empty {{
        display: none !important;
    }}
    
    /* Remove padding from map container */
    .element-container:has(iframe) {{
        margin-bottom: 0 !important;
        padding-bottom: 0 !important;
    }}
    
    /* Hide any stale element containers */
    .stale {{
        display: none !important;
    }}
    
    /* Target streamlit-folium specific containers */
    .streamlit-folium {{
        margin-bottom: 0 !important;
        padding-bottom: 0 !important;
    }}
    
    /* Hide any container that might appear after st_folium */
    div[data-testid="stVerticalBlock"] > div:last-child:empty {{
        display: none !important;
    }}
    
    /* Nuclear option for containers after folium */
    .element-container:has(.streamlit-folium) ~ .element-container {{
        display: none !important;
    }}
    
    /* Remove any spacer divs */
    .spacer {{
        display: none !important;
    }}
    
    /* Target the specific streamlit component iframe */
    iframe[title*="streamlit_folium"] {{
        margin-bottom: 0 !important;
    }}

     
    
    iframe[title*="streamlit_folium"] + * {{
        display: none !important;
    }}
  /* SPECIFIC FIX: Remove white space after folium map */
    .element-container:has(iframe[title*="streamlit_folium"]) {{
        margin-bottom: -1rem !important;
    }}
    
    /* Remove the next sibling container after map */
    .element-container:has(iframe[title*="streamlit_folium"]) + .element-container {{
        display: none !important;
        height: 0 !important;
        margin: 0 !important;
        padding: 0 !important;
        visibility: hidden !important;
    }}
    
    /* Force remove any spacing after map iframe */
    div.stIFrame + div {{
        display: none !important;
    }}
    
    /* Target Streamlit's spacer elements */
    .element-container > div[style*="height"] {{
        display: none !important;
    }}

    /* Very specific: target the exact iframe container and its siblings */
    iframe[src*="streamlit_folium"][height="650"] {{
        margin-bottom: -50px !important;
    }}
    
    /* Remove the streamlit container padding after map */
    .css-1kyxreq {{
        padding-bottom: 0 !important;
    }}
    
    /* Target the main container's last child if it's empty */
    section[data-testid="stMain"] > div:last-child:empty {{
        display: none !important;
    }}
    /* Fix footer spacing and hide branding */
    .reportview-container .main footer {{
        display: none;
        }}
    
    /* NEW BLUE TEXT STYLING */
    div[style*="background: rgba(255, 255, 255, 0.65)"] {{
        color: #0066cc !important;
        border: 1px solid rgba(0, 102, 204, 0.3) !important;
    }}
    div[style*="background: rgba(255, 255, 255, 0.65)"] * {{
        color: #0066cc !important;
        font-weight: bold !important;
        -webkit-text-stroke: 0.5px white !important;
        text-shadow: 1px 1px 1px rgba(255,255,255,0.5) !important;
    }}
    div[style*="background: rgba(255, 255, 255, 0.65)"] h3 {{
        color: #004080 !important;
        font-weight: bold !important;
    }}
    
    #MainMenu {{visibility: hidden;}}
    footer {{visibility: hidden;}}
    </style>
    """, unsafe_allow_html=True)

    if not JAWG_TOKEN:
        st.warning("⚠️ Jawg token not found – using OpenStreetMap as fallback")

    # ───────────────────────────── Enhanced Title & Subtitle with Blue Flag Icon ─────────────────────────────
    if img_base64:
        title_html = f"""
        <div style="background: linear-gradient(135deg, rgba(0, 83, 156, 0.65) 0%, rgba(0, 119, 200, 0.65) 100%); 
                    padding: 20px; 
                    border-radius: 15px; 
                    margin-bottom: 20px;
                    box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
                    backdrop-filter: blur(10px);
                    border: 1px solid rgba(255, 255, 255, 0.2);">
            <h1 style="color: #FFFFFF; 
                       text-shadow: 3px 3px 6px rgba(0, 0, 0, 0.9), 0 0 25px rgba(0, 0, 0, 0.5); 
                       margin: 0; 
                       display: flex; 
                       align-items: center;
                       font-family: 'Arial', sans-serif;
                       font-size: 36px;
                       font-weight: bold;">
                <img src="data:image/png;base64,{img_base64}" style="height: 50px; 
                                                            margin-right: 15px; 
                                                            padding: 8px; 
                                                            background-color: white; 
                                                            border-radius: 8px; 
                                                            border: 2px solid #ccc;
                                                            filter: drop-shadow(2px 2px 4px rgba(0,0,0,0.5));"> 
        Blue Flag Beaches Greece
            </h1>
        </div>
        """
    else:
        title_html = """
        <div style="background: linear-gradient(135deg, rgba(0, 83, 156, 0.65) 0%, rgba(0, 119, 200, 0.65) 100%); 
                    padding: 20px; 
                    border-radius: 15px; 
                    margin-bottom: 20px;
                    box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
                    backdrop-filter: blur(10px);
                    border: 1px solid rgba(255, 255, 255, 0.2);">
            <h1 style="color: #FFFFFF; 
                       text-shadow: 3px 3px 6px rgba(0, 0, 0, 0.9), 0 0 25px rgba(0, 0, 0, 0.5); 
                       margin: 0; 
                       font-family: 'Arial', sans-serif;
                       font-size: 36px;
                       font-weight: bold;">
                🌊 Blue Flag Beaches Greece
            </h1>
        </div>
        """
    
    st.markdown(title_html, unsafe_allow_html=True)
    
    st.markdown("""
    <div style="background: rgba(255, 255, 255, 0.85); padding:10px; border-radius:8px; margin-bottom:10px;">
        <span style="font-family: 'Arial', sans-serif; font-weight: bold; font-size: 22px; color: #0066cc; -webkit-text-stroke: 1px black;">Interactive map of Greece's certified Blue Flag beaches with live sea conditions, depth data and more </span>
    </div>
    """, unsafe_allow_html=True)

    # ─────────────────────────────── Load Data ─────────────────────────────────
    with st.spinner("📍 Loading beach data..."):
        df, data_source = load_cached_data()

    df["Latitude"] = pd.to_numeric(df["Latitude"], errors="coerce")
    df["Longitude"] = pd.to_numeric(df["Longitude"], errors="coerce")
    valid_coords_df = df.dropna(subset=["Latitude", "Longitude"]).copy()

   
    
    # ───────────────────────────── Search Input ─────────────────────────────────
    # ───────────────────────────── Search Input ─────────────────────────────────
    col1, col2 = st.columns([3, 1])
    with col1:
        search_query = st.text_input(
            "search",  # Hidden label
            placeholder="🔍 Search beaches: If map becomes transparent, beach info is not available 😊. At least you get a great view ! ",
            label_visibility="hidden"  # Completely hide label and its container
        )
    with col2:
        # Add spacing to align button with input field
        st.markdown("<div style='margin-top: 2.4rem;'></div>", unsafe_allow_html=True)
        search_button = st.button("🔍 Search", use_container_width=True)
   # ───────────────────────────── Filter Logic ─────────────────────────────────
    if search_query and (search_button or search_query):  # Trigger on button click or typing
        search_lower = search_query.lower()
        mask = df['Search_Text'].str.contains(search_lower, case=False, na=False)
        filtered_df = df[mask]
        display_df = filtered_df.dropna(subset=["Latitude", "Longitude"]).copy()

        if len(filtered_df) > 0:
            # Results found - just show on map, no message
            pass
        else:
            # Option 1: Completely transparent messages
            st.markdown("""
            <style>
            .stAlert {
                background-color: rgba(255, 255, 255, 0.0) !important;
                border: none !important;
                color: rgba(0, 0, 0, 0.0) !important;
            }
            .stAlert > div {
                background-color: rgba(255, 255, 255, 0.0) !important;
                border: none !important;
                color: rgba(0, 0, 0, 0.0) !important;
            }
            .stAlert * {
                color: rgba(0, 0, 0, 0.0) !important;
                opacity: 0 !important;
            }
            </style>
            """, unsafe_allow_html=True)
            
            st.warning(f"No beaches found matching '{search_query}'")
            st.info("💡 Try popular beaches: Ammoudara, Faliraki, Myrtos, Elounda, Posidi")
            display_df = valid_coords_df.head(0)
            
            # Option 2: Or simply comment out the messages entirely
            # display_df = valid_coords_df.head(0)
    else:
        display_df = valid_coords_df
        st.markdown(f"""
        <div style="background: rgba(255, 255, 255, 0.0); padding:10px; border-radius:8px; margin-bottom:10px;">
            <span style="font-family: 'Arial', sans-serif; font-weight: bold; font-size: 18px; color: rgba(0, 102, 204, 0.0);">📍 Showing all {len(display_df)} beaches with coordinates on the map</span>
        </div>
        """, unsafe_allow_html=True)

    # ─────────────────────────────── Map Section ─────────────────────────────────
    if len(display_df) > 0:
        # Display weather data info
        st.markdown("""
        <div style="background: rgba(255, 255, 255, 0.85); padding:10px; border-radius:8px; margin-bottom:10px;">
            <strong style="font-family: 'Arial', sans-serif; font-size: 18px; color: #0066cc;">🌊 Sea Data:</strong> 
            <span style="font-family: 'Arial', sans-serif; font-weight: bold; font-size: 18px; color: #0066cc;">
            Click on any marker to see current sea conditions including sea temperature, wave conditions, sea debth 5m from the shore, wind speed/direction and much more. Regular data updates.
            </span>
        </div>
        """, unsafe_allow_html=True)
      

        with st.spinner("🗺️ Loading beach map with pre-loaded depth data..."):
            # Convert DataFrame to JSON for caching
            df_json = display_df.to_json(date_format="iso")
            
            # Get cached HTML
            map_html = build_map_html(df_json, JAWG_TOKEN)
            
            # Display using components
            st.components.v1.html(
                map_html,
                height=650,
                scrolling=False
            )
            
        # Inject CSS to remove the white box after map renders
        st.markdown("""
<style>
    /* Target the white info box specifically */
    div[style*="background: rgba(255, 255, 255, 0.65); padding:10px; border-radius:8px; margin-bottom:10px;"] {
        color: #0066cc !important;
        font-family: 'Arial', sans-serif !important;
    }
    
    /* Make sure all text inside is blue */
    div[style*="background: rgba(255, 255, 255, 0.65);"] * {
        color: #0066cc !important;
        -webkit-text-stroke: 0 !important;
    }
    
    /* Keep the white background but make text blue */
    div[style*="background: rgba(255, 255, 255, 0.65);"] {
        background: rgba(255, 255, 255, 0.65) !important;
    }
</style>
""", unsafe_allow_html=True)
     
    else:
        st.warning("🔍 No beaches found matching your search or no coordinates available")

    # ───────────────────────────── Footer Bar ────────────────────────────────────
    st.markdown("---")
    
    # Enhanced footer with depth database info
    if DEPTH_AVAILABLE and DEPTH_DATABASE:
        metadata = DEPTH_DATABASE.get('metadata', {})
        depth_info = f"🏊 **Depth Data:** {metadata.get('total_beaches', 0)} beaches in database ({metadata.get('coverage_stats', {}).get('total_coverage_percent', 0)}% coverage)"
    else:
        depth_info = "🏊 **Depth Data:** Not available (run depth_data_generator.py)"
    
    st.markdown(f"""
    <div style="text-align:center;padding:15px;background:#f8f9fa;border-radius:10px">
        <div style="font-size:14px;color:#666;margin-bottom:10px">
            🌊 <strong>Data Source:</strong> {data_source} | 
            📍 <strong>Beaches Mapped:</strong> {len(valid_coords_df)} | 
            🌤️ <strong>Weather:</strong> Open-Meteo.com |
            {depth_info} |
            🔍 <strong>Search Languages:</strong> Greek & English
        </div>
        <div style="font-size:12px;color:#999">
            Blue Flag Beaches Greece • Environmental Excellence Certified • Live Weather Conditions • Pre-loaded Depth Database
        </div>
    </div>
    """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()
