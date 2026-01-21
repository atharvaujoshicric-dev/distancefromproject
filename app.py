import streamlit as st
import pandas as pd
from geopy.geocoders import Nominatim
import requests
import time
import re

# --- SETUP ---
st.set_page_config(page_title="Free Real Estate Proximity Dashboard", layout="wide")

st.title("Project Proximity & Market Dashboard")
st.markdown("Enter your **Google Maps Link**, upload your file, and get distance/market data for free.")

# --- HELPER FUNCTIONS ---

def extract_coords_from_url(url):
    """Extracts Latitude and Longitude from a Google Maps URL."""
    try:
        # 1. Handle shortened links (maps.app.goo.gl)
        if "maps.app.goo.gl" in url:
            response = requests.get(url, allow_redirects=True, timeout=10)
            url = response.url
            
        # 2. Extract from URL using Regex (e.g., .../@18.521,73.856,17z/...)
        match = re.search(r'@([-.\d]+),([-.\d]+)', url)
        if match:
            return float(match.group(1)), float(match.group(2))
        
        # 3. Fallback for some desktop formats (.../place/Address/data=...!3d18.521!4d73.856)
        match_alt = re.search(r'!3d([-.\d]+)!4d([-.\d]+)', url)
        if match_alt:
            return float(match_alt.group(1)), float(match_alt.group(2))
            
    except Exception as e:
        st.error(f"Error parsing URL: {e}")
    return None

def get_soc_coordinates(address):
    """Get Lat/Long for the society using OpenStreetMap (Free)."""
    try:
        geolocator = Nominatim(user_agent="real_estate_agent_app_v2")
        # Adding 'Pune' to narrow search scope for better accuracy
        location = geolocator.geocode(f"{address}, Pune, Maharashtra")
        if location:
            return (location.latitude, location.longitude)
    except:
        return None
    return None

def get_osrm_distance(origin_coords, dest_coords):
    """Get driving distance in KM using OSRM (Free)."""
    try:
        # origin_coords: (lat, lon)
        url = f"http://router.project-osrm.org/route/v1/driving/{origin_coords[1]},{origin_coords[0]};{dest_coords[1]},{dest_coords[0]}?overview=false"
        r = requests.get(url, timeout=10)
        data = r.json()
        if data['code'] == 'Ok':
            return round(data['routes'][0]['distance'] / 1000, 2)
    except:
        return "Error"
    return "N/A"

def fetch_market_info_free(society, locality):
    """Basic search-based extraction for Price and Configuration."""
    search_query = f"{society} {locality} Pune price configuration"
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        res = requests.get(f"https://html.duckduckgo.com/html/?q={search_query}", headers=headers, timeout=10)
        text = res.text.lower()
        
        # Simple Logic to find BHK
        bhk_match = re.findall(r'(\d\s?bhk)', text)
        config = ", ".join(sorted(list(set(bhk_match)))).upper() if bhk_match else "2, 3 BHK"
        
        # Simple Logic to find Price
        price_match = re.findall(r'(\d+\.?\d*\s?(?:cr|lakh|lac))', text)
        price = price_match[0].strip() if price_match else "Contact Developer"
        
        return price, config
    except:
        return "N/A", "N/A"

# --- SIDEBAR ---
with st.sidebar:
    st.header("Project Info")
    project_link = st.text_input("Paste Google Maps Link", placeholder="https://maps.app.goo.gl/...")
    process_btn = st.button("Generate Dashboard")

# --- MAIN INTERFACE ---
uploaded_file = st.file_uploader("Upload Excel/CSV (Columns: society, locality)", type=['csv', 'xlsx'])

if uploaded_file and process_btn and project_link:
    # Read file
    if uploaded_file.name.endswith('.csv'):
        df = pd.read_csv(uploaded_file)
    else:
        df = pd.read_excel(uploaded_file)
    
    # 1. Get Project Coordinates from URL
    with st.spinner("Extracting coordinates from Google Maps link..."):
        project_coords = extract_coords_from_url(project_link)
    
    if not project_coords:
        st.error("Could not find coordinates in that link. Make sure it's a direct Google Maps pin link.")
    else:
        st.success(f"Project Coordinates Found: {project_coords[0]}, {project_coords[1]}")
        
        # Prep containers for results
        distances = []
        prices = []
        configs = []
        
        progress_bar = st.progress(0)
        status = st.empty()
        
        for i, row in df.iterrows():
            soc = str(row.get('society', ''))
            loc = str(row.get('locality', ''))
            status.text(f"Processing ({i+1}/{len(df)}): {soc}")
            
            # Step A: Get Society Coordinates
            soc_coords = get_soc_coordinates(f"{soc}, {loc}")
            
            # Step B: Calculate Distance
            if soc_coords:
                dist = get_osrm_distance(project_coords, soc_coords)
                distances.append(f"{dist} km" if isinstance(dist, float) else dist)
            else:
                distances.append("Location Not Found")
            
            # Step C: Market Data
            p, c = fetch_market_info_free(soc, loc)
            prices.append(p)
            configs.append(c)
            
            progress_bar.progress((i + 1) / len(df))
            time.sleep(1) # Important: Stay within Free Geocoding limits
            
        # Add columns to DataFrame
        df['Distance from project'] = distances
        df['Ticket Size'] = prices
        df['Configurations'] = configs
        
        status.text("Done!")
        st.subheader("Market Intelligence Table")
        st.dataframe(df)
        
        # Download button
        csv = df.to_csv(index=False).encode('utf-8')
        st.download_button("Download Result", csv, "property_analysis.csv", "text/csv")

elif not project_link and process_btn:
    st.warning("Please paste a Google Maps Link in the sidebar.")
