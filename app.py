import streamlit as st
import pandas as pd
from geopy.geocoders import Nominatim
import requests
import time
import re

# --- SETUP ---
st.set_page_config(page_title="Real Estate Dashboard - Pro", layout="wide")

st.title("Project Proximity & Market Intelligence")
st.markdown("Using **OpenStreetMap** (Free) & **DuckDuckGo** (Free) to analyze your society list.")

# --- IMPROVED SEARCH LOGIC ---

def get_soc_coordinates(society, locality, city):
    """
    Tries multiple search combinations to find the society location.
    """
    geolocator = Nominatim(user_agent="real_estate_locator_v3")
    
    # Clean up the society name (removes common suffixes that confuse search engines)
    clean_soc = re.sub(r'\b(CHSL|CHS|Society|Phase \d+|Wing [A-Z])\b', '', society, flags=re.IGNORECASE).strip()
    
    # List of queries to try in order of specificity
    queries = [
        f"{society}, {locality}, {city}",         # 1. Full Specific (Exact)
        f"{clean_soc}, {locality}, {city}",       # 2. Cleaned Society + Locality
        f"{society}, {city}",                     # 3. Society + City
        f"{locality}, {city}"                     # 4. Fallback: Just the Locality
    ]
    
    for q in queries:
        try:
            location = geolocator.geocode(q, timeout=10)
            if location:
                return (location.latitude, location.longitude), q
        except:
            continue
        time.sleep(1) # Respect Nominatim's 1-second rule
        
    return None, None

def extract_coords_from_url(url):
    """Extracts Lat/Long from a Google Maps Link."""
    try:
        if "goo.gl" in url or "maps.app.goo.gl" in url or "googleusercontent" in url:
            response = requests.get(url, allow_redirects=True, timeout=10)
            url = response.url
        
        match = re.search(r'@([-.\d]+),([-.\d]+)', url)
        if match:
            return float(match.group(1)), float(match.group(2))
        
        match_alt = re.search(r'!3d([-.\d]+)!4d([-.\d]+)', url)
        if match_alt:
            return float(match_alt.group(1)), float(match_alt.group(2))
    except:
        pass
    return None

def get_osrm_distance(origin_coords, dest_coords):
    """Calculates road distance using OSRM."""
    try:
        url = f"http://router.project-osrm.org/route/v1/driving/{origin_coords[1]},{origin_coords[0]};{dest_coords[1]},{dest_coords[0]}?overview=false"
        r = requests.get(url, timeout=10)
        data = r.json()
        if data['code'] == 'Ok':
            return round(data['routes'][0]['distance'] / 1000, 2)
    except:
        return "N/A"
    return "N/A"

def fetch_market_info(society, locality, city):
    """Searches web snippets for Price and BHK."""
    query = f"{society} {locality} {city} price BHK"
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        res = requests.get(f"https://html.duckduckgo.com/html/?q={query}", headers=headers, timeout=10)
        text = res.text.lower()
        
        # Extract BHK
        bhk = re.findall(r'(\d\s?bhk)', text)
        config = ", ".join(sorted(list(set(bhk)))).upper() if bhk else "1, 2, 3 BHK"
        
        # Extract Price
        price_match = re.findall(r'(\d+\.?\d*\s?(?:cr|lakh|lac))', text)
        price = price_match[0].strip() if price_match else "See Website"
        
        return price, config
    except:
        return "N/A", "N/A"

# --- STREAMLIT UI ---
with st.sidebar:
    st.header("1. Project Location")
    proj_link = st.text_input("Paste Google Maps Link")
    st.divider()
    st.header("2. Search Options")
    st.info("The tool will combine 'society' + 'locality' + 'city' for the best match.")
    run_btn = st.button("Generate Dashboard")

uploaded_file = st.file_uploader("Upload your CSV/Excel", type=['csv', 'xlsx'])

if uploaded_file and proj_link and run_btn:
    # Load Data
    df = pd.read_csv(uploaded_file) if uploaded_file.name.endswith('.csv') else pd.read_excel(uploaded_file)
    
    # Get Project Point
    proj_coords = extract_coords_from_url(proj_link)
    
    if not proj_coords:
        st.error("Invalid Google Maps Link. Please copy the URL from your browser address bar.")
    else:
        st.success(f"Target Project Location identified.")
        
        results = []
        progress = st.progress(0)
        status = st.empty()
        
        for idx, row in df.iterrows():
            soc = str(row.get('society', ''))
            loc = str(row.get('locality', ''))
            city = str(row.get('city', 'Pune'))
            
            status.text(f"Searching: {soc} in {loc}...")
            
            # Step 1: Geocode
            coords, found_via = get_soc_coordinates(soc, loc, city)
            
            # Step 2: Distance
            dist_val = "Not Found"
            if coords:
                dist_val = get_osrm_distance(proj_coords, coords)
                if isinstance(dist_val, float):
                    dist_val = f"{dist_val} km"
            
            # Step 3: Market Data
            price, config = fetch_market_info(soc, loc, city)
            
            results.append({
                "Distance from project": dist_val,
                "Ticket Size": price,
                "Configurations": config,
                "Matched Via": found_via if found_via else "None"
            })
            
            progress.progress((idx + 1) / len(df))
            
        # Merge results
        res_df = pd.concat([df, pd.DataFrame(results)], axis=1)
        
        st.subheader("Analysis Result")
        st.dataframe(res_df)
        
        # Download
        csv = res_df.to_csv(index=False).encode('utf-8')
        st.download_button("Download Updated Excel", csv, "final_project_analysis.csv", "text/csv")
