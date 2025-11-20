#!/usr/bin/env python3
"""
Weather Updater for Blue Flag Beaches Greece - OPTIMIZED VERSION
Maintains all original functionality while reducing resource usage by:
- Smart caching (skip fresh data)
- Rate-limited API calls
- Memory-efficient processing
- Batched threading
- Atomic file writes
"""

from dotenv import load_dotenv
# Load environment variables from .env file (only when not in GitHub Actions)
import os
if not os.getenv('GITHUB_ACTIONS'):
    load_dotenv('JAWG_TOKEN.env')

import pandas as pd
import requests
import json
import time
import os
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import logging
import psutil
import resource
import gzip
import shutil
from ratelimit import limits, sleep_and_retry

# Configuration constants
CACHE_CONFIG = {
    'sea_temp_hours': 4,       # Cache sea temp for 4 hours
    'weather_hours': 6,        # Cache weather for 6 hours
    'max_cache_size': 1000,    # Maximum entries to keep in memory
    'cache_clean_interval': 10 # Clean cache every 10 updates
}

# Global variable to store sea temperature data
SEA_TEMP_CACHE = {
    'data': None,
    'last_updated': None,
    'size': 0
}

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('weather_updater.log'),
        logging.StreamHandler()
    ]
)

def check_memory_usage():
    """Log memory usage information and set soft limits"""
    process = psutil.Process(os.getpid())
    mem_info = process.memory_info()
    logging.info(f"Memory usage: {mem_info.rss / 1024 / 1024:.2f} MB RSS")
    
    # Set soft memory limit (512MB)
    soft_limit = 512 * 1024 * 1024
    resource.setrlimit(resource.RLIMIT_AS, (soft_limit, resource.RLIM_INFINITY))

@sleep_and_retry
@limits(calls=30, period=60)  # 30 calls per minute
def call_api(url):
    """Rate-limited API caller with retry logic"""
    try:
        response = requests.get(url, timeout=20)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        logging.warning(f"API call failed: {str(e)}")
        raise

def fetch_greece_sea_temperature():
    """Fetch sea temperature for entire Greece in ONE call (cached for 4 hours)"""
    try:
        # Check cache validity
        if SEA_TEMP_CACHE['data'] and SEA_TEMP_CACHE['last_updated']:
            time_since_update = datetime.now() - SEA_TEMP_CACHE['last_updated']
            if time_since_update.total_seconds() < CACHE_CONFIG['sea_temp_hours'] * 3600:
                logging.info("Using cached sea temperature data")
                return SEA_TEMP_CACHE['data']
        
        logging.info("Fetching fresh sea temperature data...")
        
        # NOAA ERDDAP API
        base_url = "https://coastwatch.pfeg.noaa.gov/erddap/griddap/jplMURSST41.json"
        query = "analysed_sst[(last)][(34):1:(42)][(19):1:(29)]"
        url = f"{base_url}?{query}"
        
        data = call_api(url)
        
        # Parse NOAA data
        sst_data = {}
        valid_count = 0
        for row in data['table']['rows']:
            time, lat, lon, sst = row
            if sst is not None and -10 < sst < 50:  # Valid range
                sst_celsius = round(sst, 1)
                key = f"{lat}_{lon}"
                sst_data[key] = {
                    'lat': lat,
                    'lon': lon,
                    'temp': sst_celsius
                }
                valid_count += 1
        
        # Update cache
        SEA_TEMP_CACHE['data'] = sst_data
        SEA_TEMP_CACHE['last_updated'] = datetime.now()
        SEA_TEMP_CACHE['size'] = valid_count
        
        logging.info(f"Downloaded sea temps for {valid_count} points")
        return sst_data
            
    except Exception as e:
        logging.error(f"Sea temp fetch failed: {str(e)}")
        return SEA_TEMP_CACHE['data']  # Return cached if available

