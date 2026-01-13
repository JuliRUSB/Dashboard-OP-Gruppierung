# ==================================================
# Imports
# ==================================================
import os
import requests
import pandas as pd
import plotly.express as px
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

    # Bereich
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

    # Zugang
    zugang_mapping = {
        1: 'Offen',
        2: 'Laparoskopisch',
        3: 'roboter-assistiert',
        4: 'konvertiert',
        5: 'hybrid (2Höhlen-Eingriffe)'
    }
    df['zugang'] = pd.to_numeric(df['zugang'], errors='coerce')
    df['zugang'] = df['zugang'].map(zugang_mapping).fillna('Unbekannt')

    # Numerische Felder
    df['jahr_opdatum'] = df['opdatum'].dt.year.astype('Int64')
    df['quartal_opdatum'] = df['opdatum'].dt.to_period('Q').astype(str).str.replace(r'(\d{4})Q(\d)', r'Q\2-\1', regex=True)
    df['quartal_sort'] = df['opdatum'].dt.year * 10 + df['opdatum'].dt.quarter
    df['max_dindo_calc_surv'] = pd.to_numeric(df['max_dindo_calc_surv'], errors='coerce')
    df = df.dropna(subset=['jahr_opdatum'])
    return df

# ==================================================
# Streamlit App
# ==================================================
st.title("OP-Gruppierung Dashboard")

df = export_redcap_data(API_URL)
if df is not None:
    df = prepare_data(df)
else:
    st.stop()

# -------- Session State initialisieren --------
alle_jahre = sorted(df['jahr_opdatum'].unique())
alle_quartale = sorted(df['quartal_opdatum'].unique())

if 'selected_jahre' not in st.session_state:
    st.session_state.selected_jahre = alle_jahre
if 'selected_quartale' not in st.session_state:
    st.session_state.selected_quartale = alle_quartale

# -------- Filter: Jahr --------
jahr_filter = st.multiselect(
    "Jahr auswählen:",
    options=alle_jahre,
    default=st.session_state.selected_jahre
)

# Jahr-Änderung erkennen und Quartale anpassen
if jahr_filter != st.session_state.selected_jahre:
    hinzugefuegt = set(jahr_filter) - set(st.session_state.selected_jahre)
    entfernt = set(st.session_state.selected_jahre) - set(jahr_filter)
    
    neue_quartale = set(st.session_state.selected_quartale)
    
    # Quartale für neue Jahre hinzufügen
    for jahr in hinzugefuegt:
        jahr_quartale = df[df['jahr_opdatum'] == jahr]['quartal_opdatum'].unique()
        neue_quartale.update(jahr_quartale)
    
    # Quartale für entfernte Jahre entfernen
    for jahr in entfernt:
        jahr_quartale = df[df['jahr_opdatum'] == jahr]['quartal_opdatum'].unique()
        neue_quartale -= set(jahr_quartale)
    
    st.session_state.selected_quartale = sorted(neue_quartale)
    st.session_state.selected_jahre = jahr_filter

# -------- Filter: Quartal --------
# Nur Quartale der ausgewählten Jahre anzeigen
verfuegbare_quartale = sorted(df[df['jahr_opdatum'].isin(jahr_filter)]['quartal_opdatum'].unique())
gueltige_quartale = [q for q in st.session_state.selected_quartale if q in verfuegbare_quartale]

quartal_filter = st.multiselect(
    "Quartal auswählen:",
    options=verfuegbare_quartale,
    default=gueltige_quartale
)

# Quartal-Änderung erkennen und Jahre anpassen
if quartal_filter != gueltige_quartale:
    # Welche Jahre sind durch die gewählten Quartale abgedeckt?
    jahre_aus_quartalen = set(df[df['quartal_opdatum'].isin(quartal_filter)]['jahr_opdatum'].unique())
    
    # Wenn ein Jahr keine Quartale mehr hat, Jahr auch entfernen
    neue_jahre = []
    for jahr in jahr_filter:
        jahr_quartale = df[df['jahr_opdatum'] == jahr]['quartal_opdatum'].unique()
        # Prüfe ob mindestens ein Quartal dieses Jahres ausgewählt ist
        if any(q in quartal_filter for q in jahr_quartale):
            neue_jahre.append(jahr)
    
    if neue_jahre != jahr_filter:
        st.session_state.selected_jahre = neue_jahre
        st.session_state.selected_quartale = quartal_filter
        st.rerun()
    
    st.session_state.selected_quartale = quartal_filter

# -------- Daten filtern --------
# Für Jahresgraph: nur nach Jahren filtern
df_jahr_filtered = df[df['jahr_opdatum'].isin(jahr_filter)]

