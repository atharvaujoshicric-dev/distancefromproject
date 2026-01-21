import streamlit as st
import pandas as pd
from geopy.geocoders import Nominatim
import requests
import time
import re

# --- CONFIGURATION ---
st.set_page_config(page_title="Car Route Proximity Dashboard", layout="wide")

st.title("🚗 Real Estate Proximity & Market Intelligence")
st.markdown("""
This dashboard calculates **car driving distances** and searches for **Ticket Sizes (Price)** and **Configurations (1-5 BHK)** using free open-source tools.
""")

# --- LOGIC FUNCTIONS ---

def get_coordinates(query):
    """Geocode address to Lat/Long using OpenStreetMap (Free)."""
    geolocator = Nominatim(user_agent="real_estate_car_router_v5")
    try:
        location = geolocator.geocode(query, timeout=10)
        if location:
            return (location.latitude, location.longitude)
    except:
        return None
    return None

def get_car_route_distance(origin, destination):
    """Gets driving distance (Car Route) in KM using OSRM."""
    try:
        # origin/destination are (lat, lon)
        url = f"http://router.project-osrm.org/route/v1/driving/{origin[1]},{origin[0]};{destination[1]},{destination[0]}?overview=false"
        r = requests.get(url, timeout=10)
        data = r.json()
        if data['code'] == 'Ok':
            # Returns distance in meters, convert to KM
            return round(data['routes'][0]['distance'] / 1000, 2)
    except:
        return "N/A"
    return "N/A"

def fetch_market_intelligence(society, locality, city):
    """Scrapes market data for Price and 1-5 BHK configurations."""
    # We add 1-5 BHK in the query to force the search engine to find those patterns
    search_query = f"{society} {locality} {city} 1bhk 2bhk 3bhk 4bhk 5bhk price"
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    
    try:
        res = requests.get(f"https://html.duckduckgo.com/html/?q={search_query}", headers=headers, timeout=10)
        text = res.text.lower()
        
        # 1. EXTRACT ALL BHKs (1 to 5)
        # We look for digits followed by BHK (e.g., 1BHK, 1 BHK, 2BHK...)
        bhk_patterns = re.findall(r'([1-5]\s?bhk)', text)
        found_configs = sorted(list(set([b.upper().replace(" ", "") for b in bhk_patterns])))
        config_str = ", ".join(found_configs) if found_configs else "2 BHK, 3 BHK (Likely)"
        
        # 2. EXTRACT TICKET SIZE (Price)
        # Searching for patterns like 1.2 Cr, 90 Lakhs, ₹ 1.5Cr
        price_patterns = [
            r'(\d+\.?\d*\s?cr(?:ore)?)', 
            r'(\d+\.?\d*\s?lakh(?:s)?)',
            r'(\d+\.?\d*\s?lac(?:s)?)',
            r'(?:rs\.?|₹)\s?(\d+\.?\d*)'
        ]
        
        extracted_prices = []
        for p in price_patterns:
            matches = re.findall(p, text)
            if matches: extracted_prices.extend(matches)
        
        # Return the best price found or a placeholder
        ticket_size = extracted_prices[0].strip() if extracted_prices else "See Market Rates"
        
        return ticket_size, config_str
    except:
        return "Search Error", "Search Error"

def extract_project_coords(url):
    """Extract Lat/Long from Google Maps URL."""
    try:
        if "goo.gl" in url or "google" in url:
            r = requests.get(url, allow_redirects=True, timeout=10)
            url = r.url
        match = re.search(r'@([-.\d]+),([-.\d]+)', url)
        if match: return float(match.group(1)), float(match.group(2))
        match_alt = re.search(r'!3d([-.\d]+)!4d([-.\d]+)', url)
        if match_alt: return float(match_alt.group(1)), float(match_alt.group(2))
    except: pass
    return None

# --- UI INTERFACE ---

with st.sidebar:
    st.header("1. Input Project Location")
    project_url = st.text_input("Paste Project Google Maps Link")
    st.divider()
    st.header("2. Process Data")
    process_btn = st.button("Calculate Distances & Market Data")

uploaded_file = st.file_uploader("Upload Society List (Excel/CSV)", type=['csv', 'xlsx'])

if uploaded_file and project_url and process_btn:
    # Read Data
    if uploaded_file.name.endswith('.csv'):
        df = pd.read_csv(uploaded_file)
    else:
        df = pd.read_excel(uploaded_file)
    
    # Check if required columns exist
    if 'society' not in df.columns or 'locality' not in df.columns:
        st.error("Your file must contain 'society' and 'locality' columns.")
    else:
        # Get Project Coordinates
        project_coords = extract_project_coords(project_url)
        
        if not project_coords:
            st.error("Invalid Google Maps Link. Please copy the full link from your browser.")
        else:
            st.info(f"Project Coordinates: {project_coords}. Starting Analysis...")
            
            results = []
            progress = st.progress(0)
            status_note = st.empty()
            
            for i, row in df.iterrows():
                soc = str(row['society'])
                loc = str(row['locality'])
                city = str(row.get('city', 'Pune')) # Default to Pune if city column missing
                
                status_note.text(f"Processing ({i+1}/{len(df)}): {soc}")
                
                # A. Find Society Location
                soc_coords = get_coordinates(f"{soc}, {loc}, {city}")
                
                # B. Calculate CAR ROUTE Distance
                dist_label = "Location Not Found"
                if soc_coords:
                    dist_km = get_car_route_distance(project_coords, soc_coords)
                    dist_label = f"{dist_km} km" if dist_km != "N/A" else "Route Error"
                
                # C. Find Price & Config (1-5 BHK)
                price, configs = fetch_market_intelligence(soc, loc, city)
                
                results.append({
                    "Distance from project": dist_label,
                    "Ticket Size": price,
                    "Configurations": configs
                })
                
                # Progress and Anti-block delay
                progress.progress((i + 1) / len(df))
                time.sleep(1.2) # Mandatory delay for free geocoding
            
            # Append 3 new columns to the end
            results_df = pd.DataFrame(results)
            final_df = pd.concat([df.reset_index(drop=True), results_df], axis=1)
            
            st.success("Analysis Complete!")
            st.dataframe(final_df)
            
            # Download
            csv_output = final_df.to_csv(index=False).encode('utf-8')
            st.download_button("Download Processed File", csv_output, "Final_Project_Dashboard.csv", "text/csv")
