#!/usr/bin/env python3
"""
Simple Weather Updater - No directory complications
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
    """Load existing cache."""
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
            logging.info(f"Loaded cache with {len(data)} entries")
            return data
        except Exception as e:
            logging.warning(f"Failed to load cache: {e}")
    return {}

def save_cache(data: Dict[str, Any]):
    """Save cache to file."""
    try:
        with open(CACHE_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logging.info(f"Saved cache with {len(data)} entries")
    except Exception as e:
        logging.error(f"Failed to save cache: {e}")
        raise

def update_all_beaches():
    """Update all beaches."""
    # Load beaches
    if not os.path.exists(CSV_FILE):
        raise FileNotFoundError(f"CSV file not found: {CSV_FILE}")
    
    df = pd.read_csv(CSV_FILE)
    df = df.dropna(subset=['Latitude', 'Longitude'])
    
    logging.info(f"Updating {len(df)} beaches")
    
    # Load existing cache
    cache = load_existing_cache()
    updates = 0
    
    for _, row in df.iterrows():
        beach_name = row['Name']
        lat = float(row['Latitude'])
        lon = float(row['Longitude'])
        
        key = f"{lat:.6f}_{lon:.6f}"
        
        # Simple update logic - always fetch new data
        try:
            # Fetch weather data
            weather_url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current=temperature_2m,wind_speed_10m,wind_direction_10m&timezone=auto"
            weather_data = requests.get(weather_url, timeout=10).json()
            
            # Fetch marine data
            time.sleep(0.5)
            marine_url = f"https://marine-api.open-meteo.com/v1/marine?latitude={lat}&longitude={lon}&current=wave_height,wave_direction,wave_period"
            marine_data = requests.get(marine_url, timeout=10).json()
            
            # Create entry
            entry = {
                'beach_name': beach_name,
                'latitude': lat,
                'longitude': lon,
                'air_temp': round(weather_data['current'].get('temperature_2m', 'N/A'), 1) if weather_data['current'].get('temperature_2m') is not None else 'N/A',
                'wind_speed': round(weather_data['current'].get('wind_speed_10m', 'N/A'), 1) if weather_data['current'].get('wind_speed_10m') is not None else 'N/A',
                'wind_direction': weather_data['current'].get('wind_direction_10m', 'N/A'),
                'wave_height': round(marine_data['current'].get('wave_height', 'N/A'), 1) if marine_data['current'].get('wave_height') is not None else 'N/A',
                'wave_direction': marine_data['current'].get('wave_direction', 'N/A'),
                'wave_period': round(marine_data['current'].get('wave_period', 'N/A'), 1) if marine_data['current'].get('wave_period') is not None else 'N/A',
                'sea_temp': 'N/A',  # Simplified
                'last_updated': datetime.now().isoformat()
            }
            
            cache[key] = entry
            updates += 1
            logging.info(f"Updated {beach_name}")
            
            # Small delay to avoid rate limiting
            time.sleep(0.1)
            
        except Exception as e:
            logging.error(f"Failed to update {beach_name}: {e}")
    
    # Save updated cache
    save_cache(cache)
    logging.info(f"Completed: {updates} beaches updated, total in cache: {len(cache)}")

def main():
    parser = argparse.ArgumentParser(description='Simple Weather Updater')
    parser.add_argument('--once', action='store_true', help='Run once and exit')
    args = parser.parse_args()
    
    if args.once:
        update_all_beaches()
    else:
        # Continuous mode for local testing
        while True:
            update_all_beaches()
            logging.info("Sleeping for 8 hours...")
            time.sleep(8 * 60 * 60)

if __name__ == "__main__":
    main()
