# ==================================================
# Imports
# ==================================================
import os
import requests
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ==================================================
# Konfiguration
# ==================================================
API_URL = 'https://fxdb.usb.ch/api/'

# ==================================================
# Datenexport aus REDCap
# ==================================================
def export_redcap_data(api_url):
    API_TOKEN = os.getenv("tok_op_gruppen")

    data = {
        'token': API_TOKEN,
        'content': 'record',
        'action': 'export',
        'format': 'json',
        'type': 'flat',
        'fields[0]': 'opdatum',
        'fields[1]': 'bereich',
        'fields[2]': 'hsm',
        'fields[3]': 'zugang',
        'fields[4]': 'max_dindo_calc_surv',
        'rawOrLabel': 'raw',
        'rawOrLabelHeaders': 'raw',
        'exportCheckboxLabel': 'false',
        'exportSurveyFields': 'false',
        'exportDataAccessGroups': 'false',
        'returnFormat': 'json'
    }

    try:
        r = requests.post(api_url, data=data, verify=False)
        r.raise_for_status()
        return pd.DataFrame(r.json())
    except requests.exceptions.RequestException as e:
        st.error(f"Fehler beim Export: {e}")
        return None

# ==================================================
# Datenaufbereitung
# ==================================================
def prepare_data(df):
    df = df.copy()
    df['opdatum'] = pd.to_datetime(df['opdatum'], errors='coerce')

    # -------- Bereich (Checkboxen) --------
    bereich_cols = [c for c in df.columns if c.startswith('bereich___')]
    if bereich_cols:
        mapping = {
            'bereich___1': 'Allgemein',
            'bereich___2': 'BMC',
            'bereich___3': 'Endokrin',
            'bereich___4': 'Chirurgische Onkologie/Sarkome',
            'bereich___5': 'Hernien',
            'bereich___6': 'Kolorektal',
            'bereich___7': 'Leber',
            'bereich___8': 'Pankreas',
            'bereich___9': 'Upper-GI'
        }

        def get_bereich(row):
            return ', '.join(
                label for col, label in mapping.items() if row.get(col) == '1'
            ) or 'Nicht angegeben'

        df['bereich'] = df.apply(get_bereich, axis=1)
        df = df.drop(columns=bereich_cols)

    # -------- Zugang --------
    zugang_mapping = {
        1: 'Offen',
        2: 'Laparoskopisch',
        3: 'roboter-assistiert',
        4: 'konvertiert',
        5: 'hybrid (2Höhlen-Eingriffe)'
    }

    df['zugang'] = pd.to_numeric(df['zugang'], errors='coerce')
    df['zugang'] = df['zugang'].map(zugang_mapping).fillna('Unbekannt')

    # -------- Zeitfelder --------
    df['jahr_opdatum'] = df['opdatum'].dt.year.astype('Int64')
    df['quartal_opdatum'] = (
        df['opdatum']
        .dt.to_period('Q')
        .astype(str)
        .str.replace(r'(\d{4})Q(\d)', r'Q\2-\1', regex=True)
    )
    df['quartal_sort'] = df['opdatum'].dt.year * 10 + df['opdatum'].dt.quarter
    df['max_dindo_calc_surv'] = pd.to_numeric(df['max_dindo_calc_surv'], errors='coerce')

    df = df.dropna(subset=['jahr_opdatum'])
    return df

# ==================================================
# Streamlit App
# ==================================================
st.title("OP-Gruppierung Dashboard")

df = export_redcap_data(API_URL)
if df is None:
    st.stop()

df = prepare_data(df)

# ==================================================
# Filter
# ==================================================
jahre = sorted(df['jahr_opdatum'].astype(int).unique())
jahr_filter = st.multiselect("Jahr auswählen:", jahre, default=jahre)

df_jahr = df[df['jahr_opdatum'].isin(jahr_filter)]

quartale = (
    df_jahr[['quartal_opdatum', 'quartal_sort']]
    .drop_duplicates()
    .sort_values('quartal_sort')['quartal_opdatum']
    .tolist()
)

quartal_filter = st.multiselect("Quartal auswählen:", quartale, default=quartale)

df_quartal = df_jahr[df_jahr['quartal_opdatum'].isin(quartal_filter)]

