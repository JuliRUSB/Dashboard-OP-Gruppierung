# ==================================================
# Imports – Bibliotheken laden
# ==================================================
import os
import requests
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import plotly.io as pio
import streamlit as st
import urllib3

# Warnungen von urllib3 deaktivieren
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ==================================================
# Globale Plotly Konfiguration (Barrierefrei)
# ==================================================
# Setzt die "Safe"-Palette als Standard für alle Diagramme
pio.templates.default = "plotly_white"
px.defaults.color_discrete_sequence = px.colors.qualitative.Safe
pio.templates[pio.templates.default].layout.colorway = px.colors.qualitative.Safe

# ==================================================
# Konfiguration
# ==================================================
API_URL = 'https://fxdb.usb.ch' 

# ==================================================
# Datenexport aus REDCap
# ==================================================
@st.cache_data(ttl=300)
def export_redcap_data(api_url):
    """Exportiert Daten aus REDCap mit Caching"""
    API_TOKEN = os.getenv("tok_op_gruppen")
    if not API_TOKEN:
        st.error("API Token nicht gefunden. Bitte Umgebungsvariable 'tok_op_gruppen' setzen.")
        return None
    
    data = {
        'token': API_TOKEN,
        'content': 'record',
        'action': 'export',
        'format': 'json',
        'type': 'flat',
        'fields[0]': 'opdatum',
        'fields[1]': 'bereich',
        'fields[2]': 'leber_gruppen',
        'fields[3]': 'hsm',
        'fields[4]': 'zugang',
        'fields[5]': 'max_dindo_calc',
        'fields[6]': 'los_opdatum',
        'fields[7]': 'los_eintritt_austritt',
        'rawOrLabel': 'raw',
        'rawOrLabelHeaders': 'raw',
        'exportCheckboxLabel': 'false',
        'exportSurveyFields': 'false',
        'exportDataAccessGroups': 'false',
        'returnFormat': 'json'
    }
    try:
        r = requests.post(api_url, data=data, verify=False, timeout=30)
        r.raise_for_status()
        return pd.DataFrame(r.json())
    except requests.exceptions.RequestException as e:
        st.error(f"Fehler beim Export: {e}")
        return None

# ==================================================
# Datenaufbereitung
# ==================================================
@st.cache_data
def prepare_data(df):
    """Bereitet die Rohdaten auf"""
    if df is None or df.empty:
        return None
    
    df = df.copy()
    df['opdatum'] = pd.to_datetime(df['opdatum'], errors='coerce')
    
    # Bereich Mapping
    bereich_cols = [c for c in df.columns if c.startswith('bereich___')]
    if bereich_cols:
        mapping = {
            'bereich___1': 'Allgemein', 'bereich___2': 'BMC', 'bereich___3': 'Endokrin',
            'bereich___4': 'Onkologie', 'bereich___5': 'Hernien', 'bereich___6': 'Kolorektal',
            'bereich___7': 'Leber', 'bereich___8': 'Pankreas', 'bereich___9': 'Upper-GI'
        }
        def get_bereich(row):
            return ', '.join(label for col, label in mapping.items() if row.get(col) == '1') or 'Nicht angegeben'
        df['bereich'] = df.apply(get_bereich, axis=1)
        df = df.drop(columns=bereich_cols)
    
    # Zugang Mapping
    zugang_mapping = {1: 'Offen', 2: 'Laparoskopisch', 3: 'roboter-assistiert', 4: 'konvertiert', 5: 'hybrid'}
    df['zugang'] = pd.to_numeric(df['zugang'], errors='coerce').map(zugang_mapping).fillna('Unbekannt')

    # Clavien-Dindo Mapping
    dindo_mapping = {0: 'Keine', 1: 'Grade I', 2: 'Grade Id', 3: 'Grade II', 4: 'Grade IId', 5: 'Grade IIIa'} # ... gekürzt
    df['max_dindo_calc'] = pd.to_numeric(df['max_dindo_calc'], errors='coerce').map(dindo_mapping).fillna('Unbekannt')

    # Zeitliche Felder
    df['jahr_opdatum'] = df['opdatum'].dt.year.astype('Int64')
    df['quartal_opdatum'] = df['opdatum'].dt.to_period('Q').astype(str).str.replace(r'(\d{4})Q(\d)', r'Q\2-\1', regex=True)
    
    return df.dropna(subset=['jahr_opdatum'])

# ==================================================
# Streamlit App & Filter
# ==================================================
st.set_page_config(page_title="OP-Gruppierung Dashboard", layout="wide")
st.title("📊 Dashboard OP-Gruppierung (2026)")

with st.spinner('Lade Daten...'):
    df_raw = export_redcap_data(API_URL)
    df = prepare_data(df_raw)

if df is None or df.empty:
    st.error("Keine Daten verfügbar.")
    st.stop()

# Sidebar Filter
st.sidebar.header("Filter")
alle_jahre = sorted(df['jahr_opdatum'].unique().tolist())
selected_jahre = st.sidebar.multiselect("Jahre auswählen:", options=alle_jahre, default=alle_jahre)

# Daten filtern
df_filtered = df[df['jahr_opdatum'].isin(selected_jahre)]

# ==================================================
# Visualisierungen (nutzen automatisch 'Safe' Palette)
# ==================================================
col1, col2 = st.columns(2)

with col1:
    st.subheader("Eingriffe nach Bereich")
    fig1 = px.bar(df_filtered, x='bereich', title="Anzahl OPs nach Fachbereich")
    st.plotly_chart(fig1, use_container_width=True)

with col2:
    st.subheader("Zugangsweg")
    # Hier wird die 'Safe' Palette automatisch angewendet
    fig2 = px.pie(df_filtered, names='zugang', title="Verteilung der Zugangswege")
    st.plotly_chart(fig2, use_container_width=True)

st.subheader("Zeitlicher Verlauf")
df_timeline = df_filtered.groupby(['quartal_opdatum', 'bereich']).size().reset_index(name='Anzahl')
fig3 = px.line(df_timeline, x='quartal_opdatum', y='Anzahl', color='bereich', title="OPs pro Quartal")
st.plotly_chart(fig3, use_container_width=True)
