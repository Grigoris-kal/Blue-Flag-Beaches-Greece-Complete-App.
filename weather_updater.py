#!/usr/bin/env python3
"""
Weather Updater for Blue Flag Beaches Greece
Run this script separately to continuously update weather data
Usage: python weather_updater.py
MODIFIED FOR GITHUB ACTIONS
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
    """Fetch sea temperature for entire Greece in ONE call (cached for 1 hour)"""
    try:
        # Check if we have cached data less than 1 hour old
        if SEA_TEMP_CACHE['data'] is not None and SEA_TEMP_CACHE['last_updated'] is not None:
            time_since_update = datetime.now() - SEA_TEMP_CACHE['last_updated']
            if time_since_update.total_seconds() < 3600:
                logging.info("Using cached sea temperature data (less than 1 hour old)")
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


def get_weather_data(lat, lon, beach_name, sea_temp_data=None):
    """Get weather and marine data from APIs"""
    try:
        # Weather API URLs
        weather_url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current=temperature_2m,wind_speed_10m,wind_direction_10m&timezone=auto&forecast_days=1"
        marine_url = f"https://marine-api.open-meteo.com/v1/marine?latitude={lat}&longitude={lon}&current=wave_height,wave_direction,wave_period&timezone=auto"
        
        # Initialize data structure - MATCH flag.py format exactly
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
        
        # 1. Fetch standard weather data
        response = requests.get(weather_url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            current = data.get('current', {})
            weather_info['air_temp'] = round(current.get('temperature_2m', 'N/A'), 1) if current.get('temperature_2m') is not None else 'N/A'
            weather_info['wind_speed'] = round(current.get('wind_speed_10m', 'N/A'), 1) if current.get('wind_speed_10m') is not None else 'N/A'
            weather_info['wind_direction'] = current.get('wind_direction_10m', 'N/A')
        
        # 2. Fetch wave data
        marine_response = requests.get(marine_url, timeout=10)
        if marine_response.status_code == 200:
            marine_data = marine_response.json()
            current_marine = marine_data.get('current', {})
            weather_info['wave_height'] = round(current_marine.get('wave_height', 'N/A'), 1) if current_marine.get('wave_height') is not None else 'N/A'
            weather_info['wave_direction'] = current_marine.get('wave_direction', 'N/A')
            weather_info['wave_period'] = round(current_marine.get('wave_period', 'N/A'), 1) if current_marine.get('wave_period') is not None else 'N/A'
        
        # 3. Extract sea temperature from the Greece-wide data
        if sea_temp_data is not None:
            try:
                # Find nearest point in NOAA data
                min_distance = float('inf')
                nearest_temp = None

                for key, point in sea_temp_data.items():
                    # Calculate distance (simple approximation)
                    distance = ((point['lat'] - lat)**2 + (point['lon'] - lon)**2)**0.5
                    if distance < min_distance:
                        min_distance = distance
                        nearest_temp = point['temp']

                # Only use if within reasonable distance (about 2.0 degrees)
                if nearest_temp is not None and nearest_temp != "N/A" and min_distance < 2.0:
                    weather_info['sea_temp'] = nearest_temp

            except Exception as e:
                logging.warning(f"Could not extract sea temp for {beach_name}: {str(e)}")

        logging.info(f"Weather fetched for {beach_name}")
        return weather_info

    except Exception as e:
        logging.error(f"Failed to fetch {beach_name}: {str(e)}")
        return None

def commit_changes_to_github():
    """Commit updated weather cache to GitHub repository"""
    try:
        import subprocess
        
        # Configure git (GitHub Actions needs this)
        subprocess.run(['git', 'config', 'user.name', 'GitHub Action'], check=True)
        subprocess.run(['git', 'config', 'user.email', 'action@github.com'], check=True)
        
        # Add the weather cache file
        subprocess.run(['git', 'add', 'weather_cache.json'], check=True)
        
        # Check if there are changes to commit
        result = subprocess.run(['git', 'diff', '--staged', '--quiet'], capture_output=True)
        if result.returncode != 0:  # There are changes
            commit_message = f"Update weather data - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            subprocess.run(['git', 'commit', '-m', commit_message], check=True)
            subprocess.run(['git', 'push'], check=True)
            logging.info("Weather data committed and pushed to GitHub")
        else:
            logging.info("No weather data changes to commit")
            
    except subprocess.CalledProcessError as e:
        logging.error(f"Git operation failed: {e}")
    except Exception as e:
        logging.error(f"Failed to commit changes: {e}")

def update_weather_cache():
    """Load beaches and update weather for all of them"""
    # Load beach data
    save_dir = os.path.join(os.path.expanduser("~"), "MyAPIs", "Blue_Flags_Greece_API", "flag_backend")
    csv_path = os.path.join(save_dir, "blueflag_greece_scraped.csv")
    
    if not os.path.exists(csv_path):
        logging.error(f"Beach data not found at {csv_path}")
        return
    
    # Load beaches - use regex to extract coordinates from anywhere in each row
    import re
    
    df = pd.read_csv(csv_path, header=0)
    
    # Extract coordinates using more flexible regex patterns
    # Allow for more decimal place variations and potential formatting differences
    lat_pattern = r'(?:3[4-9]|4[0-2])\.\d{4,8}'  # 34-42 with 4-8 decimal places
    lon_pattern = r'(?:1[9]|2[0-9])\.\d{4,8}'    # 19-29 with 4-8 decimal places
    
    # Extract coordinates using very broad patterns - catch any decimal numbers
    
    # Find all decimal numbers in each row (even shorter ones)
    df['row_string'] = df.astype(str).apply(lambda x: ','.join(x), axis=1)
    
    # Look for decimal numbers with 1+ decimal places (most flexible)
    all_numbers_pattern = r'\d{1,2}\.\d{1,8}'
    
    def extract_coordinates(row_text):
        import re
        numbers = re.findall(all_numbers_pattern, row_text)
        numbers = [float(n) for n in numbers if '.' in n]
        
        lat, lon = None, None
        
        # More generous Greek coordinate ranges
        # Latitude: 33-43 (slightly expanded)
        # Longitude: 18-30 (slightly expanded) 
        for num in numbers:
            if 33.0 <= num <= 43.0 and lat is None:
                lat = num
            elif 18.0 <= num <= 30.0 and lon is None:
                lon = num
                
        # If we didn't find both, try any reasonable coordinate-like numbers
        if lat is None or lon is None:
            for num in numbers:
                # Fallback: any number that looks like coordinates
                if 30.0 <= num <= 45.0 and lat is None:  # Very broad latitude
                    lat = num
                elif 15.0 <= num <= 35.0 and lon is None:  # Very broad longitude
                    lon = num
        
        return lat, lon
    
    # Apply coordinate extraction
    coords = df['row_string'].apply(extract_coordinates)
    df['Latitude'] = coords.apply(lambda x: x[0])
    df['Longitude'] = coords.apply(lambda x: x[1])
    
    # Clean up temporary column
    df = df.drop('row_string', axis=1)
    
    # Ensure we have Name column (first column)
    cols = list(df.columns)
    if 'Name' not in df.columns and len(cols) > 0:
        df = df.rename(columns={cols[0]: 'Name'})
    
    # Coordinates are already cleaned by regex extraction above
    
    logging.info(f"Loaded {len(df)} beaches from CSV")
    
    # Log beaches with missing coordinates (after cleaning)
    missing_coords = df[df['Latitude'].isna() | df['Longitude'].isna()]
    if len(missing_coords) > 0:
        logging.warning(f"Found {len(missing_coords)} beaches with missing/invalid coordinates:")
        for _, beach in missing_coords.iterrows():
            lat_val = beach.get('Latitude', 'N/A')
            lon_val = beach.get('Longitude', 'N/A') 
            logging.warning(f"  - {beach['Name']} (Lat: {lat_val}, Lon: {lon_val})")
    
    # Filter out beaches without valid coordinates
    df_with_coords = df.dropna(subset=['Latitude', 'Longitude'])
    
    # Get unique locations (some beaches might share coordinates)
    unique_locations = df_with_coords[['Name', 'Latitude', 'Longitude']].drop_duplicates(subset=['Latitude', 'Longitude'])
    total_locations = len(unique_locations)
    
    logging.info(f"Starting weather update for {total_locations} unique beach locations")
    
    # FIRST: Fetch sea temperature for ALL of Greece (1 API call)
    sea_temp_data = fetch_greece_sea_temperature()
    
    # THEN: Fetch weather data in parallel, passing the sea temp data
    weather_data = {}
    
    with ThreadPoolExecutor(max_workers=10) as executor:
        # Submit all tasks WITH the sea temperature data
        future_to_beach = {
            executor.submit(get_weather_data, row['Latitude'], row['Longitude'], row['Name'], sea_temp_data): 
            (row['Latitude'], row['Longitude'], row['Name']) 
            for _, row in unique_locations.iterrows()
        }
        
        # Process completed tasks
        completed = 0
        for future in as_completed(future_to_beach):
            lat, lon, name = future_to_beach[future]
            try:
                result = future.result()
                if result:
                    # CRITICAL: Use EXACT same key format as flag.py expects
                    key = f"{round(lat, 6)}_{round(lon, 6)}"
                    weather_data[key] = result
                    completed += 1
                    if completed % 10 == 0:
                        logging.info(f"Progress: {completed}/{total_locations} beaches updated")
            except Exception as e:
                logging.error(f"Error processing {name}: {str(e)}")
    
    # Save weather data
    cache_path = os.path.join(save_dir, "weather_cache.json")
    with open(cache_path, 'w', encoding='utf-8') as f:
        json.dump(weather_data, f, ensure_ascii=False, indent=2)
    
    logging.info(f"Weather cache updated successfully! Saved to {cache_path}")
    logging.info(f"Updated weather for {len(weather_data)} locations")
    
    # Summary report
    total_beaches = len(df)
    processed_beaches = len(df_with_coords)
    missing_beaches = len(missing_coords)
    
    logging.info(f"SUMMARY: {processed_beaches}/{total_beaches} beaches processed, {missing_beaches} skipped due to missing coordinates")
    
def continuous_update(interval_minutes=30):
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
    parser.add_argument('--interval', type=int, default=30, help='Update interval in minutes (default: 30)')
    
    args = parser.parse_args()
    
    if args.once:
        update_weather_cache()
    else:
        continuous_update(args.interval)
