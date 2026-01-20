# ==================================================
# Imports – Bibliotheken laden
# ==================================================
import os                          # Zugriff auf Umgebungsvariablen (z.B. API-Tokens)
import requests                    # HTTP-Requests (hier für REDCap API)
import pandas as pd                # Datenverarbeitung mit DataFrames
import plotly.express as px        # Plotly Express für Diagramme
import streamlit as st             # Streamlit für Web-App
import urllib3                     # Bibliothek für HTTP-Kommunikation

# Warnungen von urllib3 deaktivieren (unsicheres HTTPS)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ==================================================
# Konfiguration
# ==================================================
API_URL = 'https://fxdb.usb.ch/api/'  # REDCap API URL

# ==================================================
# Datenexport aus REDCap
# ==================================================
@st.cache_data(ttl=300)  # Ergebnisse werden 5 Minuten gecacht, um wiederholte API-Aufrufe zu vermeiden
def export_redcap_data(api_url):
    """Exportiert Daten aus REDCap mit Caching"""
    # API-Token aus Umgebungsvariable holen
    API_TOKEN = os.getenv("tok_op_gruppen")
    if not API_TOKEN:
        st.error("API Token nicht gefunden. Bitte Umgebungsvariable 'tok_op_gruppen' setzen.")
        return None
    
    # Daten für POST-Request definieren
    data = {
        'token': API_TOKEN,
        'content': 'record',              # Datentyp: Records
        'action': 'export',               # Aktion: Export
        'format': 'json',                 # Format: JSON
        'type': 'flat',                   # Flache Struktur (nicht verschachtelt)
        'fields[0]': 'opdatum',           # Felder, die exportiert werden sollen
        'fields[1]': 'bereich',
        'fields[2]': 'hsm',
        'fields[3]': 'zugang',
        'fields[4]': 'max_dindo_calc_surv',
        'rawOrLabel': 'raw',              # Werte als Rohdaten exportieren
        'rawOrLabelHeaders': 'raw',
        'exportCheckboxLabel': 'false',
        'exportSurveyFields': 'false',
        'exportDataAccessGroups': 'false',
        'returnFormat': 'json'
    }
    try:
        # API-Request senden (POST)
        r = requests.post(api_url, data=data, verify=False, timeout=30)
        r.raise_for_status()  # Fehler werfen, falls HTTP-Status nicht OK
        return pd.DataFrame(r.json())  # JSON in DataFrame umwandeln
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
    
    df = df.copy()  # Kopie, damit Originaldaten nicht verändert werden
    df['opdatum'] = pd.to_datetime(df['opdatum'], errors='coerce')  # Datum konvertieren
    
    # Bereich: Spalten mit 'bereich___' zusammenfassen
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
        # Funktion, um alle markierten Bereiche zu einem String zusammenzufassen
        def get_bereich(row):
            return ', '.join(label for col, label in mapping.items() if row.get(col) == '1') or 'Nicht angegeben'
        df['bereich'] = df.apply(get_bereich, axis=1)
        df = df.drop(columns=bereich_cols)  # Ursprüngliche Spalten löschen

    # Zugang: numerische Codes in Text umwandeln
    zugang_mapping = {
        1: 'Offen',
        2: 'Laparoskopisch',
        3: 'roboter-assistiert',
        4: 'konvertiert',
        5: 'hybrid (2Höhlen-Eingriffe)'
    }
    df['zugang'] = pd.to_numeric(df['zugang'], errors='coerce')
    df['zugang'] = df['zugang'].map(zugang_mapping).fillna('Unbekannt')

    # Numerische Felder für Analyse erstellen
    df['jahr_opdatum'] = df['opdatum'].dt.year.astype('Int64')  # Jahr extrahieren
    # Quartal als "Q1-2026"-Format
    df['quartal_opdatum'] = df['opdatum'].dt.to_period('Q').astype(str).str.replace(
        r'(\d{4})Q(\d)', r'Q\2-\1', regex=True)
    # Quartals-Sortierung als Zahl (für Diagramme)
    df['quartal_sort'] = df['opdatum'].dt.year * 10 + df['opdatum'].dt.quarter
    df['max_dindo_calc_surv'] = pd.to_numeric(df['max_dindo_calc_surv'], errors='coerce')
    
    # Zeilen ohne gültiges Datum entfernen
    df = df.dropna(subset=['jahr_opdatum'])
    
    return df

# ==================================================
# Streamlit App
# ==================================================
st.set_page_config(page_title="OP-Gruppierung Dashboard", layout="wide")  # Layout festlegen
st.title("Dashboard OP-Gruppierung")

