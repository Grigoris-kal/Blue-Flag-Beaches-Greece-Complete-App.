#!/usr/bin/env python3
"""
Weather Updater (Option B) - write only NEW/UPDATED entries per batch.

Behavior:
- Loads the existing canonical cache from data_dir/weather_cache.json (if present)
- Determines which beaches need update (based on last_updated)
- Fetches data for only those beaches in the given batch
- Writes a partial cache JSON (only updated entries) to data_dir/weather_cache.json
  - If no entries updated, writes an empty JSON object {}
- Designed to be run in a CI matrix job; the combine job merges partial results.
"""

from __future__ import annotations
import argparse
import os
import logging
from dotenv import load_dotenv
import pandas as pd
import requests
import json
import time
from datetime import datetime
import psutil
import resource
import gzip
import shutil
from ratelimit import limits, sleep_and_retry
from typing import Dict, Any, Optional

# ---------- Arguments and data_dir early parse ----------
parser = argparse.ArgumentParser(add_help=False)
parser.add_argument('--data-dir', default='.', help='Directory for cache, logs, and data files')
args_known, _ = parser.parse_known_args()
data_dir = os.path.abspath(args_known.data_dir)
os.makedirs(data_dir, exist_ok=True)

# ---------- Logging (to data_dir) ----------
log_path = os.path.join(data_dir, 'weather_updater.log')
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_path),
        logging.StreamHandler()
    ]
)

# Load local env file only when not running in GitHub Actions
if not os.getenv('GITHUB_ACTIONS'):
    env_path = os.path.join(data_dir, 'JAWG_TOKEN.env')
    if os.path.exists(env_path):
        load_dotenv(env_path)

# ---------- Imports that require logging configured ----------
# (already imported above)

# ---------- Config ----------
CACHE_CONFIG = {
    'sea_temp_hours': 4,       # Cache sea temp for 4 hours
    'weather_hours': 6,        # Cache weather for 6 hours
    'max_cache_size': 10000,   # safety limit (full cache size)
    'cache_clean_interval': 10
}

SEA_TEMP_CACHE = {
    'data': None,
    'last_updated': None,
    'size': 0
}

# ---------- Helpers ----------
def check_memory_usage():
    try:
        process = psutil.Process(os.getpid())
        mem_info = process.memory_info()
        logging.info(f"Memory usage: {mem_info.rss / 1024 / 1024:.2f} MB RSS")
        soft_limit = 512 * 1024 * 1024
        # setrlimit may not be available on all platforms; guard it
        try:
            resource.setrlimit(resource.RLIMIT_AS, (soft_limit, resource.RLIM_INFINITY))
        except Exception:
            pass
    except Exception:
        logging.debug("psutil not available or failed to read memory info")

@sleep_and_retry
@limits(calls=30, period=60)  # rate-limit: 30 calls per minute
def call_api(url: str) -> Any:
    try:
        r = requests.get(url, timeout=20)
        r.raise_for_status()
        return r.json()
    except requests.exceptions.RequestException as e:
        logging.warning(f"API call failed ({url}): {e}")
        raise

