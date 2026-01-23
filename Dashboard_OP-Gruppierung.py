# ==================================================
# Imports – Bibliotheken laden
# ==================================================
import plotly.graph_objects as go
import os                          # Zugriff auf Umgebungsvariablen
import requests                    # HTTP-Requests für REDCap API
import pandas as pd                # Datenverarbeitung
import plotly.express as px        # Plotly Express für Diagramme
import streamlit as st             # Streamlit für Web-App
import urllib3                     # Bibliothek für HTTP-Kommunikation

# Warnungen von urllib3 deaktivieren (unsicheres HTTPS im Spitalnetz)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ==================================================
# Globale Konfiguration der Farbpalette (Barrierefrei)
# ==================================================
# Dies setzt die "Safe"-Palette als Standard für alle Plotly Express Diagramme
px.defaults.color_discrete_sequence = px.colors.qualitative.Safe

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
            return ', '.join(label for col, label in mapping.items() if row.get(col) == '1') or 'Nicht angegeben'
        df['bereich'] = df.apply(get_bereich, axis=1)
        df = df.drop(columns=bereich_cols)
    
    # Leber-Gruppen Mapping
    leber_gruppen_cols = [c for c in df.columns if c.startswith('leber_gruppen___')]
    if leber_gruppen_cols:
        mapping_leber = {
            'leber_gruppen___1': 'HCC',
            'leber_gruppen___2': 'CCC',
            'leber_gruppen___3': 'Metastasen',
            'leber_gruppen___4': 'Benigne',
        }
        def get_leber_gruppen(row):
            return ', '.join(label for col, label in mapping_leber.items() if row.get(col) == '1') or 'Nicht angegeben'
        df['leber_gruppen'] = df.apply(get_leber_gruppen, axis=1)
        df = df.drop(columns=leber_gruppen_cols)
    
    # Zugang Mapping
    zugang_mapping = {
        1: 'Offen', 2: 'Laparoskopisch', 3: 'roboter-assistiert', 
        4: 'konvertiert', 5: 'hybrid (2Höhlen-Eingriffe)'
    }
    df['zugang'] = pd.to_numeric(df['zugang'], errors='coerce').map(zugang_mapping).fillna('Unbekannt')

    # Clavien-Dindo Mapping
    dindo_mapping = {
        0: 'Keine Komplikation', 1: 'Grade I', 2: 'Grade Id', 3: 'Grade II', 
        4: 'Grade IId', 5: 'Grade IIIa', 6: 'Grade IIIa d', 7: 'Grade IIIb', 
        8: 'Grade IIIb d', 9: 'Grade IVa', 10: 'Grade IVa d', 11: 'Grade IVb', 
        12: 'Grade IVb d', 13: 'Grade V'
    }
    df['max_dindo_calc'] = pd.to_numeric(df['max_dindo_calc'], errors='coerce').map(dindo_mapping).fillna('Unbekannt')

    # Zeit-Features
    df['jahr_opdatum'] = df['opdatum'].dt.year.astype('Int64')
    df['quartal_opdatum'] = df['opdatum'].dt.to_period('Q').astype(str).str.replace(r'(\d{4})Q(\d)', r'Q\2-\1', regex=True)
    df['quartal_sort'] = df['opdatum'].dt.year * 10 + df['opdatum'].dt.quarter
    
    return df.dropna(subset=['jahr_opdatum'])

# ==================================================
# Streamlit App & Filter
# ==================================================
st.set_page_config(page_title="OP-Gruppierung Dashboard", layout="wide")
st.title("📊 Dashboard OP-Gruppierung (2026)")

# Daten laden
with st.spinner('Lade Daten...'):
    df_raw = export_redcap_data(API_URL)
    df = prepare_data(df_raw)

if df is None or df.empty:
    st.error("Keine Daten verfügbar.")
    st.stop()

# Sidebar für Filter
st.sidebar.header("Filter")
alle_jahre = sorted(df['jahr_opdatum'].unique().tolist())
selected_jahre = st.sidebar.multiselect("Jahre auswählen:", options=alle_jahre, default=alle_jahre)

# Daten filtern
df_filtered = df[df['jahr_opdatum'].isin(selected_jahre)]

# ==================================================
# Visualisierungen (nutzen automatisch die 'Safe' Palette)
# ==================================================
col1, col2 = st.columns(2)

with col1:
    st.subheader("Eingriffe nach Bereich")
    fig1 = px.bar(df_filtered, x='bereich', color='bereich', title="Anzahl OPs pro Fachbereich")
    st.plotly_chart(fig1, use_container_width=True)

with col2:
    st.subheader("Verteilung Zugangsweg")
    fig2 = px.pie(df_filtered, names='zugang', title="Zugangswege (Gesamt)")
    st.plotly_chart(fig2, use_container_width=True)

st.subheader("Zeitlicher Verlauf nach Quartal")
df_timeline = df_filtered.groupby(['quartal_opdatum', 'bereich', 'quartal_sort']).size().reset_index(name='Anzahl')
df_timeline = df_timeline.sort_values('quartal_sort')

fig3 = px.line(df_timeline, x='quartal_opdatum', y='Anzahl', color='bereich', 
               markers=True, title="OP-Entwicklung pro Bereich")
st.plotly_chart(fig3, use_container_width=True)

# Datentabelle anzeigen
if st.checkbox("Rohdaten anzeigen"):
    st.dataframe(df_filtered)