# Daten laden
with st.spinner('Lade Daten...'):
    df_raw = export_redcap_data(API_URL)  # Daten aus REDCap exportieren
    df = prepare_data(df_raw)             # Daten aufbereiten

# Fehlerbehandlung: keine Daten
if df is None or df.empty:
    st.error("Keine Daten verfügbar.")
    st.stop()

# -------- Session State initialisieren --------
# Alle Jahre und Quartale sammeln
alle_jahre = sorted(df['jahr_opdatum'].dropna().unique().tolist())
alle_quartale = sorted(df['quartal_opdatum'].dropna().unique().tolist())

# Session State verwenden, damit Auswahl zwischen Reloads erhalten bleibt
if 'selected_jahre' not in st.session_state:
    st.session_state.selected_jahre = alle_jahre
if 'selected_quartale' not in st.session_state:
    st.session_state.selected_quartale = alle_quartale

# -------- Sidebar für Filter --------
# Breite der Sidebar anpassen
st.markdown(
    """
    <style>
    section[data-testid="stSidebar"] {
        width: 450px !important; 
    }
    </style>
    """,
    unsafe_allow_html=True,
)

with st.sidebar:
    st.header("Filter")
    
    # Filter: Jahr (Multi-Select)
    jahr_filter = st.multiselect(
        "Jahr auswählen:",
        options=alle_jahre,
        default=st.session_state.selected_jahre,
        key='jahr_select'
    )

    # Änderungen in Jahr-Auswahl erkennen und Quartale anpassen
    if jahr_filter != st.session_state.selected_jahre:
        hinzugefuegt = set(jahr_filter) - set(st.session_state.selected_jahre)
        entfernt = set(st.session_state.selected_jahre) - set(jahr_filter)
        
        neue_quartale = set(st.session_state.selected_quartale)
        
        # Neue Jahre -> Quartale hinzufügen
        if hinzugefuegt:
            jahr_quartale = df[df['jahr_opdatum'].isin(hinzugefuegt)]['quartal_opdatum'].unique()
            neue_quartale.update(jahr_quartale)
        
        # Entfernte Jahre -> Quartale entfernen
        if entfernt:
            jahr_quartale = df[df['jahr_opdatum'].isin(entfernt)]['quartal_opdatum'].unique()
            neue_quartale -= set(jahr_quartale)
        
        st.session_state.selected_quartale = sorted(neue_quartale)
        st.session_state.selected_jahre = jahr_filter

    # Filter: Quartal
    verfuegbare_quartale = sorted(df[df['jahr_opdatum'].isin(jahr_filter)]['quartal_opdatum'].unique()) if jahr_filter else []
    gueltige_quartale = [q for q in st.session_state.selected_quartale if q in verfuegbare_quartale]

    quartal_filter = st.multiselect(
        "Quartal auswählen:",
        options=verfuegbare_quartale,
        default=gueltige_quartale,
        key='quartal_select'
    )

    # Änderungen in Quartal-Auswahl erkennen und Jahre anpassen
    if quartal_filter != gueltige_quartale:
        neue_jahre = []
        for jahr in jahr_filter:
            jahr_quartale = df[df['jahr_opdatum'] == jahr]['quartal_opdatum'].unique()
            if any(q in quartal_filter for q in jahr_quartale):
                neue_jahre.append(jahr)
        
        if neue_jahre != jahr_filter:
            st.session_state.selected_jahre = neue_jahre
            st.session_state.selected_quartale = quartal_filter
            st.rerun()
        
        st.session_state.selected_quartale = quartal_filter

    st.divider()
    
    # Bereich-Filter (Dropdown)
    bereich_filter = st.selectbox(
        "Bereich auswählen:", 
        ["Alle"] + sorted(df['bereich'].unique())
    )

    # Zugang-Filter (Dropdown)
    zugang_filter = st.selectbox(
        "Zugang auswählen:", 
        ["Alle"] + sorted(df['zugang'].unique())
    )

# -------- Daten filtern --------
# Nach Jahren filtern für Jahresgraph
df_jahr_filtered = df[df['jahr_opdatum'].isin(jahr_filter)].copy()

# Nach Jahren und Quartalen filtern für Quartalgraph & Details
df_filtered = df[
    (df['jahr_opdatum'].isin(jahr_filter)) &
    (df['quartal_opdatum'].isin(quartal_filter))
].copy()