def get_sea_temp(lat, lon, sea_temp_data, beach_name):
    """Get sea temperature with fallback logic"""
    try:
        # Try NOAA first
        if sea_temp_data:
            min_distance = float('inf')
            nearest_temp = None

            for key, point in sea_temp_data.items():
                distance = ((point['lat'] - lat)**2 + (point['lon'] - lon)**2)**0.5
                if distance < min_distance:
                    min_distance = distance
                    nearest_temp = point['temp']

            if nearest_temp is not None and min_distance < 2.0:
                logging.debug(f"Sea temp for {beach_name}: {nearest_temp}°C (NOAA)")
                return nearest_temp
        
        # Fallback to Open-Meteo
        marine_url = f"https://marine-api.open-meteo.com/v1/marine?latitude={lat}&longitude={lon}&current=sea_surface_temperature"
        data = call_api(marine_url)
        sea_temp = data.get('current', {}).get('sea_surface_temperature')
        
        if sea_temp is not None:
            logging.debug(f"Sea temp for {beach_name}: {sea_temp}°C (Open-Meteo)")
            return round(sea_temp, 1)
            
    except Exception as e:
        logging.warning(f"Sea temp fallback failed for {beach_name}: {str(e)}")
    
    return 'N/A'

def clean_weather_cache(cache):
    """Remove old entries from weather cache"""
    now = datetime.now()
    cleaned_cache = {}
    removed = 0
    
    for key, data in cache.items():
        try:
            last_updated = datetime.fromisoformat(data.get('last_updated', ''))
            hours_since_update = (now - last_updated).total_seconds() / 3600
            if hours_since_update < CACHE_CONFIG['weather_hours'] * 3:  # Keep 3x cache time
                cleaned_cache[key] = data
            else:
                removed += 1
        except:
            cleaned_cache[key] = data  # Keep if date parsing fails
    
    logging.info(f"Cache cleaning: Removed {removed} stale entries")
    return cleaned_cache

def load_existing_cache():
    """Load existing weather cache with memory check"""
    save_dir = os.getcwd()
    cache_path = os.path.join(save_dir, "weather_cache.json")
    
    if os.path.exists(cache_path):
        try:
            with open(cache_path, 'r', encoding='utf-8') as f:
                existing_data = json.load(f)
            
            # Initial clean if cache is large
            if len(existing_data) > CACHE_CONFIG['max_cache_size']:
                existing_data = clean_weather_cache(existing_data)
                
            logging.info(f"Loaded cache with {len(existing_data)} entries")
            return existing_data
        except Exception as e:
            logging.warning(f"Cache load failed: {str(e)}")
    
    return {}

