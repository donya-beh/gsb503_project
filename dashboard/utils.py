"""
utils.py — shared data loading for the NVIDIA Developer Analytics dashboard.
All pages import load_data() and load_sdk() from here.
Data is queried from Snowflake.
"""

import streamlit as st
import pandas as pd
import snowflake.connector

# ── Cluster colors ────────────────────────────────────────────────────────────
CLUSTER_COLORS = {
    "Technical": "#4a90d9",
    "Passive":   "#a8c4e0",
    "Casual":    "#b8d98d",
    "Attendee":  "#e8a87c",
    "Unicorn":   "#76b900",
}

CLUSTER_NAME_MAP = {
    1: "Technical",
    2: "Passive",
    3: "Casual",
    4: "Attendee",
    5: "Unicorn",
}

ACCENT_COLORS = ["#76b900", "#00c2ff", "#ff6b35", "#b39ddb", "#ffca28", "#ef9a9a"]

POPULATION = {
    'Myanmar': 54410000, 'Lithuania': 2794000, 'Algeria': 44617000,
    "Cote D'Ivoire": 27478000, 'Finland': 5541000, 'Azerbaijan': 10139000,
    'Ukraine': 43531000, 'Romania': 19237000, 'Zambia': 19473000,
    'Sierra Leone': 8141000, 'The Netherlands': 17618000,
    "Lao People's Democratic Republic": 7379000, 'Mongolia': 3347000,
    'Botswana': 2589000, 'Poland': 37958000, 'Armenia': 2963000,
    'Palestine, State of': 5354000, 'Reunion': 906000, 'North Macedonia': 2083000,
    'Mexico': 130262000, 'French Polynesia': 280000, 'Estonia': 1331000,
    'British Virgin Islands': 30000, 'China': 1412000000, 'Austria': 9043000,
    'Russian Federation': 144713000, 'Iraq': 41179000, 'Andorra': 77000,
    'Croatia': 3899000, 'Liechtenstein': 38000, 'El Salvador': 6486000,
    'Nepal': 29192000, 'Czechia': 10701000, 'Portugal': 10290000,
    'Somalia': 17065000, 'Guernsey': 63000, 'Ghana': 32395000,
    'Hong Kong': 7413000, 'Brunei': 437000, 'Cape Verde': 556000,
    'Taiwan': 23571000, 'Bangladesh': 166303000, 'Lebanon': 6769000,
    'Paraguay': 7356000, 'Chile': 19116000, 'Indonesia': 273524000,
    'Libya': 6958000, 'Australia': 25921000, 'Saudi Arabia': 35013000,
    'Pakistan': 220892000, 'Canada': 38246000, 'Malawi': 19647000,
    'Uzbekistan': 34915000, 'United Kingdom': 67326000, 'Malta': 514000,
    'Yemen': 33697000, 'Kazakhstan': 18754000, 'Brazil': 214326000,
    'Belarus': 9442000, 'Honduras': 10278000, 'Moldova, Republic of': 2617000,
    'Guatemala': 17110000, 'Germany': 83784000, 'Guinea': 13133000,
    'Spain': 47351000, 'Macao': 658000, 'Iran': 85029000,
    'Ecuador': 17889000, 'Bahrain': 1748000, 'Virgin Islands, U.S.': 100000,
    'Israel': 9217000, 'Mauritania': 4615000, 'Turkey': 84339000,
    'Venezuela': 28436000, 'Montenegro': 621000, 'South Africa': 59309000,
    'Costa Rica': 5094000, 'Guam': 168000, 'Korea, Republic of': 51745000,
    'Tanzania': 61498000, 'United States': 331000000, 'Serbia': 6805000,
    'Albania': 2838000, 'Malaysia': 32366000, 'India': 1380004000,
    'Jamaica': 2961000, 'United Arab Emirates': 9991000, 'Cameroon': 27224000,
    'Togo': 8479000, 'Rwanda': 13276000, 'France': 67391000,
    'Switzerland': 8654000, 'Madagascar': 27691000, 'Tunisia': 11819000,
    'Greece': 10724000, 'Chad': 16426000, 'Monaco': 39000,
    'Bosnia and Herzegovina': 3281000, 'Jordan': 10269000, 'Ethiopia': 117876000,
    'Singapore': 5686000, 'Burkina Faso': 21498000, 'Italy': 60461000,
    'Cuba': 11333000, 'Maldives': 541000, 'Faroe Islands': 49000,
    'Sweden': 10353000, 'Bulgaria': 6520000, 'Philippines': 109581000,
    'Fiji': 896000, 'Georgia': 3989000, 'Slovakia': 5460000,
    'Curaçao': 155000, 'Latvia': 1842000, 'Peru': 32972000,
    'Mauritius': 1272000, 'Mozambique': 32163000, 'Dominican Republic': 10847000,
    'Qatar': 2881000, 'Belize': 397000, 'Thailand': 69800000,
    'Egypt': 102334000, 'Benin': 12123000, 'Japan': 125681000,
    'Saint Vincent and the Grenadines': 111000, 'Zimbabwe': 14863000,
    'Senegal': 17196000, 'New Zealand': 5084000, 'Oman': 4521000,
    'Sri Lanka': 21413000, 'Bhutan': 772000, 'Hungary': 9660000,
    'Kenya': 54986000, 'Cyprus': 1207000, 'Slovenia': 2079000,
    'Mali': 22414000, 'Guadeloupe': 395000, 'Uganda': 47124000,
    'Ireland': 4995000, 'Kuwait': 4271000, 'Belgium': 11590000,
    'Morocco': 37345000, 'Cambodia': 16718000, 'Nicaragua': 6625000,
    'Kyrgyzstan': 6591000, 'Trinidad and Tobago': 1399000, 'Norway': 5421000,
    'Bolivia': 11673000, 'Syria': 21324000, 'Colombia': 51875000,
    'Isle of Man': 85000, 'Uruguay': 3474000, 'Nigeria': 206140000,
    'Jersey': 107000, 'Argentina': 45376000, 'Puerto Rico': 3286000,
    'Luxembourg': 634000, 'Viet Nam': 97339000, 'Iceland': 341000,
    'Afghanistan': 38929000, 'Denmark': 5792000,
    'Congo, Democratic Republic of the': 89561000, 'Tajikistan': 9537000,
    'Angola': 32866000, 'Greenland': 56000, 'Vatican City': 800,
    'Cayman Islands': 65000, 'Bermuda': 64000, 'Aruba': 107000,
    'Martinique': 375000, 'French Guiana': 298000, 'Panama': 4351000,
    'Sudan': 43849000, 'Lesotho': 2142000, 'Guyana': 787000,
    'Haiti': 11403000, 'Gabon': 2226000, 'Eritrea': 3497000,
    'Mayotte': 279000, 'Eswatini': 1160000, 'Bahamas': 393000,
    'Antarctica': 1000, 'Saint Lucia': 183000, 'Djibouti': 988000,
    'Turkmenistan': 6031000, 'Suriname': 587000, 'Seychelles': 98000,
    'Gibraltar': 33000, 'Saint-Martin (French part)': 38000,
    'Barbados': 287000, 'Congo': 5835000, 'Niger': 24207000,
    'Grenada': 113000, 'Burundi': 11891000, 'Saint Kitts and Nevis': 53000,
    'New Caledonia': 271000, 'Gambia': 2418000, 'San Marino': 34000,
    'Antigua and Barbuda': 97000, 'Northern Mariana Islands': 57000,
    'Turks and Caicos Islands': 38000, 'Papua New Guinea': 9119000,
    'Sint Maarten': 42000, "Korea, Democratic People's Republic of": 25779000,
    'Timor-Leste': 1318000, 'Anguilla': 15000, 'Wallis and Futuna': 11000,
    'South Sudan': 11194000, 'Liberia': 5058000, 'Vanuatu': 307000,
}


