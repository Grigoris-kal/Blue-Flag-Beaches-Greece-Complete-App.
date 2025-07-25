#!/usr/bin/env python3
"""
Weather Updater for Blue Flag Beaches Greece
Run this script separately to continuously update weather data
Usage: python weather_updater.py
MODIFIED FOR GITHUB ACTIONS WITH BATCH PROCESSING
OPTIMIZED FOR 80% API USAGE REDUCTION
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


# Global variable to store sea temperature data and last update time
SEA_TEMP_CACHE = {
    'data': None,
    'last_updated': None
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

def fetch_greece_sea_temperature():
    """Fetch sea temperature for entire Greece in ONE call (cached for 4 hours)"""
    try:
        # Check if we have cached data less than 4 hours old
        if SEA_TEMP_CACHE['data'] is not None and SEA_TEMP_CACHE['last_updated'] is not None:
            time_since_update = datetime.now() - SEA_TEMP_CACHE['last_updated']
            if time_since_update.total_seconds() < 14400:  # 4 hours
                logging.info("Using cached sea temperature data (less than 4 hours old)")
                return SEA_TEMP_CACHE['data']
        
        logging.info("Fetching fresh sea temperature data for all of Greece...")
        
        # FIXED: Use the correct ERDDAP URL format that we know works
        base_url = "https://coastwatch.pfeg.noaa.gov/erddap/griddap/jplMURSST41.json"
        query = "analysed_sst[(last)][(34):1:(42)][(19):1:(29)]"
        url = f"{base_url}?{query}"
        
        logging.info(f"Fetching from URL: {url}")
        
        response = requests.get(url, timeout=30)
        if response.status_code == 200:
            data = response.json()
            
            # Parse NOAA data into a simple structure
            sst_data = {}
            valid_count = 0
            for row in data['table']['rows']:
                time, lat, lon, sst = row
                if sst is not None and sst > -10 and sst < 50:  # Filter valid Celsius temperatures
                    # NOAA data is already in Celsius - no conversion needed
                    sst_celsius = round(sst, 1)
                    key = f"{lat}_{lon}"
                    sst_data[key] = {
                        'lat': lat,
                        'lon': lon,
                        'temp': sst_celsius
                    }
                    valid_count += 1
            
            # Cache the data
            SEA_TEMP_CACHE['data'] = sst_data
            SEA_TEMP_CACHE['last_updated'] = datetime.now()
            
            logging.info(f"Successfully downloaded sea temperature data for {valid_count} valid points out of {len(data['table']['rows'])} total")
            return sst_data
        else:
            raise Exception(f"Failed to fetch data: HTTP {response.status_code}")
            
    except Exception as e:
        logging.error(f"Failed to fetch Greece sea data: {str(e)}")
        return SEA_TEMP_CACHE['data']  # Return cached data if available

def get_sea_temp_open_meteo(lat, lon, beach_name):
    """Fallback function to get sea temperature from Open-Meteo Marine API"""
    try:
        marine_url = f"https://marine-api.open-meteo.com/v1/marine?latitude={lat}&longitude={lon}&current=sea_surface_temperature&timezone=auto"
        response = requests.get(marine_url, timeout=20)
        if response.status_code == 200:
            data = response.json()
            current = data.get('current', {})
            sea_temp = current.get('sea_surface_temperature')
            if sea_temp is not None:
                logging.info(f"Sea temp for {beach_name}: {sea_temp}°C (Open-Meteo fallback)")
                return round(sea_temp, 1)
    except Exception as e:
        logging.warning(f"Open-Meteo sea temp fallback failed for {beach_name}: {str(e)}")
    
    return 'N/A'

def should_update_beach(existing_data, beach_key):
    """Check if beach weather data needs updating - SMART CACHING"""
    if beach_key not in existing_data:
        return True  # New beach, definitely update
    
    last_data = existing_data[beach_key]
    
    # Skip update if data is less than 6 hours old
    try:
        last_updated = datetime.fromisoformat(last_data.get('last_updated', ''))
        hours_since_update = (datetime.now() - last_updated).total_seconds() / 3600
        
        if hours_since_update < 6:  # Only update if older than 6 hours
            logging.info(f"Skipping {last_data.get('beach_name', 'Unknown')} - updated {hours_since_update:.1f}h ago")
            return False
    except:
        pass  # If can't parse date, update anyway
    
    return True

def get_weather_data(lat, lon, beach_name, sea_temp_data=None):
    """Get weather and marine data from APIs with retry logic"""
    max_retries = 3
    base_delay = 2  # INCREASED from 1 to 2 seconds
    
    for attempt in range(max_retries):
        try:
            # Add small delay between requests to avoid overwhelming the API
            if attempt > 0:
                delay = base_delay * (2 ** attempt)  # Exponential backoff
                time.sleep(delay)
                logging.info(f"Retry {attempt + 1} for {beach_name} after {delay}s delay")
            
            # Weather API URLs
            weather_url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current=temperature_2m,wind_speed_10m,wind_direction_10m&timezone=auto&forecast_days=1"
            marine_url = f"https://marine-api.open-meteo.com/v1/marine?latitude={lat}&longitude={lon}&current=wave_height,wave_direction,wave_period&timezone=auto"
            
            # Initialize data structure
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
            
            # 1. Fetch standard weather data with longer timeout
            response = requests.get(weather_url, timeout=20)  # Increased timeout
            if response.status_code == 200:
                data = response.json()
                current = data.get('current', {})
                weather_info['air_temp'] = round(current.get('temperature_2m', 'N/A'), 1) if current.get('temperature_2m') is not None else 'N/A'
                weather_info['wind_speed'] = round(current.get('wind_speed_10m', 'N/A'), 1) if current.get('wind_speed_10m') is not None else 'N/A'
                weather_info['wind_direction'] = current.get('wind_direction_10m', 'N/A')
            
            # INCREASED delay between API calls
            time.sleep(1.5)  # INCREASED from 0.5 to 1.5 seconds
            
            # 2. Fetch wave data with longer timeout
            marine_response = requests.get(marine_url, timeout=20)  # Increased timeout
            if marine_response.status_code == 200:
                marine_data = marine_response.json()
                current_marine = marine_data.get('current', {})
                weather_info['wave_height'] = round(current_marine.get('wave_height', 'N/A'), 1) if current_marine.get('wave_height') is not None else 'N/A'
                weather_info['wave_direction'] = current_marine.get('wave_direction', 'N/A')
                weather_info['wave_period'] = round(current_marine.get('wave_period', 'N/A'), 1) if current_marine.get('wave_period') is not None else 'N/A'
            
            # 3. Extract sea temperature - NOAA first, then Open-Meteo fallback
            try:
                # Try NOAA first (existing logic)
                sea_temp = 'N/A'
                if sea_temp_data is not None:
                    min_distance = float('inf')
                    nearest_temp = None

                    for key, point in sea_temp_data.items():
                        distance = ((point['lat'] - lat)**2 + (point['lon'] - lon)**2)**0.5
                        if distance < min_distance:
                            min_distance = distance
                            nearest_temp = point['temp']

                    # Use NOAA if within reasonable distance
                    if nearest_temp is not None and nearest_temp != "N/A" and min_distance < 2.0:
                        sea_temp = nearest_temp
                        logging.info(f"Sea temp for {beach_name}: {sea_temp}°C (NOAA)")
                
                # If NOAA failed, try Open-Meteo Marine API
                if sea_temp == 'N/A':
                    sea_temp = get_sea_temp_open_meteo(lat, lon, beach_name)
                
                weather_info['sea_temp'] = sea_temp

            except Exception as e:
                logging.warning(f"Could not get sea temp for {beach_name}: {str(e)}")
                weather_info['sea_temp'] = 'N/A'

            logging.info(f"Weather fetched for {beach_name}")
            return weather_info

        except requests.Timeout:
            logging.warning(f"Timeout for {beach_name} (attempt {attempt + 1}/{max_retries})")
            if attempt == max_retries - 1:
                logging.error(f"Failed to fetch {beach_name} after {max_retries} attempts - timeout")
                return None
        except Exception as e:
            logging.warning(f"Error for {beach_name} (attempt {attempt + 1}/{max_retries}): {str(e)}")
            if attempt == max_retries - 1:
                logging.error(f"Failed to fetch {beach_name} after {max_retries} attempts: {str(e)}")
                return None
    
    return None

def load_existing_cache():
    """Load existing weather cache if it exists"""
    save_dir = os.getcwd()
    cache_path = os.path.join(save_dir, "weather_cache.json")
    
    if os.path.exists(cache_path):
        try:
            with open(cache_path, 'r', encoding='utf-8') as f:
                existing_data = json.load(f)
            logging.info(f"Loaded existing cache with {len(existing_data)} entries")
            return existing_data
        except Exception as e:
            logging.warning(f"Could not load existing cache: {str(e)}")
    
    return {}


def update_weather_cache(batch_size=None, batch_number=None):
    """Load beaches and update weather for all of them or a specific batch"""
    # Load beach data - GitHub Actions environment
    save_dir = os.getcwd()  # Current working directory in GitHub Actions
    csv_path = os.path.join(save_dir, "blueflag_greece_scraped.csv")
    
    if not os.path.exists(csv_path):
        logging.error(f"Beach data not found at {csv_path}")
        return
    
    # Load beaches - use regex to extract coordinates from anywhere in each row
    import re
    
    df = pd.read_csv(csv_path, header=0)
    
    # Clean the data first - handle actual CSV columns properly
    # Clean latitude and longitude columns if they exist and have data

    if 'Latitude' in df.columns and 'Longitude' in df.columns:
        # Strip whitespace and convert to numeric
        df['Latitude'] = df['Latitude'].astype(str).str.strip()
        df['Longitude'] = df['Longitude'].astype(str).str.strip()
        df['Latitude'] = pd.to_numeric(df['Latitude'], errors='coerce')
        df['Longitude'] = pd.to_numeric(df['Longitude'], errors='coerce')
        
        # Log how many we found from direct columns
        direct_coords = df.dropna(subset=['Latitude', 'Longitude'])
        logging.info(f"Found {len(direct_coords)} beaches with direct Lat/Lon columns")
    
    # For beaches still missing coordinates, try regex extraction
    missing_coords_mask = df['Latitude'].isna() | df['Longitude'].isna()
    if missing_coords_mask.sum() > 0:
        logging.info(f"Attempting regex extraction for {missing_coords_mask.sum()} beaches with missing coordinates")
        
        # Create row string for regex extraction
        df_missing = df[missing_coords_mask].copy()
        df_missing['row_string'] = df_missing.astype(str).apply(lambda x: ','.join(x), axis=1)
        
        def extract_coordinates_no_filter(row_text):
            import re
            # Find ALL decimal numbers - no geographic filtering at all
            pattern = r'\d+\.\d+'
            matches = re.findall(pattern, row_text)
            numbers = [float(m) for m in matches]
            
            lat, lon = None, None
            
            # NO FILTERING - just take first two reasonable decimal numbers
            # Assume first coordinate-like number is latitude, second is longitude
            coordinate_candidates = [n for n in numbers if n > 10 and n < 50]  # Very broad range
            
            if len(coordinate_candidates) >= 2:
                lat = coordinate_candidates[0]
                lon = coordinate_candidates[1]
            elif len(coordinate_candidates) == 1:
                # If only one number, try to guess if it's lat or lon based on typical ranges
                num = coordinate_candidates[0]
                if 30 <= num <= 45:  # More likely latitude
                    lat = num
                elif 15 <= num <= 35:  # More likely longitude  
                    lon = num
            
            return lat, lon
        
        # Apply regex extraction to missing coordinates
        extracted_coords = df_missing['row_string'].apply(extract_coordinates_no_filter)
        
        # Update the main dataframe
        for idx, (lat, lon) in zip(df_missing.index, extracted_coords):
            if lat is not None and pd.isna(df.loc[idx, 'Latitude']):
                df.loc[idx, 'Latitude'] = lat
            if lon is not None and pd.isna(df.loc[idx, 'Longitude']):
                df.loc[idx, 'Longitude'] = lon
    
    # Clean up temporary column if it exists
    if 'row_string' in df.columns:
        df = df.drop('row_string', axis=1)
    
    # Ensure we have Name column (first column)
    cols = list(df.columns)
    if 'Name' not in df.columns and len(cols) > 0:
        df = df.rename(columns={cols[0]: 'Name'})
    
    logging.info(f"Loaded {len(df)} beaches from CSV")
    
    # Log beaches with missing coordinates
    missing_coords = df[df['Latitude'].isna() | df['Longitude'].isna()]
    if len(missing_coords) > 0:
        logging.warning(f"Found {len(missing_coords)} beaches with missing/invalid coordinates:")
        for _, beach in missing_coords.iterrows():
            lat_val = beach.get('Latitude', 'N/A')
            lon_val = beach.get('Longitude', 'N/A') 
            logging.warning(f"  - {beach['Name']} (Lat: {lat_val}, Lon: {lon_val})")
    
    # Filter out beaches without valid coordinates
    df_with_coords = df.dropna(subset=['Latitude', 'Longitude'])
    
    # Get unique locations
    unique_locations = df_with_coords[['Name', 'Latitude', 'Longitude']].drop_duplicates(subset=['Latitude', 'Longitude'])
    total_locations = len(unique_locations)
    
    # BATCH PROCESSING: Determine which beaches to process
    if batch_size is not None and batch_number is not None:
        # Process specific batch
        start_idx = batch_number * batch_size
        end_idx = min(start_idx + batch_size, total_locations)
        
        # Get this batch
        locations_to_process = unique_locations.iloc[start_idx:end_idx]
        
        logging.info(f"BATCH PROCESSING: Processing batch {batch_number + 1}")
        logging.info(f"Total locations: {total_locations}, Batch size: {batch_size}")
        logging.info(f"Processing beaches {start_idx + 1}-{end_idx} ({len(locations_to_process)} beaches)")
        
        if locations_to_process.empty:
            logging.info("No beaches in this batch - all done!")
            return
    else:
        # Process all locations (original behavior)
        locations_to_process = unique_locations
        logging.info(f"Starting weather update for {total_locations} unique beach locations")
    
    # Fetch sea temperature for Greece
    sea_temp_data = fetch_greece_sea_temperature()
    
    # Load existing cache (ALWAYS load to preserve existing data)
    existing_weather_data = load_existing_cache()
    
    # SMART CACHING: Filter locations that actually need updating
    locations_needing_update = []
    for _, row in locations_to_process.iterrows():
        # Generate primary key format
        lat, lon, name = row['Latitude'], row['Longitude'], row['Name']
        primary_key = f"{round(lat, 6)}_{round(lon, 6)}"
        
        if should_update_beach(existing_weather_data, primary_key):
            locations_needing_update.append(row)

    if not locations_needing_update:
        logging.info("🎉 No beaches need updating - all data is recent!")
        return

    logging.info(f"🔄 SMART UPDATE: Processing {len(locations_needing_update)} out of {len(locations_to_process)} beaches")
    
    # Fetch weather data in parallel (REDUCED workers)
    new_weather_data = {}
    
    with ThreadPoolExecutor(max_workers=3) as executor:  # REDUCED from 8 to 3 workers
        # Submit only beaches that need updating
        future_to_beach = {
            executor.submit(get_weather_data, row['Latitude'], row['Longitude'], row['Name'], sea_temp_data): 
            (row['Latitude'], row['Longitude'], row['Name']) 
            for row in locations_needing_update  # Only process filtered beaches
        }
        
        # Process completed tasks
        completed = 0
        for future in as_completed(future_to_beach):
            lat, lon, name = future_to_beach[future]
            try:
                result = future.result()
                if result:
                    # CRITICAL: Generate multiple key formats for mobile app compatibility
                    # This is the KEY FIX - generate keys with different decimal precisions
                    for decimals in [7, 6, 5, 4, 3]:
                        key = f"{round(lat, decimals)}_{round(lon, decimals)}"
                        if key not in new_weather_data:  # Avoid overwriting
                            new_weather_data[key] = result
                    
                    completed += 1
                    if batch_size is not None:
                        logging.info(f"Progress: {completed}/{len(locations_needing_update)} beaches updated in this batch")
                    else:
                        if completed % 10 == 0:
                            logging.info(f"Progress: {completed}/{len(locations_needing_update)} beaches updated")
            except Exception as e:
                logging.error(f"Error processing {name}: {str(e)}")
    
    # Merge new data with existing cache (ALWAYS merge to preserve all data)
    existing_weather_data.update(new_weather_data)
    weather_data = existing_weather_data
    
    # Save weather data
    cache_path = os.path.join(save_dir, "weather_cache.json")
    with open(cache_path, 'w', encoding='utf-8') as f:
        json.dump(weather_data, f, ensure_ascii=False, indent=2)
    
    if batch_size is not None and batch_number is not None:
        logging.info(f"✅ Batch {batch_number + 1} completed successfully!")
        logging.info(f"📊 Updated weather for {len(new_weather_data)} locations in this batch")
        logging.info(f"💾 Total cache now contains {len(weather_data)} locations")
    else:
        logging.info(f"✅ Weather cache updated successfully! Saved to {cache_path}")
        logging.info(f"📊 Updated weather for {len(new_weather_data)} locations")
    
    # Summary report
    total_beaches = len(df)
    processed_beaches = len(df_with_coords)
    missing_beaches = len(missing_coords)
    
    if batch_size is not None and batch_number is not None:
        logging.info(f"BATCH SUMMARY: {len(locations_needing_update)} beaches processed in batch {batch_number + 1}")
        logging.info(f"Overall progress: {min((batch_number + 1) * batch_size, total_locations)}/{total_locations} total locations processed")
    else:
        logging.info(f"SUMMARY: {processed_beaches}/{total_beaches} beaches processed, {missing_beaches} skipped due to missing coordinates")
        logging.info(f"🚀 API OPTIMIZATION: Only updated beaches older than 6 hours - saved ~{len(locations_to_process) - len(locations_needing_update)} API calls!")


def continuous_update(interval_minutes=240):
    """Continuously update weather data at specified interval"""
    logging.info(f"Starting continuous weather updates every {interval_minutes} minutes")
    
    while True:
        try:
            update_weather_cache()
            logging.info(f"Next update in {interval_minutes} minutes...")
            time.sleep(interval_minutes * 60)
        except KeyboardInterrupt:
            logging.info("Weather updater stopped by user")
            break
        except Exception as e:
            logging.error(f"Unexpected error: {str(e)}")
            logging.info("Retrying in 5 minutes...")
            time.sleep(300)  # Wait 5 minutes before retry


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Weather updater for Blue Flag Beaches')
    parser.add_argument('--once', action='store_true', help='Run once and exit')
    parser.add_argument('--interval', type=int, default=240, help='Update interval in minutes (default: 240 = 4 hours)')
    parser.add_argument('--batch-size', type=int, help='Number of beaches to process per batch (optional)')
    parser.add_argument('--batch-number', type=int, help='Batch number to process (0-indexed, optional)')
    
    args = parser.parse_args()
    
    if args.once:
        update_weather_cache(batch_size=args.batch_size, batch_number=args.batch_number)
    else:
        continuous_update(args.interval)
