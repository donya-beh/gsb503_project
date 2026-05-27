"""
utils.py — shared data loading for the NVIDIA Developer Analytics dashboard.
All pages import load_data() and load_sdk() from here.
Run Parquet_Files.ipynb first to generate dashboard_ready.parquet and sdk_ready.parquet.
"""

import streamlit as st
import pandas as pd

# ── Country code → name mapping (used by load_sdk) ────────────────────────────
COUNTRY_CODE_MAP = {
    'MM': 'Myanmar', 'LT': 'Lithuania', 'DZ': 'Algeria', 'CI': "Cote D'Ivoire",
    'FI': 'Finland', 'AZ': 'Azerbaijan', 'UA': 'Ukraine', 'RO': 'Romania',
    'ZM': 'Zambia', 'SL': 'Sierra Leone', 'NL': 'The Netherlands',
    'LA': "Lao People's Democratic Republic", 'MN': 'Mongolia', 'BW': 'Botswana',
    'PL': 'Poland', 'AM': 'Armenia', 'PS': 'Palestine, State of', 'RE': 'Reunion',
    'MK': 'North Macedonia', 'MX': 'Mexico', 'PF': 'French Polynesia', 'EE': 'Estonia',
    'VG': 'British Virgin Islands', 'CN': 'China', 'AT': 'Austria',
    'RU': 'Russian Federation', 'IQ': 'Iraq', 'AD': 'Andorra', 'HR': 'Croatia',
    'LI': 'Liechtenstein', 'SV': 'El Salvador', 'NP': 'Nepal', 'CZ': 'Czechia',
    'PT': 'Portugal', 'SO': 'Somalia', 'GG': 'Guernsey', 'GH': 'Ghana',
    'HK': 'Hong Kong', 'BN': 'Brunei', 'CV': 'Cape Verde', 'TW': 'Taiwan',
    'BD': 'Bangladesh', 'LB': 'Lebanon', 'PY': 'Paraguay', 'CL': 'Chile',
    'ID': 'Indonesia', 'LY': 'Libya', 'AU': 'Australia', 'SA': 'Saudi Arabia',
    'PK': 'Pakistan', 'CA': 'Canada', 'MW': 'Malawi', 'UZ': 'Uzbekistan',
    'GB': 'United Kingdom', 'MT': 'Malta', 'YE': 'Yemen', 'KZ': 'Kazakhstan',
    'BR': 'Brazil', 'BY': 'Belarus', 'HN': 'Honduras', 'MD': 'Moldova, Republic of',
    'GT': 'Guatemala', 'DE': 'Germany', 'GN': 'Guinea', 'ES': 'Spain', 'MO': 'Macao',
    'IR': 'Iran', 'EC': 'Ecuador', 'BH': 'Bahrain', 'VI': 'Virgin Islands, U.S.',
    'IL': 'Israel', 'MR': 'Mauritania', 'TR': 'Turkey', 'VE': 'Venezuela',
    'ME': 'Montenegro', 'ZA': 'South Africa', 'CR': 'Costa Rica', 'GU': 'Guam',
    'KR': 'Korea, Republic of', 'TZ': 'Tanzania', 'US': 'United States',
    'RS': 'Serbia', 'AL': 'Albania', 'MY': 'Malaysia', 'IN': 'India',
    'JM': 'Jamaica', 'AE': 'United Arab Emirates', 'CM': 'Cameroon', 'TG': 'Togo',
    'RW': 'Rwanda', 'FR': 'France', 'CH': 'Switzerland', 'MG': 'Madagascar',
    'TN': 'Tunisia', 'GR': 'Greece', 'TD': 'Chad', 'MC': 'Monaco',
    'BA': 'Bosnia and Herzegovina', 'JO': 'Jordan', 'ET': 'Ethiopia',
    'SG': 'Singapore', 'BF': 'Burkina Faso', 'IT': 'Italy', 'CU': 'Cuba',
    'MV': 'Maldives', 'FO': 'Faroe Islands', 'SE': 'Sweden', 'BG': 'Bulgaria',
    'PH': 'Philippines', 'FJ': 'Fiji', 'GE': 'Georgia', 'SK': 'Slovakia',
    'CW': 'Curacao', 'LV': 'Latvia', 'PE': 'Peru', 'MU': 'Mauritius',
    'MZ': 'Mozambique', 'DO': 'Dominican Republic', 'QA': 'Qatar', 'BZ': 'Belize',
    'TH': 'Thailand', 'EG': 'Egypt', 'BJ': 'Benin', 'JP': 'Japan',
    'VC': 'Saint Vincent and the Grenadines', 'ZW': 'Zimbabwe', 'SN': 'Senegal',
    'NZ': 'New Zealand', 'OM': 'Oman', 'LK': 'Sri Lanka', 'BT': 'Bhutan',
    'HU': 'Hungary', 'KE': 'Kenya', 'CY': 'Cyprus', 'SI': 'Slovenia',
    'ML': 'Mali', 'GP': 'Guadeloupe', 'UG': 'Uganda', 'IE': 'Ireland',
    'KW': 'Kuwait', 'BE': 'Belgium', 'MA': 'Morocco', 'KH': 'Cambodia',
    'NI': 'Nicaragua', 'KG': 'Kyrgyzstan', 'TT': 'Trinidad and Tobago',
    'NO': 'Norway', 'BO': 'Bolivia', 'SY': 'Syria', 'CO': 'Colombia',
    'IM': 'Isle of Man', 'UY': 'Uruguay', 'NG': 'Nigeria', 'JE': 'Jersey',
    'AR': 'Argentina', 'PR': 'Puerto Rico', 'LU': 'Luxembourg', 'VN': 'Viet Nam',
    'IS': 'Iceland', 'AF': 'Afghanistan', 'DK': 'Denmark',
    'CD': 'Congo, Democratic Republic of the', 'TJ': 'Tajikistan', 'AO': 'Angola',
    'GL': 'Greenland', 'VA': 'Vatican City', 'KY': 'Cayman Islands',
    'BM': 'Bermuda', 'AW': 'Aruba', 'MQ': 'Martinique', 'GF': 'French Guiana',
    'PA': 'Panama', 'SD': 'Sudan', 'LS': 'Lesotho', 'GY': 'Guyana',
    'HT': 'Haiti', 'GA': 'Gabon', 'ER': 'Eritrea', 'YT': 'Mayotte',
    'SZ': 'Eswatini', 'BS': 'Bahamas', 'AQ': 'Antarctica', 'LC': 'Saint Lucia',
    'DJ': 'Djibouti', 'TM': 'Turkmenistan', 'SR': 'Suriname', 'SC': 'Seychelles',
    'GI': 'Gibraltar', 'MF': 'Saint-Martin (French part)', 'BB': 'Barbados',
    'CG': 'Congo', 'NE': 'Niger', 'GD': 'Grenada', 'BI': 'Burundi',
    'KN': 'Saint Kitts and Nevis', 'NC': 'New Caledonia', 'GM': 'Gambia',
    'SM': 'San Marino', 'AG': 'Antigua and Barbuda', 'MP': 'Northern Mariana Islands',
    'TC': 'Turks and Caicos Islands', 'PG': 'Papua New Guinea', 'SX': 'Sint Maarten',
    'KP': "Korea, Democratic People's Republic of", 'TL': 'Timor-Leste',
    'AI': 'Anguilla', 'WF': 'Wallis and Futuna', 'SS': 'South Sudan',
    'LR': 'Liberia', 'VU': 'Vanuatu',
}

