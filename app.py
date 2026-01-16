import streamlit as st
import pandas as pd
import re
import io
import time
from openpyxl.styles import Alignment, PatternFill, Border, Side

# Selenium Imports
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager

# --- NEW: ADVANCED PROJECT DATA SEARCH ---
def fetch_project_metadata_live(project_name):
    """
    Powerful search-based extraction. It looks for numbers near keywords 
    like 'floors', 'towers', and 'possession' across search snippets.
    """
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36")
    
    driver = None
    try:
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
        
        # Searching via Bing (Less bot-protection for Snippet Reading)
        search_query = f"{project_name} Pune magicbricks housing possession towers floors units"
        driver.get(f"https://www.bing.com/search?q={search_query.replace(' ', '+')}")
        time.sleep(4)
        
        # Capture the entire search result text
        raw_text = driver.find_element(By.TAG_NAME, "body").text.lower()
        driver.quit()

        # --- DATA PATTERN RECOGNITION ---
        
        # 1. Amenities (Counting common words or looking for "XX+ amenities")
        amn_match = re.search(r'(\d+)\s*\+?\s*amenities', raw_text)
        amenities = f"{amn_match.group(1)}+" if amn_match else "30+"
        
        # 2. Tower Count
        t_match = re.search(r'(\d+)\s*(?:towers?|wings?|buildings?)', raw_text)
        towers = t_match.group(1) if t_match else "N/A"
        
        # 3. Floor Count (Looking for G+X, X floors, X storeys)
        f_match = re.search(r'(?:g|p|b)\s*\+\s*(\d+)', raw_text)
        if not f_match:
            f_match = re.search(r'(\d+)\s*(?:floors?|storeys?|levels?)', raw_text)
        floors = f"G+{f_match.group(1)}" if f_match else "N/A"
        
        # 4. Total Units
        u_match = re.search(r'(\d{2,4})\s*(?:units?|apartments?|flats?|homes?)', raw_text)
        units = u_match.group(1) if u_match else "N/A"
        
        # 5. Possession Date (Regex for Month Year)
        p_match = re.search(r'(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s*,?\s*(\d{4})', raw_text)
        possession = f"{p_match.group(1).capitalize()}, {p_match.group(2)}" if p_match else "N/A"

        return [amenities, towers, floors, units, possession]
    except:
        if driver: driver.quit()
        return ["N/A"] * 5

# --- AREA & BHK LOGIC (UNCHANGED) ---
def extract_area_logic(text):
    if pd.isna(text) or text == "": return 0.0
    text = " ".join(str(text).split()).replace(' ,', ',').replace(', ', ',')
    m_unit = r'(?:चौ\.?\s*मी\.?|चौरस\s*मी[टत]र|sq\.?\s*m(?:tr)?\.?)'
    m_segments = re.split(f'(\d+\.?\d*)\s*{m_unit}', text, flags=re.IGNORECASE)
    m_vals = [float(m_segments[i]) for i in range(1, len(m_segments), 2) 
              if 0 < float(m_segments[i]) < 500 and not any(w in m_segments[i-1].lower() for w in ["पार्किंग", "पार्कींग", "parking"])]
    return round(sum(m_vals), 3) if m_vals else 0.0

def determine_config(area, t1, t2, t3):
    if area == 0: return "N/A"
    return "1 BHK" if area < t1 else "2 BHK" if area < t2 else "3 BHK" if area < t3 else "4 BHK"

# --- FORMATTING (GLOBAL CENTER ALIGN & BLACK BORDERS) ---
def apply_excel_formatting(df, writer, sheet_name, is_summary=True, show_extra=False):
    df.to_excel(writer, sheet_name=sheet_name, index=False)
    worksheet = writer.sheets[sheet_name]
    center = Alignment(horizontal='center', vertical='center')
    border = Border(left=Side(style='thin'), right=Side(style='thin'), top=Side(style='thin'), bottom=Side(style='thin'))
    colors = ["A2D2FF", "FFD6A5", "CAFFBF", "FDFFB6", "FFADAD", "BDB2FF", "9BF6FF"]

    # Global Alignment
    for r in range(1, worksheet.max_row + 1):
        for c in range(1, worksheet.max_column + 1):
            cell = worksheet.cell(row=r, column=c)
            cell.alignment = center
            if is_summary: cell.border = border

    if is_summary:
        color_idx, start_prop, start_cfg = 0, 2, 2
        for i in range(2, len(df) + 2):
            curr_p, next_p = df.iloc[i-2, 0], df.iloc[i-1, 0] if i-1 < len(df) else None
            fill = PatternFill(start_color=colors[color_idx % len(colors)], end_color=colors[color_idx % len(colors)], fill_type="solid")
            for col in range(1, len(df.columns) + 1): worksheet.cell(row=i, column=col).fill = fill
            
            if curr_p != next_p:
                m_cols = [1]
                if show_extra: m_cols.extend(range(len(df.columns)-4, len(df.columns)+1))
                for c_idx in m_cols:
                    if i > start_prop:
                        worksheet.merge_cells(start_row=start_prop, start_column=c_idx, end_row=i, end_column=c_idx)
                color_idx, start_prop = color_idx + 1, i + 1
            
            if [df.iloc[i-2,0], df.iloc[i-2,1]] != ([df.iloc[i-1,0], df.iloc[i-1,1]] if i-1 < len(df) else None):
                if i > start_cfg: worksheet.merge_cells(start_row=start_cfg, start_column=2, end_row=i, end_column=2)
                start_cfg = i + 1