# Für Quartalgraph und Details: nach Jahren UND Quartalen filtern
df_filtered = df[
    (df['jahr_opdatum'].isin(jahr_filter)) &
    (df['quartal_opdatum'].isin(quartal_filter))
]

# Bereich
bereich_filter = st.selectbox("Bereich auswählen:", ["Alle"] + sorted(df['bereich'].unique()))
if bereich_filter != "Alle":
    df_filtered = df_filtered[df_filtered['bereich'] == bereich_filter]

# Zugang
zugang_filter = st.selectbox("Zugang auswählen:", ["Alle"] + sorted(df['zugang'].unique()))
if zugang_filter != "Alle":
    df_filtered = df_filtered[df_filtered['zugang'] == zugang_filter]

# -------- Kennzahlen --------
st.subheader("Kennzahlen")
col1, col2, col3 = st.columns(3)
col1.metric("Gesamt Fälle", len(df_filtered))
avg_dindo = df_filtered['max_dindo_calc_surv'].mean()
col2.metric("Ø Clavien-Dindo", f"{avg_dindo:.2f}" if pd.notna(avg_dindo) else "N/A")
col3.metric("Bereiche", df_filtered['bereich'].nunique())

# -------- Visualisierungen --------
st.subheader("Visualisierungen")
col1, col2 = st.columns(2)

# Farbdictionary Jahr
jahre_unique = sorted(df_filtered['jahr_opdatum'].unique())
farben = {jahr: f"rgb({50+jahr%5*40},{100+jahr%3*50},{150+jahr%4*30})" for jahr in jahre_unique}

# Graph 1: Jahr (zeigt ALLE Quartale der ausgewählten Jahre)
if len(df_jahr_filtered) > 0:
    jahr_counts_df = df_jahr_filtered.groupby('jahr_opdatum').size().reset_index(name='count')
    marker_colors = [farben.get(jahr, 'rgb(100,100,100)') for jahr in jahr_counts_df['jahr_opdatum']]
    fig_jahr = px.bar(jahr_counts_df, x='jahr_opdatum', y='count', text='count', title="Fallzahlen pro Jahr")
    fig_jahr.update_traces(marker_color=marker_colors, textfont_size=16, textposition='inside')
    fig_jahr.update_layout(xaxis_title=None, yaxis_title=None, showlegend=False)
    col1.plotly_chart(fig_jahr, use_container_width=True)

    # Graph 2: Quartal (zeigt nur ausgewählte Quartale)
    df_quartal_plot = df_filtered.copy()
    if len(df_quartal_plot) > 0:
        df_quartal_plot['jahr_von_quartal'] = df_quartal_plot['quartal_opdatum'].str.split('-').str[1].astype(int)
        jahre_quartal_unique = sorted(df_quartal_plot['jahr_von_quartal'].unique())
        farben_quartal = {jahr: f"rgb({50+jahr%5*40},{100+jahr%3*50},{150+jahr%4*30})" for jahr in jahre_quartal_unique}

        quartal_counts_df = df_quartal_plot.groupby('quartal_opdatum').size().reset_index(name='count')
        marker_colors_quartal = [farben_quartal[int(q.split('-')[1])] for q in quartal_counts_df['quartal_opdatum']]
        fig_quartal = px.bar(quartal_counts_df, x='quartal_opdatum', y='count', text='count', title="Fallzahlen pro Quartal")
        fig_quartal.update_traces(marker_color=marker_colors_quartal, textfont_size=16, textposition='inside')
        fig_quartal.update_layout(xaxis_title=None, yaxis_title=None, showlegend=False)
        col2.plotly_chart(fig_quartal, use_container_width=True)

    # Pie nach Bereich
    st.plotly_chart(px.pie(df_filtered, names='bereich', title="Verteilung nach Bereich"))

    # Clavien-Dindo
    st.plotly_chart(px.bar(df_filtered['max_dindo_calc_surv'].value_counts().sort_index(), title="Clavien-Dindo Komplikationen"))

    # Zugang
    st.plotly_chart(px.bar(df_filtered['zugang'].value_counts(), title="Verteilung nach Zugangsart"))

    # Trendanalyse
    if 'jahr_opdatum' in df_filtered.columns and 'bereich' in df_filtered.columns:
        trend_data = df_filtered.groupby(['jahr_opdatum','bereich']).size().reset_index(name='count')
        st.plotly_chart(px.line(trend_data, x='jahr_opdatum', y='count', color='bereich', title="Trend über Zeit nach Bereich"))
else:
    st.warning("Keine Daten für die gewählten Filter verfügbar.")