# Weitere Filter anwenden (Bereich, Zugang)
if bereich_filter != "Alle":
    df_jahr_filtered = df_jahr_filtered[df_jahr_filtered['bereich'] == bereich_filter]
    df_filtered = df_filtered[df_filtered['bereich'] == bereich_filter]

if zugang_filter != "Alle":
    df_jahr_filtered = df_jahr_filtered[df_jahr_filtered['zugang'] == zugang_filter]
    df_filtered = df_filtered[df_filtered['zugang'] == zugang_filter]

# -------- Kennzahlen --------
st.header("Kennzahlen")
col1, col2, col3, col4 = st.columns(4)  # 4 Spalten für Kennzahlen

with col1:
    st.metric("Gesamt Fälle", len(df_filtered))  # Anzahl gefilterter Fälle
    
with col2:
    avg_dindo = df_filtered['max_dindo_calc_surv'].mean()  # Durchschnitt Clavien-Dindo
    st.metric("Ø Clavien-Dindo", f"{avg_dindo:.2f}" if pd.notna(avg_dindo) else "N/A")
    
with col3:
    st.metric("Bereiche", df_filtered['bereich'].nunique())  # Anzahl verschiedener Bereiche
    
with col4:
    st.metric("Zeitraum", f"{len(jahr_filter)} Jahre, {len(quartal_filter)} Quartale")  # Zeitraum anzeigen

st.divider()

# -------- Visualisierungen --------
st.header("Fallzahlen Übersicht")

if len(df_filtered) == 0:
    st.warning("Keine Daten für die gewählten Filter verfügbar.")
    st.stop()

col1, col2 = st.columns(2)  # Zwei Spalten für Graphen

# Funktion für Farbzuordnung nach Jahr
def get_color_for_year(jahr):
    return f"rgb({50+jahr%5*40},{100+jahr%3*50},{150+jahr%4*30})"

# Graph 1: Jahr
with col1:
    if len(df_jahr_filtered) > 0:
        jahr_counts_df = df_jahr_filtered.groupby('jahr_opdatum', as_index=False).size()
        jahr_counts_df.columns = ['jahr_opdatum', 'count']
        
        farben_jahr = {jahr: get_color_for_year(jahr) for jahr in jahr_counts_df['jahr_opdatum']}
        marker_colors = [farben_jahr[jahr] for jahr in jahr_counts_df['jahr_opdatum']]
        
        fig_jahr = px.bar(
            jahr_counts_df, 
            x='jahr_opdatum', 
            y='count', 
            text='count', 
            title="Fallzahlen pro Jahr"
        )
        fig_jahr.update_traces(marker_color=marker_colors, textfont_size=16, textposition='inside')
        fig_jahr.update_layout(xaxis_title=None, yaxis_title="Anzahl Fälle", showlegend=False, height=400)
        st.plotly_chart(fig_jahr, use_container_width=True)

# Graph 2: Quartal
with col2:
    if len(df_filtered) > 0:
        quartal_counts_df = df_filtered.groupby('quartal_opdatum', as_index=False).size()
        quartal_counts_df.columns = ['quartal_opdatum', 'count']
        
        quartal_counts_df['jahr'] = quartal_counts_df['quartal_opdatum'].str.split('-').str[1].astype(int)
        farben_quartal = {jahr: get_color_for_year(jahr) for jahr in quartal_counts_df['jahr'].unique()}
        marker_colors_quartal = [farben_quartal[jahr] for jahr in quartal_counts_df['jahr']]
        
        fig_quartal = px.bar(
            quartal_counts_df, 
            x='quartal_opdatum', 
            y='count', 
            text='count', 
            title="Fallzahlen pro Quartal"
        )
        fig_quartal.update_traces(marker_color=marker_colors_quartal, textfont_size=16, textposition='inside')
        fig_quartal.update_layout(xaxis_title=None, yaxis_title="Anzahl Fälle", showlegend=False, height=400)
        st.plotly_chart(fig_quartal, use_container_width=True)

st.divider()

# -------- Weitere Analysen (Tabs) --------
st.header("Detailanalysen")
tab1, tab2, tab3, tab4, tab5 = st.tabs(["Bereich", "Zugang", "Komplikationen", "HSM", "Trends"])

# Bereich-Piechart
with tab1:
    if df_filtered['bereich'].nunique() > 0:
        # Farbpalette basierend auf der Jahr-Farblogik
        bereiche = sorted(df_filtered['bereich'].unique())
        bereich_farben = [f"rgb({50+i*40},{100+i*50},{150+i*30})" for i in range(len(bereiche))]
        
        fig_bereich = px.pie(df_filtered, names='bereich', title="Verteilung nach Bereich", hole=0.3,
                            color_discrete_sequence=bereich_farben)
        st.plotly_chart(fig_bereich, use_container_width=True)
    else:
        st.info("Keine Bereichsdaten verfügbar")

