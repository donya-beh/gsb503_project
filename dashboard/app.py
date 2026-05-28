import streamlit as st
from utils import load_data, load_sdk

st.set_page_config(
    page_title="NVIDIA Developer Analytics",
    layout="wide",
)

# Preload both datasets once at startup with progress feedback
if "data_loaded" not in st.session_state:
    st.markdown("## Loading NVIDIA Developer Analytics...")
    
    with st.spinner("Step 1/3: Connecting to S3 and downloading activity data (~2 GB, please wait)..."):
        load_data()
    
    with st.spinner("Step 2/3: Downloading SDK data..."):
        load_sdk()

    with st.spinner("Step 3/3: Finalizing..."):
        import time; time.sleep(0.3)

    st.session_state["data_loaded"] = True
    st.rerun()

pg = st.navigation([
    st.Page("pages/group_trends.py",        title="Full Group Trends",             icon="📈"),
    st.Page("pages/single_devs.py",         title="Single Developer Profiles",     icon="👤"),
    st.Page("pages/org_analysis.py",        title="Organization Profiles",         icon="🏢"),
    st.Page("pages/geographic_analysis.py", title="Geographic Profiles",           icon="🌍"),
])

pg.run()