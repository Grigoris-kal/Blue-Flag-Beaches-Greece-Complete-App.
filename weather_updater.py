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
    # MODIFIED: Use GitHub Actions compatible file paths
    save_dir = os.path.dirname(os.path.abspath(__file__))  # Use current directory
    
    # Try multiple possible CSV locations
    csv_files = [
        os.path.join(save_dir, "blueflag_greece_scraped.csv"),
        "blueflag_greece_scraped.csv",  # Current directory
        "./blueflag_greece_scraped.csv"  # Explicit current directory
    ]
    
    csv_path = None
    for path in csv_files:
        if os.path.exists(path):
            csv_path = path
            break
    
    if not csv_path:
        logging.error("Beach data CSV not found in any expected location")
        logging.error(f"Searched in: {csv_files}")
        return
    
    logging.info(f"Using CSV file: {csv_path}")
    
    # Load beaches
    df = pd.read_csv(csv_path)
    df = df.dropna(subset=['Latitude', 'Longitude'])
    
    # Get unique locations (some beaches might share coordinates)
    unique_locations = df[['Name', 'Latitude', 'Longitude']].drop_duplicates(subset=['Latitude', 'Longitude'])
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
                    key = f"{lat}_{lon}"
                    weather_data[key] = result
                    completed += 1
                    if completed % 10 == 0:
                        logging.info(f"Progress: {completed}/{total_locations} beaches updated")
            except Exception as e:
                logging.error(f"Error processing {name}: {str(e)}")
    
    # MODIFIED: Save weather data to repository root
    cache_path = "weather_cache.json"
    with open(cache_path, 'w', encoding='utf-8') as f:
        json.dump(weather_data, f, ensure_ascii=False, indent=2)
    
    logging.info(f"Weather cache updated successfully! Saved to {cache_path}")
    logging.info(f"Updated weather for {len(weather_data)} locations")
    
    # NEW: Commit changes to GitHub if running in GitHub Actions
    if os.getenv('GITHUB_ACTIONS') == 'true':
        commit_changes_to_github()

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