def save_weather_cache(data):
    """Save cache with atomic write and optional compression"""
    temp_path = "weather_cache.tmp"
    final_path = "weather_cache.json"
    
    try:
        # Atomic write
        with open(temp_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(temp_path, final_path)
        
        # Compress if large
        if os.path.getsize(final_path) > 1024 * 1024:  # >1MB
            with open(final_path, 'rb') as f_in:
                with gzip.open(final_path + '.gz', 'wb') as f_out:
                    shutil.copyfileobj(f_in, f_out)
            logging.info("Created compressed cache backup")
            
    except Exception as e:
        logging.error(f"Cache save failed: {str(e)}")

def get_weather_data(lat, lon, beach_name, sea_temp_data=None):
    """Optimized weather data fetcher with cache reuse"""
    # First check memory
    check_memory_usage()
    
    # Generate cache key
    key = f"{round(lat, 6)}_{round(lon, 6)}"
    
    # Try to reuse existing data if fresh
    existing_cache = load_existing_cache()
    if key in existing_cache:
        data = existing_cache[key]
        try:
            last_updated = datetime.fromisoformat(data.get('last_updated', ''))
            hours_since_update = (datetime.now() - last_updated).total_seconds() / 3600
            
            if hours_since_update < CACHE_CONFIG['weather_hours'] / 2:  # 3 hours
                logging.info(f"Reusing recent data for {beach_name}")
                # Only update sea temp if missing/stale
                if data['sea_temp'] == 'N/A' or hours_since_update > 2:
                    data['sea_temp'] = get_sea_temp(lat, lon, sea_temp_data, beach_name)
                    data['last_updated'] = datetime.now().isoformat()
                return data
        except:
            pass  # Proceed to full update if date parsing fails
    
    # Full API fetch
    weather_info = {
        'beach_name': beach_name,
        'latitude': lat,
        'longitude': lon,
        'air_temp': 'N/A',
        'wind_speed': 'N/A',
        'wind_direction': 'N/A',
        'wave_height': 'N/A',
        'wave_direction': 'N/A',
        'wave_period': 'N/A',
        'sea_temp': 'N/A',
        'last_updated': datetime.now().isoformat()
    }
    
    try:
        # Get weather data
        weather_url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current=temperature_2m,wind_speed_10m,wind_direction_10m&timezone=auto"
        weather_data = call_api(weather_url)
        current = weather_data.get('current', {})
        weather_info['air_temp'] = round(current.get('temperature_2m', 'N/A'), 1) if current.get('temperature_2m') is not None else 'N/A'
        weather_info['wind_speed'] = round(current.get('wind_speed_10m', 'N/A'), 1) if current.get('wind_speed_10m') is not None else 'N/A'
        weather_info['wind_direction'] = current.get('wind_direction_10m', 'N/A')
        
        # Get wave data
        time.sleep(1)  # Rate limit pause
        marine_url = f"https://marine-api.open-meteo.com/v1/marine?latitude={lat}&longitude={lon}&current=wave_height,wave_direction,wave_period"
        marine_data = call_api(marine_url)
        current_marine = marine_data.get('current', {})
        weather_info['wave_height'] = round(current_marine.get('wave_height', 'N/A'), 1) if current_marine.get('wave_height') is not None else 'N/A'
        weather_info['wave_direction'] = current_marine.get('wave_direction', 'N/A')
        weather_info['wave_period'] = round(current_marine.get('wave_period', 'N/A'), 1) if current_marine.get('wave_period') is not None else 'N/A'
        
        # Get sea temp
        weather_info['sea_temp'] = get_sea_temp(lat, lon, sea_temp_data, beach_name)
        
        logging.info(f"Updated {beach_name}")
        return weather_info
        
    except Exception as e:
        logging.error(f"Failed to update {beach_name}: {str(e)}")
        return None

def update_beaches_in_batches(beaches, sea_temp_data):
    """Process beaches sequentially to avoid thread limits"""
    batch_size = 20  # Smaller batches
    total_batches = (len(beaches) + batch_size - 1) // batch_size
    new_data = {}
    
    for batch_num in range(total_batches):
        start_idx = batch_num * batch_size
        end_idx = start_idx + batch_size
        batch = beaches[start_idx:end_idx]
        
        # SEQUENTIAL PROCESSING INSTEAD OF THREADED
        for row in batch:
            try:
                result = get_weather_data(row['Latitude'], row['Longitude'], row['Name'], sea_temp_data)
                if result:
                    # Generate multiple key formats for compatibility
                    for decimals in [7, 6, 5, 4, 3]:
                        key = f"{round(row['Latitude'], decimals)}_{round(row['Longitude'], decimals)}"
                        if key not in new_data:
                            new_data[key] = result
            except Exception as e:
                logging.error(f"Processing failed for {row['Name']}: {str(e)}")
        
        # Pause between batches
        if batch_num < total_batches - 1:
            time.sleep(15)  # Longer pause
    
    return new_data

def load_beaches_optimized():
    """Load beach data with optimized coordinate parsing"""
    csv_path = os.path.join(os.getcwd(), "blueflag_greece_scraped.csv")
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"Beach data not found at {csv_path}")
    
    # FIXED: Add engine='python' and error handling
    try:
        df = pd.read_csv(csv_path, header=0, engine='python')
    except pd.errors.ParserError:
        df = pd.read_csv(csv_path, header=0, engine='python', error_bad_lines=False)
    
    # Clean coordinate columns if they exist
    if 'Latitude' in df.columns and 'Longitude' in df.columns:
        df['Latitude'] = pd.to_numeric(df['Latitude'], errors='coerce')
        df['Longitude'] = pd.to_numeric(df['Longitude'], errors='coerce')
    
    # Ensure Name column exists
    if 'Name' not in df.columns and len(df.columns) > 0:
        df = df.rename(columns={df.columns[0]: 'Name'})
    
    return df.dropna(subset=['Latitude', 'Longitude'])