# --- STREAMLIT UI ---
st.set_page_config(page_title="Property Analytics Pro", layout="wide")
st.title("🏠 Automated Property Analyst (Live Web Search)")

st.sidebar.header("Settings")
loading = st.sidebar.number_input("Loading Factor", value=1.35)
t1 = st.sidebar.number_input("1 BHK <", value=600); t2 = st.sidebar.number_input("2 BHK <", value=850); t3 = st.sidebar.number_input("3 BHK <", value=1100)
show_extra = st.sidebar.checkbox("Fetch Project Details (Live Web Search)")

uploaded_file = st.file_uploader("Upload Raw Excel File", type="xlsx")

if uploaded_file:
    df = pd.read_excel(uploaded_file)
    clean_cols = {c.lower().strip(): c for c in df.columns}
    desc, cons, prop = clean_cols.get('property description'), clean_cols.get('consideration value'), clean_cols.get('property')
    
    if desc and cons and prop:
        with st.spinner('Calculating Area Statistics...'):
            df['Carpet Area (SQ.MT)'] = df[desc].apply(extract_area_logic)
            df['Carpet Area (SQ.FT)'] = (df['Carpet Area (SQ.MT)'] * 10.764).round(3)
            df['Saleable Area'] = (df['Carpet Area (SQ.FT)'] * loading).round(3)
            df['APR'] = df.apply(lambda r: round(r[cons]/r['Saleable Area'], 3) if r['Saleable Area'] > 0 else 0, axis=1)
            df['Configuration'] = df['Carpet Area (SQ.FT)'].apply(lambda x: determine_config(x, t1, t2, t3))
        
        valid_df = df[df['Carpet Area (SQ.FT)'] > 0].sort_values([prop, 'Configuration', 'Carpet Area (SQ.FT)'])
        summary = valid_df.groupby([prop, 'Configuration', 'Carpet Area (SQ.FT)']).agg(
            Min_APR=('APR', 'min'), Max_APR=('APR', 'max'), Avg_APR=('APR', 'mean'),
            Median_APR=('APR', 'median'), Mode_APR=('APR', lambda x: x.mode().iloc[0] if not x.mode().empty else 0),
            Property_Count=(prop, 'count')
        ).reset_index()
        summary.columns = ['Property', 'Configuration', 'Carpet Area(SQ.FT)', 'Min. APR', 'Max APR', 'Average of APR', 'Median of APR', 'Mode of APR', 'Count of Property']

        if show_extra:
            unique_projects = summary['Property'].unique()
            project_map = {}
            for p in unique_projects:
                with st.spinner(f"Analyzing Web Data for: {p}..."):
                    project_map[p] = fetch_project_metadata_live(p)
            
            extra_cols = ["Amenities", "Towers", "Floors", "Total Units", "Possession"]
            for i, col in enumerate(extra_cols):
                summary[col] = summary['Property'].apply(lambda x: project_map[x][i])

        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='Raw Data', index=False)
            ws_raw = writer.sheets['Raw Data']
            for r in range(1, ws_raw.max_row+1):
                for c in range(1, ws_raw.max_column+1):
                    ws_raw.cell(row=r, column=c).alignment = Alignment(horizontal='center', vertical='center')
            
            apply_excel_formatting(summary, writer, 'Summary', show_extra=show_extra)
        
        st.success("Analysis Complete!")
        st.dataframe(summary)
        st.download_button("📥 Download Excel Report", data=output.getvalue(), file_name="Property_Summary_Report.xlsx")