def load_existing_cache() -> Dict[str, Any]:
    """Load canonical cache from data_dir (if present)."""
    cache_path = os.path.join(data_dir, "weather_cache.json")
    if os.path.exists(cache_path):
        try:
            with open(cache_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            if isinstance(data, dict):
                logging.info(f"Loaded existing cache with {len(data)} entries")
                # Optionally clean if too large
                if len(data) > CACHE_CONFIG['max_cache_size']:
                    logging.info("Existing cache too large; performing light cleaning")
                    return clean_weather_cache(data)
                return data
            else:
                logging.warning("Existing cache file is not a JSON object; ignoring")
        except Exception as e:
            logging.warning(f"Failed to load existing cache: {e}")
    return {}

def save_partial_cache(partial: Dict[str, Any]) -> None:
    """Write only the partial (updated) entries into data_dir/weather_cache.json atomically.
    If partial is empty, still write an empty JSON object {} so artifact uploader sees a file.
    """
    temp = os.path.join(data_dir, "weather_cache.tmp")
    final = os.path.join(data_dir, "weather_cache.json")
    try:
        with open(temp, 'w', encoding='utf-8') as f:
            json.dump(partial, f, ensure_ascii=False, indent=2)
        os.replace(temp, final)
        logging.info(f"Wrote partial cache with {len(partial)} entries to {final}")
        # optional compression for large partials
        if os.path.getsize(final) > 1024 * 1024:
            with open(final, 'rb') as f_in, gzip.open(final + '.gz', 'wb') as f_out:
                shutil.copyfileobj(f_in, f_out)
            logging.info("Created compressed partial cache backup")
    except Exception as e:
        logging.error(f"Failed to write partial cache: {e}")

def clean_weather_cache(cache: Dict[str, Any]) -> Dict[str, Any]:
    now = datetime.now()
    cleaned = {}
    removed = 0
    for key, v in cache.items():
        try:
            last = v.get('last_updated', '')
            if last:
                last_dt = datetime.fromisoformat(last)
                hours = (now - last_dt).total_seconds() / 3600.0
                if hours < CACHE_CONFIG['weather_hours'] * 3:
                    cleaned[key] = v
                else:
                    removed += 1
            else:
                cleaned[key] = v
        except Exception:
            cleaned[key] = v
    logging.info(f"clean_weather_cache: removed {removed} stale entries")
    return cleaned

# ---------- Sea temp fetching (cached) ----------
def fetch_greece_sea_temperature():
    try:
        if SEA_TEMP_CACHE['data'] and SEA_TEMP_CACHE['last_updated']:
            elapsed = (datetime.now() - SEA_TEMP_CACHE['last_updated']).total_seconds()
            if elapsed < CACHE_CONFIG['sea_temp_hours'] * 3600:
                logging.info("Using cached sea-temperature dataset")
                return SEA_TEMP_CACHE['data']
        logging.info("Fetching sea temperature dataset (NOAA ERDDAP)...")
        base_url = "https://coastwatch.pfeg.noaa.gov/erddap/griddap/jplMURSST41.json"
        query = "analysed_sst[(last)][(34):1:(42)][(19):1:(29)]"
        url = f"{base_url}?{query}"
        data = call_api(url)
        sst = {}
        count = 0
        for row in data['table']['rows']:
            _, lat, lon, temp = row
            if temp is not None and -10 < temp < 50:
                key = f"{round(lat,6)}_{round(lon,6)}"
                sst[key] = {'lat': lat, 'lon': lon, 'temp': round(temp,1)}
                count += 1
        SEA_TEMP_CACHE['data'] = sst
        SEA_TEMP_CACHE['last_updated'] = datetime.now()
        SEA_TEMP_CACHE['size'] = count
        logging.info(f"Fetched sea temps for {count} points")
        return sst
    except Exception as e:
        logging.warning(f"fetch_greece_sea_temperature failed: {e}")
        return SEA_TEMP_CACHE.get('data') or {}

def get_sea_temp(lat: float, lon: float, sea_temp_data: Dict[str, Any], beach_name: str):
    try:
        if sea_temp_data:
            best_d = float('inf')
            best_t = None
            for p in sea_temp_data.values():
                d = ((p['lat'] - lat)**2 + (p['lon'] - lon)**2)**0.5
                if d < best_d:
                    best_d = d
                    best_t = p['temp']
            if best_t is not None and best_d < 2.0:
                return best_t
        # fallback to marine-api
        marine_url = f"https://marine-api.open-meteo.com/v1/marine?latitude={lat}&longitude={lon}&current=sea_surface_temperature"
        data = call_api(marine_url)
        val = data.get('current', {}).get('sea_surface_temperature')
        if val is not None:
            return round(val,1)
    except Exception as e:
        logging.debug(f"sea temp fallback failed for {beach_name}: {e}")
    return 'N/A'

# ---------- Weather fetcher (returns full entry dict) ----------
def get_weather_data(lat: float, lon: float, beach_name: str, sea_temp_data: Dict[str,Any]) -> Optional[Dict[str,Any]]:
    check_memory_usage()
    entry = {
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
        weather_url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current=temperature_2m,wind_speed_10m,wind_direction_10m&timezone=auto"
        w = call_api(weather_url)
        cur = w.get('current', {})
        if cur.get('temperature_2m') is not None:
            entry['air_temp'] = round(cur.get('temperature_2m'),1)
        if cur.get('wind_speed_10m') is not None:
            entry['wind_speed'] = round(cur.get('wind_speed_10m'),1)
        entry['wind_direction'] = cur.get('wind_direction_10m', 'N/A')

        time.sleep(1)  # small pause
        marine_url = f"https://marine-api.open-meteo.com/v1/marine?latitude={lat}&longitude={lon}&current=wave_height,wave_direction,wave_period"
        m = call_api(marine_url)
        cm = m.get('current', {})
        if cm.get('wave_height') is not None:
            entry['wave_height'] = round(cm.get('wave_height'),1)
        entry['wave_direction'] = cm.get('wave_direction', 'N/A')
        if cm.get('wave_period') is not None:
            entry['wave_period'] = round(cm.get('wave_period'),1)

        entry['sea_temp'] = get_sea_temp(lat, lon, sea_temp_data, beach_name)
        logging.info(f"Fetched weather for {beach_name}")
        return entry
    except Exception as e:
        logging.warning(f"get_weather_data failed for {beach_name}: {e}")
        return None

# ---------- Load beaches ----------
def load_beaches_optimized() -> pd.DataFrame:
    csv_path = os.path.join(data_dir, "blueflag_greece_scraped.csv")
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"Beach data not found at {csv_path}")
    try:
        df = pd.read_csv(csv_path, header=0, engine='python')
    except pd.errors.ParserError:
        df = pd.read_csv(csv_path, header=0, engine='python', error_bad_lines=False)
    # normalize coords
    if 'Latitude' in df.columns and 'Longitude' in df.columns:
        df['Latitude'] = pd.to_numeric(df['Latitude'], errors='coerce')
        df['Longitude'] = pd.to_numeric(df['Longitude'], errors='coerce')
    if 'Name' not in df.columns and len(df.columns) > 0:
        df = df.rename(columns={df.columns[0]: 'Name'})
    return df.dropna(subset=['Latitude','Longitude'])

def should_update_beach(cache: Dict[str,Any], row: pd.Series) -> bool:
    key = f"{round(row['Latitude'],6)}_{round(row['Longitude'],6)}"
    if key not in cache:
        return True
    try:
        last = cache[key].get('last_updated','')
        if not last:
            return True
        last_dt = datetime.fromisoformat(last)
        hours = (datetime.now() - last_dt).total_seconds() / 3600.0
        return hours >= CACHE_CONFIG['weather_hours']
    except Exception:
        return True

# ---------- Main batch processing (produces only updates) ----------
def update_weather_cache(batch_size: Optional[int]=None, batch_number: Optional[int]=None):
    check_memory_usage()
    # Load beaches
    df = load_beaches_optimized()
    unique_locations = df[['Name','Latitude','Longitude']].drop_duplicates().reset_index(drop=True)

    # Determine which slice to process
    if batch_size is not None and batch_number is not None:
        start = batch_number * batch_size
        end = start + batch_size
        slice_df = unique_locations.iloc[start:end]
        logging.info(f"Processing batch {batch_number} -> {len(slice_df)} beaches")
    else:
        slice_df = unique_locations
        logging.info(f"Processing entire dataset -> {len(slice_df)} beaches")

    # Load existing full cache once
    existing_cache = load_existing_cache()

    # Filter beaches that need update (based on existing cache)
    to_update = []
    for _, row in slice_df.iterrows():
        if should_update_beach(existing_cache, row):
            to_update.append(row)

    if not to_update:
        logging.info("No beaches in this batch need updates. Writing empty partial cache {}")
        save_partial_cache({})  # write an empty object so artifact uploader has a file
        return

    # Fetch sea temp dataset once
    sea_temp_data = fetch_greece_sea_temperature() or {}

    # Collect only updated entries
    partial_updates: Dict[str, Any] = {}
    for row in to_update:
        try:
            entry = get_weather_data(row['Latitude'], row['Longitude'], row['Name'], sea_temp_data)
            if entry:
                # Use high-precision keys so merge is robust; these keys match canonical key format
                for decimals in (7,6,5,4,3):
                    k = f"{round(row['Latitude'], decimals)}_{round(row['Longitude'], decimals)}"
                    # only set if not already added (prefer highest precision)
                    if k not in partial_updates:
                        partial_updates[k] = entry
                        break
        except Exception as e:
            logging.error(f"Error processing {row['Name']}: {e}")

    # Save only partial updates (could be empty if all fetches failed)
    save_partial_cache(partial_updates)

# ---------- CLI ----------
def main():
    parser = argparse.ArgumentParser(description="Weather Updater - Option B (partial updates)")
    parser.add_argument('--once', action='store_true', help='Run once and exit')
    parser.add_argument('--interval', type=int, default=480, help='Interval minutes for continuous run')
    parser.add_argument('--batch-size', type=int, help='Batch size for partial processing')
    parser.add_argument('--batch-number', type=int, help='Batch number (0-indexed)')
    parser.add_argument('--data-dir', default='.', help='Directory for cache, logs, and data files')
    args = parser.parse_args()

    # Respect passed data-dir (override earlier)
    global data_dir
    data_dir = os.path.abspath(args.data_dir)
    os.makedirs(data_dir, exist_ok=True)

    if args.once:
        update_weather_cache(args.batch_size, args.batch_number)
    else:
        while True:
            try:
                update_weather_cache(args.batch_size, args.batch_number)
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