def update_weather_cache(batch_size=None, batch_number=None):
    """Main update function with all optimizations"""
    check_memory_usage()
    
    try:
        # Load beaches
        df = load_beaches_optimized()
        unique_locations = df[['Name', 'Latitude', 'Longitude']].drop_duplicates()
        
        # Batch processing logic
        if batch_size and batch_number is not None:
            start_idx = batch_number * batch_size
            end_idx = start_idx + batch_size
            locations_to_process = unique_locations.iloc[start_idx:end_idx]
            logging.info(f"Processing batch {batch_number + 1} ({len(locations_to_process)} beaches)")
        else:
            locations_to_process = unique_locations
            logging.info(f"Processing all {len(locations_to_process)} beaches")
        
        # Filter beaches needing updates
        existing_cache = load_existing_cache()
        beaches_needing_update = [
            row for _, row in locations_to_process.iterrows()
            if should_update_beach(existing_cache, row)
        ]
        
        if not beaches_needing_update:
            logging.info("All beaches are up-to-date!")
            return
        
        # Get sea temps
        sea_temp_data = fetch_greece_sea_temperature()
        
        # Process in optimized batches
        new_data = update_beaches_in_batches(beaches_needing_update, sea_temp_data)
        
        # Merge with existing cache
        existing_cache.update(new_data)
        
        # Periodic cache cleaning
        if len(existing_cache) > CACHE_CONFIG['max_cache_size']:
            existing_cache = clean_weather_cache(existing_cache)
        
        # Save results
        save_weather_cache(existing_cache)
        logging.info(f"Updated {len(new_data)} beaches. Total in cache: {len(existing_cache)}")
        
    except Exception as e:
        logging.error(f"Update failed: {str(e)}", exc_info=True)
        raise

def should_update_beach(cache, row):
    """Check if a beach needs updating"""
    key = f"{round(row['Latitude'], 6)}_{round(row['Longitude'], 6)}"
    
    if key not in cache:
        return True
    
    try:
        last_updated = datetime.fromisoformat(cache[key].get('last_updated', ''))
        hours_since_update = (datetime.now() - last_updated).total_seconds() / 3600
        return hours_since_update >= CACHE_CONFIG['weather_hours']
    except:
        return True

def continuous_update(interval_minutes=480):
    """Run updates continuously with optimized intervals"""
    logging.info(f"Starting optimized updater (interval: {interval_minutes} mins)")
    
    while True:
        try:
            update_weather_cache()
            logging.info(f"Sleeping for {interval_minutes} minutes...")
            time.sleep(interval_minutes * 60)
        except KeyboardInterrupt:
            logging.info("Stopped by user")
            break
        except Exception as e:
            logging.error(f"Update cycle failed: {str(e)}")
            time.sleep(300)  # Wait 5 minutes before retry

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Optimized Weather Updater')
    parser.add_argument('--once', action='store_true', help='Run once and exit')
    parser.add_argument('--interval', type=int, default=480, help='Update interval in minutes')
    parser.add_argument('--batch-size', type=int, help='Batch size for partial processing')
    parser.add_argument('--batch-number', type=int, help='Batch number (0-indexed)')
    
    args = parser.parse_args()
    
    if args.once:
        update_weather_cache(args.batch_size, args.batch_number)
    else:
        continuous_update(args.interval)


