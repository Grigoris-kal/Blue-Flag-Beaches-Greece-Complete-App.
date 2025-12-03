#!/usr/bin/env python3
"""
Weather Updater for Blue Flag Beaches Greece - SIMPLIFIED VERSION
NO SCHEDULE LOGIC - Just updates when GitHub Actions tells it to run
"""

from __future__ import annotations
import argparse
import os
import logging
import pandas as pd
import requests
import json
import time
from datetime import datetime
from typing import Dict, Any, Optional

# ---------- Early parse for data_dir ----------
parser = argparse.ArgumentParser(add_help=False)
parser.add_argument('--data-dir', default='.', help='Directory for cache, logs, and data files')
args_known, _ = parser.parse_known_args()
data_dir = os.path.abspath(args_known.data_dir)
os.makedirs(data_dir, exist_ok=True)

# ---------- Logging ----------
log_path = os.path.join(data_dir, 'weather_updater.log')
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_path),
        logging.StreamHandler()
    ]
)

# ---------- Simple Config ----------
CONFIG = {
    'max_retries': 3,
    'retry_delay': 5,
    'api_delay': 0.5  # Delay between API calls
}

# ---------- Rate Limiting ----------
import functools

def rate_limited(max_calls=25, period=60):
    """Simple rate limiter."""
    import time
    from threading import Lock
    
    lock = Lock()
    min_interval = period / max_calls
    
    def decorator(func):
        last_called = [0.0]
        
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            with lock:
                elapsed = time.time() - last_called[0]
                left_to_wait = min_interval - elapsed
                if left_to_wait > 0:
                    time.sleep(left_to_wait)
                last_called[0] = time.time()
                return func(*args, **kwargs)
        return wrapper
    return decorator

@rate_limited(max_calls=25, period=60)
def call_api(url: str) -> Any:
    """API call with retry logic."""
    for attempt in range(CONFIG['max_retries']):
        try:
            r = requests.get(url, timeout=15)
            r.raise_for_status()
            return r.json()
        except requests.exceptions.RequestException as e:
            if attempt < CONFIG['max_retries'] - 1:
                wait = CONFIG['retry_delay'] * (attempt + 1)
                logging.warning(f"API call failed (attempt {attempt + 1}): {e}. Retrying in {wait}s...")
                time.sleep(wait)
            else:
                logging.error(f"API call failed after {CONFIG['max_retries']} attempts: {e}")
                raise

# ---------- Cache Management ----------
def load_existing_cache() -> Dict[str, Any]:
    """Load existing cache - NO DELETION, NO CLEANING."""
    cache_path = os.path.join(data_dir, "weather_cache.json")
    if os.path.exists(cache_path):
        try:
            with open(cache_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            if isinstance(data, dict):
                logging.info(f"Loaded existing cache with {len(data)} entries")
                return data
        except Exception as e:
            logging.warning(f"Failed to load existing cache: {e}")
    return {}

def save_batch_cache(batch_data: Dict[str, Any], batch_num: int) -> None:
    """Save batch-specific cache."""
    batch_filename = f"weather_cache_batch_{batch_num}.json"
    batch_path = os.path.join(data_dir, batch_filename)
    
    try:
        # Save batch file
        with open(batch_path, 'w', encoding='utf-8') as f:
            json.dump(batch_data, f, ensure_ascii=False, indent=2)
        logging.info(f"Saved batch {batch_num} with {len(batch_data)} entries")
        
        # Update main cache (ADD/UPDATE, never delete)
        combined_path = os.path.join(data_dir, "weather_cache.json")
        existing = load_existing_cache()
        existing.update(batch_data)  # This adds new and updates existing
        
        with open(combined_path, 'w', encoding='utf-8') as f:
            json.dump(existing, f, ensure_ascii=False, indent=2)
            
    except Exception as e:
        logging.error(f"Failed to save batch cache: {e}")

# ---------- Beach Loading ----------
def load_beaches() -> pd.DataFrame:
    """Load beach data."""
    csv_path = os.path.join(data_dir, "blueflag_greece_scraped.csv")
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"Beach data not found at {csv_path}")
    
    try:
        df = pd.read_csv(csv_path, engine='python')
    except pd.errors.ParserError:
        df = pd.read_csv(csv_path, engine='python', on_bad_lines='skip')
    
    # Validate and clean
    required_cols = ['Name', 'Latitude', 'Longitude']
    for col in required_cols:
        if col not in df.columns:
            raise ValueError(f"Missing required column: {col}")
    
    df['Latitude'] = pd.to_numeric(df['Latitude'], errors='coerce')
    df['Longitude'] = pd.to_numeric(df['Longitude'], errors='coerce')
    df = df.dropna(subset=['Latitude', 'Longitude'])
    
    # Create consistent key
    df['cache_key'] = df.apply(
        lambda row: f"{row['Latitude']:.7f}_{row['Longitude']:.7f}", 
        axis=1
    )
    
    logging.info(f"Loaded {len(df)} beaches")
    return df