# Zugang-Balkendiagramm
with tab2:
    if df_filtered['zugang'].nunique() > 0:
        zugang_counts = (
            df_filtered
            .groupby(['jahr_opdatum', 'zugang'], as_index=False)
            .size()
        )
        zugang_counts.columns = ['jahr_opdatum', 'zugang', 'count']
        
        # Farben für jedes Jahr
        farben_jahr_zugang = {jahr: get_color_for_year(jahr) for jahr in zugang_counts['jahr_opdatum'].unique()}

        fig_zugang = px.bar(
            zugang_counts,
            x='jahr_opdatum',
            y='count',
            color='zugang',
            barmode='group',
            text='count',
            title="Verteilung nach Zugangsart und Jahr",
            color_discrete_sequence=[f"rgb({50+i*40},{100+i*50},{150+i*30})" for i in range(df_filtered['zugang'].nunique())]
        )
        fig_zugang.update_traces(textposition='inside', textfont_size=16)
        fig_zugang.update_layout(xaxis_title=None, yaxis_title="Anzahl Fälle")
        st.plotly_chart(fig_zugang, use_container_width=True)
    else:
        st.info("Keine Zugangsdaten verfügbar")

# Komplikationen-Balkendiagramm (Clavien-Dindo)
with tab3:
    dindo_data = df_filtered['max_dindo_calc_surv'].dropna()
    if len(dindo_data) > 0:
        dindo_counts = dindo_data.value_counts().sort_index().reset_index()
        dindo_counts.columns = ['dindo', 'count']
        
        # Farben für Dindo-Grade
        dindo_farben = [f"rgb({50+int(i)*35},{100+int(i)*40},{150+int(i)*25})" for i in dindo_counts['dindo']]
        
        fig_dindo = px.bar(dindo_counts, x='dindo', y='count', text='count', title="Clavien-Dindo Komplikationen")
        fig_dindo.update_traces(marker_color=dindo_farben, textposition='inside', textfont_size=16)
        st.plotly_chart(fig_dindo, use_container_width=True)
    else:
        st.info("Keine Komplikationsdaten verfügbar")

#HSM-Balkendiagramm
with tab4:
    if df_filtered['hsm'].notna().any():
        hsm_counts = (
            df_filtered
            .dropna(subset=['hsm', 'jahr_opdatum'])
            .assign(
                hsm=lambda d: d['hsm'].astype(str).map({'0': 'Nein', '1': 'Ja'})
            )
            .groupby(['jahr_opdatum', 'hsm'], as_index=False)
            .size()
        )
        hsm_counts.columns = ['jahr_opdatum', 'hsm', 'count']

        fig_hsm = px.bar(
            hsm_counts,
            x='jahr_opdatum',
            y='count',
            color='hsm',
            barmode='group',
            text='count',
            title="HSM nach Jahr",
            labels={'hsm': 'HSM'},
            color_discrete_sequence=[f"rgb({90},{140},{180})", f"rgb({130},{180},{220})"]
        )
        fig_hsm.update_traces(textposition='inside', textfont_size=16)
        fig_hsm.update_layout(xaxis_title=None, yaxis_title="Anzahl Fälle")
        st.plotly_chart(fig_hsm, use_container_width=True)
    else:
        st.info("Keine HSM-Informationen verfügbar")

# Trends über Jahre nach Bereich
with tab5:
    if len(df_filtered) > 0 and df_filtered['bereich'].nunique() > 1:
        trend_data = df_filtered.groupby(['jahr_opdatum', 'bereich'], as_index=False).size()
        trend_data.columns = ['jahr_opdatum', 'bereich', 'count']
        
        # Farbpalette für Bereiche im Trend
        bereiche_trend = sorted(trend_data['bereich'].unique())
        trend_farben = [f"rgb({50+i*40},{100+i*50},{150+i*30})" for i in range(len(bereiche_trend))]
        
        fig_trend = px.line(trend_data, x='jahr_opdatum', y='count', color='bereich', 
                           title="Trend über Zeit nach Bereich", markers=True,
                           color_discrete_sequence=trend_farben)
        st.plotly_chart(fig_trend, use_container_width=True)
    else:
        st.info("Nicht genügend Daten für Trendanalyse")
