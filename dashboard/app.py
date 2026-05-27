import streamlit as st
 
st.set_page_config(
    page_title="NVIDIA Developer Analytics",
    layout="wide",
)
 
pg = st.navigation([
    st.Page("pages/single_devs.py",         title="Single Developer Profiles",    icon="👤"),
    st.Page("pages/org_analysis.py",        title="Organization Profiles",        icon="🏢"),
    st.Page("pages/geographic_analysis.py", title="Geographic Profiles",          icon="🌍"),
])
 
pg.run()
 