def _get_connection():
    return snowflake.connector.connect(
        account=st.secrets["snowflake"]["account"],
        user=st.secrets["snowflake"]["user"],
        password=st.secrets["snowflake"]["password"],
        warehouse=st.secrets["snowflake"]["warehouse"],
        database=st.secrets["snowflake"]["database"],
        schema=st.secrets["snowflake"]["schema"],
    )


def _query(sql: str) -> pd.DataFrame:
    conn = _get_connection()
    try:
        df = pd.read_sql(sql, conn)
        df.columns = [c.lower() for c in df.columns]
        return df
    finally:
        conn.close()


@st.cache_data
def load_data() -> pd.DataFrame:
    """Load all activity data from Snowflake."""
    df = _query("SELECT * FROM activities")

    df["cluster_name"] = df["cluster"].map(CLUSTER_NAME_MAP)
    df["activity_date"] = pd.to_datetime(df["activity_date"], utc=True, errors="coerce")
    df["first_activity_date"] = pd.to_datetime(df["first_activity_date"], utc=True, errors="coerce")

    return df


@st.cache_data
def load_data_for_country(country: str) -> pd.DataFrame:
    """Load activity data filtered by country."""
    df = _query(f"SELECT * FROM activities WHERE country = '{country}'")
    df["cluster_name"] = df["cluster"].map(CLUSTER_NAME_MAP)
    df["activity_date"] = pd.to_datetime(df["activity_date"], utc=True, errors="coerce")
    df["first_activity_date"] = pd.to_datetime(df["first_activity_date"], utc=True, errors="coerce")
    return df


