import streamlit as st
import pandas as pd
import google.generativeai as genai
import requests
import re
import json
import time

# --- SETUP ---
st.set_page_config(page_title="Real Estate AI Dashboard", layout="wide")

st.title("🏙️ Real Estate Proximity & Market Dashboard")
st.markdown("Automating your Gemini chat logic for the entire society list.")

# --- HELPER FUNCTIONS ---

def extract_coords_from_url(url):
    """Extracts Latitude and Longitude from a Google Maps URL."""
    try:
        if "goo.gl" in url or "maps.app.goo.gl" in url:
            response = requests.get(url, allow_redirects=True, timeout=10)
            url = response.url
            
        # Regex to find @lat,long
        match = re.search(r'@([-.\d]+),([-.\d]+)', url)
        if match:
            return f"{match.group(1)}, {match.group(2)}"
        
        # Fallback for desktop format
        match_alt = re.search(r'!3d([-.\d]+)!4d([-.\d]+)', url)
        if match_alt:
            return f"{match_alt.group(1)}, {match_alt.group(2)}"
    except:
        pass
    return None

def get_gemini_analysis(society, locality, project_location, api_key):
    """Uses Gemini 1.5 Flash to replicate your specific chat logic."""
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-1.5-flash')
    
    # This prompt mimics your successful chat logic
    prompt = f"""
    My project is located at these coordinates/address: {project_location}.
    For the society "{society}" in "{locality}, Pune", provide:
    1. Distance from project: Calculate the CAR ROUTE driving distance in KM.
    2. Ticket Size: Current market price range (e.g., 80 L - 1.2 Cr).
    3. Configurations: List all available (check for 1, 2, 3, 4, and 5 BHK).

    Return ONLY a JSON object:
    {{"distance": "1.5 km", "price": "90 L - 1.4 Cr", "config": "2 BHK, 3 BHK, 4 BHK"}}
    """
    
    try:
        response = model.generate_content(prompt)
        # Clean the response to ensure it's valid JSON
        data_str = re.search(r'\{.*\}', response.text, re.DOTALL).group()
        return json.loads(data_str)
    except:
        return {"distance": "N/A", "price": "Check Online", "config": "1-5 BHK"}

# --- SIDEBAR ---
with st.sidebar:
    st.header("1. Setup")
    api_key = st.text_input("Gemini API Key", value="AIzaSyA4i_sX4N1RgOIJyNkN3cH2n1iXE-e1DU4", type="password")
    project_link = st.text_input("Project Google Maps Link", placeholder="Paste link here...")
    
    st.divider()
    run_btn = st.button("🚀 Analyze All Societies")

# --- MAIN APP ---
uploaded_file = st.file_uploader("Upload 'Book 5.xlsx'", type=['csv', 'xlsx'])

if uploaded_file and project_link and run_btn:
    # Load file
    df = pd.read_csv(uploaded_file) if uploaded_file.name.endswith('.csv') else pd.read_excel(uploaded_file)
    
    # 1. Extract Project Coordinates
    with st.spinner("Extracting project location..."):
        proj_location = extract_coords_from_url(project_link)
        if not proj_location:
            # If coordinates fail, we use the link text itself as a reference
            proj_location = project_link

    st.info(f"Analyzing {len(df)} societies relative to your project link...")
    
    results = []
    progress_bar = st.progress(0)
    status_text = st.empty()

    for idx, row in df.iterrows():
        soc = str(row['society'])
        loc = str(row['locality'])
        
        status_text.text(f"Processing {idx+1}/{len(df)}: {soc}")
        
        # Use Gemini AI (trained on your logic)
        ai_data = get_gemini_analysis(soc, loc, proj_location, api_key)
        
        results.append({
            "Distance from project": ai_data.get("distance"),
            "Ticket Size": ai_data.get("price"),
            "Configurations": ai_data.get("config")
        })
        
        # Update progress
        progress_bar.progress((idx + 1) / len(df))
        time.sleep(0.5) # Sleep to avoid API rate limits

    # Merge and Display
    final_df = pd.concat([df, pd.DataFrame(results)], axis=1)
    st.success("✅ Dashboard Updated!")
    st.dataframe(final_df)
    
    # Download
    csv = final_df.to_csv(index=False).encode('utf-8')
    st.download_button("Download Processed Excel", csv, "property_dashboard.csv", "text/csv")