CLUSTER_COLORS = {
    "Technical": "#4a90d9",
    "Passive":   "#a8c4e0",
    "Casual":    "#b8d98d",
    "Attendee":  "#e8a87c",
    "Unicorn":   "#76b900",
}

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

CLUSTER_COLORS = {
    "Technical": "#4a90d9",
    "Passive":   "#a8c4e0",
    "Casual":    "#b8d98d",
    "Attendee":  "#e8a87c",
    "Unicorn":   "#76b900",
}


@st.cache_data
def load_data() -> pd.DataFrame:
    """
    Load the pre-cleaned dashboard_ready.parquet produced by Parquet_Files.ipynb.
    """
    df = pd.read_parquet("dashboard_ready.parquet")

    # ── Cluster name mapping ──────────────────────────────────────────────────
    CLUSTER_NAME_MAP = {
        1: "Technical",
        2: "Passive",
        3: "Casual",
        4: "Attendee",
        5: "Unicorn",
    }
    df["cluster_name"] = df["cluster"].map(CLUSTER_NAME_MAP)

    return df


@st.cache_data
def load_clean_orgs() -> pd.DataFrame:
    """Returns load_data() with unclassified org names filtered out."""
    df = load_data()
    return df[
        (df["normalized_account_name"] != "Not Normalized") &
        (df["normalized_account_name"] != "Unclassified - Invalid")
    ]


@st.cache_data
def load_sdk() -> pd.DataFrame:
    """
    Load the pre-cleaned sdk_ready.parquet produced by Parquet_Files.ipynb.
    Already has country names mapped and downloads_per_100k computed.
    """
    return pd.read_parquet("sdk_ready.parquet")