@st.cache_data
def load_data_for_org(org: str) -> pd.DataFrame:
    """Load activity data filtered by organization."""
    df = _query(f"SELECT * FROM activities WHERE normalized_account_name = $${org}$$")
    df["cluster_name"] = df["cluster"].map(CLUSTER_NAME_MAP)
    df["activity_date"] = pd.to_datetime(df["activity_date"], utc=True, errors="coerce")
    df["first_activity_date"] = pd.to_datetime(df["first_activity_date"], utc=True, errors="coerce")
    return df


@st.cache_data
def load_data_for_developer(developer_id: str) -> pd.DataFrame:
    """Load activity data for a single developer."""
    df = _query(f"SELECT * FROM activities WHERE developer_id = '{developer_id}'")
    df["cluster_name"] = df["cluster"].map(CLUSTER_NAME_MAP)
    df["activity_date"] = pd.to_datetime(df["activity_date"], utc=True, errors="coerce")
    df["first_activity_date"] = pd.to_datetime(df["first_activity_date"], utc=True, errors="coerce")
    return df


@st.cache_data
def load_data_for_cluster(cluster: str) -> pd.DataFrame:
    """Load activity data filtered by cluster name."""
    cluster_num = {v: k for k, v in CLUSTER_NAME_MAP.items()}.get(cluster)
    if cluster_num is None:
        return load_data()
    df = _query(f"SELECT * FROM activities WHERE cluster = {cluster_num}")
    df["cluster_name"] = df["cluster"].map(CLUSTER_NAME_MAP)
    df["activity_date"] = pd.to_datetime(df["activity_date"], utc=True, errors="coerce")
    df["first_activity_date"] = pd.to_datetime(df["first_activity_date"], utc=True, errors="coerce")
    return df


@st.cache_data
def load_summary() -> pd.DataFrame:
    """Load lightweight summary data — all developers, key columns only."""
    df = _query("""
        SELECT developer_id, activity, activity_date, activity_score,
               country, cluster, normalized_account_name, cluster_name
        FROM activities
    """)
    df["cluster_name"] = df["cluster"].map(CLUSTER_NAME_MAP)
    df["activity_date"] = pd.to_datetime(df["activity_date"], utc=True, errors="coerce")
    return df


@st.cache_data
def load_clean_orgs() -> pd.DataFrame:
    """Load data with unclassified org names filtered out."""
    df = _query("""
        SELECT * FROM activities
        WHERE normalized_account_name != 'Not Normalized'
        AND normalized_account_name != 'Unclassified - Invalid'
    """)
    df["cluster_name"] = df["cluster"].map(CLUSTER_NAME_MAP)
    df["activity_date"] = pd.to_datetime(df["activity_date"], utc=True, errors="coerce")
    df["first_activity_date"] = pd.to_datetime(df["first_activity_date"], utc=True, errors="coerce")
    return df


@st.cache_data
def load_sdk() -> pd.DataFrame:
    """Load SDK downloads from Snowflake."""
    sdk = _query("SELECT * FROM sdk_downloads")
    sdk["downloaddate"] = pd.to_datetime(sdk["downloaddate"], errors="coerce")
    sdk["downloadcount"] = pd.to_numeric(sdk["downloadcount"], errors="coerce").fillna(1)
    sdk["population"] = sdk["country"].map(POPULATION)
    sdk["downloads_per_100k"] = (sdk["downloadcount"] / sdk["population"] * 100000).round(2)
    return sdk


@st.cache_data
def load_sdk_for_country(country: str) -> pd.DataFrame:
    """Load SDK data for a specific country."""
    sdk = _query(f"SELECT * FROM sdk_downloads WHERE country = '{country}'")
    sdk["downloaddate"] = pd.to_datetime(sdk["downloaddate"], errors="coerce")
    sdk["downloadcount"] = pd.to_numeric(sdk["downloadcount"], errors="coerce").fillna(1)
    sdk["population"] = sdk["country"].map(POPULATION)
    sdk["downloads_per_100k"] = (sdk["downloadcount"] / sdk["population"] * 100000).round(2)
    return sdk


@st.cache_data
def get_all_countries() -> list:
    """Get list of all countries sorted by developer count."""
    df = _query("""
        SELECT country, COUNT(DISTINCT developer_id) as dev_count
        FROM activities
        GROUP BY country
        ORDER BY dev_count DESC
    """)
    return df["country"].tolist()


@st.cache_data
def get_all_orgs() -> list:
    """Get list of all valid organizations sorted by developer count."""
    df = _query("""
        SELECT normalized_account_name, COUNT(DISTINCT developer_id) as dev_count
        FROM activities
        WHERE normalized_account_name != 'Not Normalized'
        AND normalized_account_name != 'Unclassified - Invalid'
        GROUP BY normalized_account_name
        ORDER BY dev_count DESC
    """)
    return df["normalized_account_name"].tolist()


@st.cache_data
def get_all_developers() -> list:
    """Get list of all developer IDs."""
    df = _query("SELECT DISTINCT developer_id FROM activities ORDER BY developer_id")
    return df["developer_id"].tolist()