# ---------- Weather Fetching ----------
def fetch_weather_data(lat: float, lon: float, beach_name: str) -> Optional[Dict[str, Any]]:
    """Fetch ALL weather data for a location."""
    try:
        # Weather data
        weather_url = (
            f"https://api.open-meteo.com/v1/forecast?"
            f"latitude={lat}&longitude={lon}&"
            f"current=temperature_2m,wind_speed_10m,wind_direction_10m&"
            f"timezone=auto"
        )
        weather_data = call_api(weather_url)
        
        # Marine data
        time.sleep(1)  # Small delay between APIs
        marine_url = (
            f"https://marine-api.open-meteo.com/v1/marine?"
            f"latitude={lat}&longitude={lon}&"
            f"current=wave_height,wave_direction,wave_period,sea_surface_temperature"
        )
        marine_data = call_api(marine_url)
        
        # Build complete entry
        current = weather_data.get('current', {})
        marine = marine_data.get('current', {})
        
        entry = {
            'beach_name': beach_name,
            'latitude': lat,
            'longitude': lon,
            'air_temp': round(current.get('temperature_2m', 'N/A'), 1) if current.get('temperature_2m') is not None else 'N/A',
            'wind_speed': round(current.get('wind_speed_10m', 'N/A'), 1) if current.get('wind_speed_10m') is not None else 'N/A',
            'wind_direction': current.get('wind_direction_10m', 'N/A'),
            'wave_height': round(marine.get('wave_height', 'N/A'), 1) if marine.get('wave_height') is not None else 'N/A',
            'wave_direction': marine.get('wave_direction', 'N/A'),
            'wave_period': round(marine.get('wave_period', 'N/A'), 1) if marine.get('wave_period') is not None else 'N/A',
            'sea_temp': round(marine.get('sea_surface_temperature', 'N/A'), 1) if marine.get('sea_surface_temperature') is not None else 'N/A',
            'last_updated': datetime.now().isoformat()
        }
        
        logging.info(f"Fetched weather for {beach_name}")
        return entry
        
    except Exception as e:
        logging.error(f"Failed to fetch weather for {beach_name}: {e}")
        return None

# ---------- Main Processing ----------
def process_batch(batch_size: Optional[int] = None, batch_number: Optional[int] = None) -> Dict[str, Any]:
    """
    Process a batch of beaches.
    SIMPLE RULE: Update every beach in the batch.
    Let GitHub Actions control frequency via schedule.
    """
    df = load_beaches()
    
    total_beaches = len(df)
    if batch_size is None or batch_number is None:
        start_idx = 0
        end_idx = total_beaches
        logging.info(f"Processing all {total_beaches} beaches")
    else:
        start_idx = batch_number * batch_size
        end_idx = min(start_idx + batch_size, total_beaches)
        if start_idx >= total_beaches:
            logging.warning(f"Batch {batch_number} out of range")
            return {}
        logging.info(f"Processing batch {batch_number}: beaches {start_idx} to {end_idx-1}")
    
    batch_updates = {}
    
    for idx in range(start_idx, end_idx):
        row = df.iloc[idx]
        cache_key = row['cache_key']
        
        # ALWAYS FETCH NEW DATA - GitHub Actions controls frequency
        logging.info(f"Updating {row['Name']}")
        entry = fetch_weather_data(row['Latitude'], row['Longitude'], row['Name'])
        
        if entry:
            batch_updates[cache_key] = entry
            time.sleep(CONFIG['api_delay'])  # Small delay between beaches
    
    logging.info(f"Batch completed: {len(batch_updates)} updates")
    return batch_updates

# ---------- Main ----------
def main():
    parser = argparse.ArgumentParser(description="Weather Updater - Simple Version")
    parser.add_argument('--once', action='store_true', help='Run once and exit')
    parser.add_argument('--interval', type=int, default=480, help='Interval minutes (unused in GitHub Actions)')
    parser.add_argument('--batch-size', type=int, help='Batch size for partial processing')
    parser.add_argument('--batch-number', type=int, help='Batch number (0-indexed)')
    parser.add_argument('--data-dir', default='.', help='Directory for cache, logs, and data files')
    args = parser.parse_args()
    
    global data_dir
    data_dir = os.path.abspath(args.data_dir)
    os.makedirs(data_dir, exist_ok=True)
    
    logging.info("Starting SIMPLE weather updater")
    logging.info("GitHub Actions controls update frequency via cron schedule")
    
    if args.once:
        batch_updates = process_batch(args.batch_size, args.batch_number)
        if batch_updates:
            save_batch_cache(batch_updates, args.batch_number or 0)
        else:
            logging.info("No updates in this batch")
    else:
        # Continuous mode (for local testing)
        while True:
            try:
                batch_updates = process_batch(args.batch_size, args.batch_number)
                if batch_updates:
                    save_batch_cache(batch_updates, args.batch_number or 0)
                logging.info(f"Sleeping for {args.interval} minutes")
                time.sleep(args.interval * 60)
            except KeyboardInterrupt:
                logging.info("Interrupted by user")
                break
            except Exception as e:
                logging.error(f"Update loop exception: {e}", exc_info=True)
                time.sleep(300)

if __name__ == "__main__":
    main()