bereich_filter = st.selectbox(
    "Bereich auswählen:",
    ["Alle"] + sorted(df['bereich'].unique())
)

zugang_filter = st.selectbox(
    "Zugang auswählen:",
    ["Alle"] + sorted(df['zugang'].unique())
)

filtered_df = df_quartal.copy()

if bereich_filter != "Alle":
    filtered_df = filtered_df[filtered_df['bereich'] == bereich_filter]

if zugang_filter != "Alle":
    filtered_df = filtered_df[filtered_df['zugang'] == zugang_filter]

# ==================================================
# Kennzahlen
# ==================================================
st.subheader("Kennzahlen")
c1, c2, c3 = st.columns(3)

c1.metric("Gesamt Fälle", len(filtered_df))

avg_dindo = filtered_df['max_dindo_calc_surv'].mean()
c2.metric("Ø Clavien-Dindo", f"{avg_dindo:.2f}" if pd.notna(avg_dindo) else "N/A")

c3.metric("Bereiche", filtered_df['bereich'].nunique())

# ==================================================
# Visualisierungen
# ==================================================
st.subheader("Visualisierungen")
col1, col2 = st.columns(2)

# --- Farben pro Jahr ---
jahre_unique = sorted(filtered_df['jahr_opdatum'].unique())
farben = {
    jahr: f"rgb({50+jahr%5*40},{100+jahr%3*50},{150+jahr%4*30})"
    for jahr in jahre_unique
}

# --- Fallzahlen pro Jahr ---
jahr_counts_df = (
    filtered_df
    .groupby('jahr_opdatum')
    .size()
    .reset_index(name='count')
)

marker_colors = [farben[j] for j in jahr_counts_df['jahr_opdatum']]

fig_jahr = px.bar(
    jahr_counts_df,
    x='jahr_opdatum',
    y='count',
    text='count',
    title="Fallzahlen pro Jahr"
)
fig_jahr.update_traces(marker_color=marker_colors)
fig_jahr.update_layout(xaxis_title=None, yaxis_title=None, showlegend=False)

col1.plotly_chart(fig_jahr, use_container_width=True)

# --- Farben pro Jahr (Quartal) ---
filtered_df['jahr_von_quartal'] = filtered_df['quartal_opdatum'].str.split('-').str[1].astype(int)
jahre_quartal_unique = sorted(filtered_df['jahr_von_quartal'].unique())
farben_quartal = {
    jahr: f"rgb({50+jahr%5*40},{100+jahr%3*50},{150+jahr%4*30})"
    for jahr in jahre_quartal_unique
}

# --- Fallzahlen pro Quartal ---
quartal_counts_df = (
    filtered_df
    .groupby(['quartal_opdatum', 'jahr_von_quartal'])
    .size()
    .reset_index(name='count')
    .sort_values('quartal_opdatum')
)

marker_colors_q = [
    farben_quartal[j] for j in quartal_counts_df['jahr_von_quartal']
]

fig_quartal = px.bar(
    quartal_counts_df,
    x='quartal_opdatum',
    y='count',
    text='count',
    title="Fallzahlen pro Quartal"
)
fig_quartal.update_traces(marker_color=marker_colors_q)
fig_quartal.update_layout(xaxis_title=None, yaxis_title=None, showlegend=False)

col2.plotly_chart(fig_quartal, use_container_width=True)

# --- Weitere Plots ---
st.plotly_chart(
    px.pie(filtered_df, names='bereich', title="Verteilung nach Bereich")
)

st.plotly_chart(
    px.bar(
        filtered_df['max_dindo_calc_surv'].value_counts().sort_index(),
        title="Clavien-Dindo Komplikationen"
    )
)

st.plotly_chart(
    px.bar(
        filtered_df['zugang'].value_counts(),
        title="Verteilung nach Zugangsart"
    )
)

# --- Trend ---
trend_data = (
    filtered_df
    .groupby(['jahr_opdatum', 'bereich'])
    .size()
    .reset_index(name='count')
)

st.plotly_chart(
    px.line(
        trend_data,
        x='jahr_opdatum',
        y='count',
        color='bereich',
        title="Trend über Zeit nach Bereich"
    )
)
