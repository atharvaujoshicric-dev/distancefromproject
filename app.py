import streamlit as st
import pandas as pd
from geopy.geocoders import Nominatim
import requests
import time
import re

# --- SETUP ---
st.set_page_config(page_title="Real Estate Market Analyzer", layout="wide")

st.title("Project Proximity & Market Intelligence")
st.markdown("Automated Analysis for Pune Real Estate (Free Version)")

# --- LOGIC FUNCTIONS ---

def get_soc_coordinates(society, locality, city="Pune"):
    geolocator = Nominatim(user_agent="pune_re_explorer_v4")
    # Clean society name for better matching
    clean_soc = re.sub(r'\b(CHSL|CHS|Society|Phase \d+|Wing [A-Z]|Limited)\b', '', society, flags=re.IGNORECASE).strip()
    
    queries = [f"{society}, {locality}, {city}", f"{clean_soc}, {locality}, {city}", f"{locality}, {city}"]
    
    for q in queries:
        try:
            location = geolocator.geocode(q, timeout=10)
            if location: return (location.latitude, location.longitude), q
        except: continue
        time.sleep(1.1) 
    return None, None

def extract_coords_from_url(url):
    try:
        if any(x in url for x in ["goo.gl", "googleusercontent", "maps.app.goo.gl"]):
            response = requests.get(url, allow_redirects=True, timeout=10)
            url = response.url
        match = re.search(r'@([-.\d]+),([-.\d]+)', url)
        if match: return float(match.group(1)), float(match.group(2))
        match_alt = re.search(r'!3d([-.\d]+)!4d([-.\d]+)', url)
        if match_alt: return float(match_alt.group(1)), float(match_alt.group(2))
    except: pass
    return None

def fetch_market_info(society, locality, city="Pune"):
    """
    Enhanced Free Scraper for Price and BHK
    """
    query = f"{society} {locality} {city} price configurations 1bhk 2bhk 3bhk 4bhk"
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        # Using a slightly different search endpoint for better snippets
        res = requests.get(f"https://html.duckduckgo.com/html/?q={query}", headers=headers, timeout=10)
        text = res.text.lower()
        
        # 1. Advanced BHK Extraction (Look for 1 to 5 BHK)
        configs_found = sorted(list(set(re.findall(r'([1-5]\s?bhk)', text))))
        final_config = ", ".join(configs_found).upper() if configs_found else "2, 3 BHK (Check Site)"
        
        # 2. Advanced Price Extraction (Look for specific Indian Currency formats)
        # Matches: 1.5 Cr, 85 Lakh, 1.25 Crore, etc.
        price_patterns = [
            r'(\d+\.?\d*\s?cr(?:ore)?)', 
            r'(\d+\.?\d*\s?lakh(?:s)?)',
            r'(\d+\.?\d*\s?lac(?:s)?)',
            r'(?:rs\.?|₹)\s?(\d+\.?\d*\s?(?:cr|lakh|lac|l))'
        ]
        
        prices = []
        for pattern in price_patterns:
            found = re.findall(pattern, text)
            if found: prices.extend(found)
        
        # Clean and pick the most relevant price range
        if prices:
            unique_prices = sorted(list(set(prices)))
            final_price = " - ".join(unique_prices[:2]) # Shows a range if two prices found
        else:
            final_price = "Price on Request"
            
        return final_price, final_config
    except:
        return "N/A", "N/A"

# --- STREAMLIT UI ---
with st.sidebar:
    st.header("Settings")
    proj_link = st.text_input("Project Google Maps Link")
    run_btn = st.button("Start Analysis")

uploaded_file = st.file_uploader("Upload Society Excel/CSV", type=['csv', 'xlsx'])

if uploaded_file and proj_link and run_btn:
    df = pd.read_csv(uploaded_file) if uploaded_file.name.endswith('.csv') else pd.read_excel(uploaded_file)
    proj_coords = extract_coords_from_url(proj_link)
    
    if not proj_coords:
        st.error("Could not read link coordinates.")
    else:
        results = []
        progress = st.progress(0)
        status = st.empty()
        
        for idx, row in df.iterrows():
            soc, loc = str(row.get('society', '')), str(row.get('locality', ''))
            status.text(f"Analyzing: {soc}...")
            
            # Geocoding & Distance
            coords, _ = get_soc_coordinates(soc, loc)
            dist_val = "Not Found"
            if coords:
                try:
                    url = f"http://router.project-osrm.org/route/v1/driving/{proj_coords[1]},{proj_coords[0]};{coords[1]},{coords[0]}?overview=false"
                    d_res = requests.get(url).json()
                    dist_val = f"{round(d_res['routes'][0]['distance']/1000, 2)} km"
                except: pass
            
            # Market Data
            price, config = fetch_market_info(soc, loc)
            
            results.append({
                "Distance from project": dist_val,
                "Ticket Size": price,
                "Configurations": config
            })
            
            progress.progress((idx + 1) / len(df))
            time.sleep(0.5) # Balanced delay
            
        final_df = pd.concat([df, pd.DataFrame(results)], axis=1)
        st.dataframe(final_df)
        st.download_button("Download Report", final_df.to_csv(index=False), "report.csv")
