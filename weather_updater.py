#!/usr/bin/env python3
"""
Simple Weather Updater - No directory complications
Updates ALL beaches, preserves existing cache data.
"""

import argparse
import os
import logging
import pandas as pd
import requests
import json
import time
from datetime import datetime
from typing import Dict, Any

# Setup logging in current directory
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('weather_updater.log'),
        logging.StreamHandler()
    ]
)

# Simple config
CACHE_FILE = "weather_cache.json"
CSV_FILE = "blueflag_greece_scraped.csv"

def load_existing_cache() -> Dict[str, Any]:
    """Load existing cache - NEVER deletes old data."""
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
            if isinstance(data, dict):
                logging.info(f"Loaded cache with {len(data)} entries")
                return data
            else:
                logging.warning("Cache file is not a JSON object")
                return {}
        except Exception as e:
            logging.warning(f"Failed to load cache: {e}")
            return {}
    logging.info("No existing cache found, starting fresh")
    return {}

def save_cache(data: Dict[str, Any]):
    """Save cache to file - preserves all existing data."""
    try:
        with open(CACHE_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logging.info(f"✅ Saved cache with {len(data)} entries")
    except Exception as e:
        logging.error(f"❌ Failed to save cache: {e}")
        raise

def update_all_beaches():
    """Update all beaches - adds new data, updates existing."""
    # Load beaches
    if not os.path.exists(CSV_FILE):
        raise FileNotFoundError(f"❌ CSV file not found: {CSV_FILE}")
    
    try:
        df = pd.read_csv(CSV_FILE)
    except Exception as e:
        logging.error(f"Failed to read CSV: {e}")
        return
    
    # Ensure required columns
    if 'Latitude' not in df.columns or 'Longitude' not in df.columns or 'Name' not in df.columns:
        logging.error("CSV missing required columns (Name, Latitude, Longitude)")
        return
    
    # Clean data
    df['Latitude'] = pd.to_numeric(df['Latitude'], errors='coerce')
    df['Longitude'] = pd.to_numeric(df['Longitude'], errors='coerce')
    df = df.dropna(subset=['Latitude', 'Longitude'])
    
    total_beaches = len(df)
    logging.info(f"📊 Processing {total_beaches} beaches")
    
    # -----------------------------------------------------------------
    # START OF AGREED-UPON CHANGES
    # -----------------------------------------------------------------
    # 1. GET UNIQUE COORDINATES
    # Create a DataFrame with just coordinates and drop duplicates
    unique_coords_df = df[['Latitude', 'Longitude']].drop_duplicates()
    unique_coords = list(unique_coords_df.itertuples(index=False, name=None)) # List of (lat, lon) tuples
    logging.info(f"📍 Found {len(unique_coords)} unique locations")
    
    # 2. FETCH BATCHED WEATHER DATA FOR ALL UNIQUE LOCATIONS AT ONCE
    weather_batch_url = "https://api.open-meteo.com/v1/forecast?current=temperature_2m,wind_speed_10m,wind_direction_10m&timezone=auto"
    for i, (lat, lon) in enumerate(unique_coords):
        separator = "&" if i == 0 else ","
        weather_batch_url += f"{separator}latitude={lat}&longitude={lon}"
    
    weather_data_map = {}  # To store results: key=(lat,lon), value=weather_data
    try:
        logging.info("🌤️  Fetching batched weather data...")
        response = requests.get(weather_batch_url, timeout=30)
        response.raise_for_status()
        weather_batch_data = response.json()
        # The API returns data matching the order of coordinates sent
        current_weather_list = weather_batch_data.get('current', [])
        # Map data back to each coordinate
        for idx, (lat, lon) in enumerate(unique_coords):
            if idx < len(current_weather_list):
                weather_data_map[(lat, lon)] = current_weather_list[idx]
            else:
                weather_data_map[(lat, lon)] = {}
    except Exception as e:
        logging.error(f"❌ Failed to fetch batched weather: {e}")
        # Fallback: create empty map to avoid crash, but entries will have N/A
        weather_data_map = {coord: {} for coord in unique_coords}
    
    # Small delay between the two batch API calls
    time.sleep(0.5)
    
    # 3. FETCH BATCHED MARINE DATA (Similar structure)
    marine_batch_url = "https://marine-api.open-meteo.com/v1/marine?current=wave_height,wave_direction,wave_period,sea_surface_temperature"
    for i, (lat, lon) in enumerate(unique_coords):
        separator = "&" if i == 0 else ","
        marine_batch_url += f"{separator}latitude={lat}&longitude={lon}"
    
    marine_data_map = {}  # To store results: key=(lat,lon), value=marine_data
    try:
        logging.info("🌊  Fetching batched marine data...")
        response = requests.get(marine_batch_url, timeout=30)
        response.raise_for_status()
        marine_batch_data = response.json()
        current_marine_list = marine_batch_data.get('current', [])
        # Map data back to each coordinate
        for idx, (lat, lon) in enumerate(unique_coords):
            if idx < len(current_marine_list):
                marine_data_map[(lat, lon)] = current_marine_list[idx]
            else:
                marine_data_map[(lat, lon)] = {}
    except Exception as e:
        logging.error(f"❌ Failed to fetch batched marine data: {e}")
        # Fallback: create empty map
        marine_data_map = {coord: {} for coord in unique_coords}
    # -----------------------------------------------------------------
    # END OF AGREED-UPON CHANGES
    # -----------------------------------------------------------------
    
    # Load existing cache
    cache = load_existing_cache()
    updates = 0
    new_beaches = 0
    errors = 0
    
    # THE ORIGINAL LOOP TO PROCESS EACH BEACH ROW REMAINS
    for idx, row in df.iterrows():
        beach_name = str(row['Name'])
        try:
            lat = float(row['Latitude'])
            lon = float(row['Longitude'])
        except:
            logging.warning(f"Skipping {beach_name} - invalid coordinates")
            errors += 1
            continue
        
        key = f"{lat:.6f}_{lon:.6f}"
        
        # Check if we need to update (always update for now)
        try:
            # -----------------------------------------------------------------
            # MODIFIED DATA FETCHING: USE BATCHED DATA MAPS
            # -----------------------------------------------------------------
            # Get weather and marine data from the pre-fetched batch maps
            current_weather = weather_data_map.get((lat, lon), {})
            current_marine = marine_data_map.get((lat, lon), {})
            # -----------------------------------------------------------------
            
            # Create or update entry
            entry = {
                'beach_name': beach_name,
                'latitude': lat,
                'longitude': lon,
                'air_temp': round(current_weather.get('temperature_2m', 'N/A'), 1) if current_weather.get('temperature_2m') is not None else 'N/A',
                'wind_speed': round(current_weather.get('wind_speed_10m', 'N/A'), 1) if current_weather.get('wind_speed_10m') is not None else 'N/A',
                'wind_direction': current_weather.get('wind_direction_10m', 'N/A'),
                'wave_height': round(current_marine.get('wave_height', 'N/A'), 1) if current_marine.get('wave_height') is not None else 'N/A',
                'wave_direction': current_marine.get('wave_direction', 'N/A'),
                'wave_period': round(current_marine.get('wave_period', 'N/A'), 1) if current_marine.get('wave_period') is not None else 'N/A',
                'sea_temp': round(current_marine.get('sea_surface_temperature', 'N/A'), 1) if current_marine.get('sea_surface_temperature') is not None else 'N/A',
                'last_updated': datetime.now().isoformat()
            }
            
            # Update cache
            if key not in cache:
                new_beaches += 1
            cache[key] = entry
            updates += 1
            
            if updates % 10 == 0:
                logging.info(f"Progress: {updates}/{total_beaches} beaches updated")
            
            # Rate limiting (now only between beach processing, not API calls)
            time.sleep(0.05)
            
        except Exception as e:
            logging.error(f"❌ Error processing {beach_name}: {e}")
            errors += 1
    
    # Save updated cache
    save_cache(cache)
    logging.info(f"🎉 COMPLETED: {updates} updates, {new_beaches} new beaches, {errors} errors")
    logging.info(f"📁 Cache now has {len(cache)} total entries")
def main():
    parser = argparse.ArgumentParser(description='Simple Weather Updater')
    parser.add_argument('--once', action='store_true', help='Run once and exit')
    parser.add_argument('--interval', type=int, default=480, help='Interval in minutes (for continuous mode)')
    args = parser.parse_args()
    
    logging.info("🚀 Starting Weather Updater")
    
    if args.once:
        update_all_beaches()
        logging.info("✅ Single update completed")
    else:
        # Continuous mode for local testing
        logging.info(f"🔄 Continuous mode: updating every {args.interval} minutes")
        while True:
            try:
                update_all_beaches()
                logging.info(f"💤 Sleeping for {args.interval} minutes...")
                time.sleep(args.interval * 60)
            except KeyboardInterrupt:
                logging.info("👋 Stopped by user")
                break
            except Exception as e:
                logging.error(f"🔥 Update cycle failed: {e}")
                time.sleep(300)  # Wait 5 minutes on error

if __name__ == "__main__":
    main()

