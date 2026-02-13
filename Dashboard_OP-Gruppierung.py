# ==================================================
# Imports – Bibliotheken laden
# ==================================================

import os                          # Zugriff auf Umgebungsvariablen (z.B. API-Tokens)
import requests                    # HTTP-Requests (hier für REDCap API)
import pandas as pd                # Datenverarbeitung mit DataFrames
import plotly.express as px        # Plotly Express für Diagramme
import streamlit as st             # Streamlit für Web-App
import urllib3                     # Bibliothek für HTTP-Kommunikation
import plotly.graph_objects as go  # Low-Level-Schnittstelle von Plotly

# Warnungen von urllib3 deaktivieren (unsicheres HTTPS)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ==================================================
# Konfiguration
# ==================================================
API_URL = 'https://fxdb.usb.ch/api/'  # REDCap API URL

# ==================================================F
# Globale Farbpalette
COLOR_PALETTE = px.colors.qualitative.Safe
# ==================================================

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
        'fields[2]': 'leber_gruppen',
        'fields[3]': 'hsm',
        'fields[4]': 'zugang',
        'fields[5]': 'max_dindo_calc',
        'fields[6]': 'los_opdatum',
        'fields[7]':  'los_eintritt_austritt',
        'fields[8]':  'type_sark',
        'fields[9]':  'gruppen_chir_onko_sark',
        'fields[10]':  'malignit_t_sark',
        'fields[11]':  'lokalisation_sark',
        'fields[12]':  'hipec',
        'fields[13]':  'anastomosen_crs',
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
    
    # Bereich: Spalten mit 'bereich___' mappen
    bereich_cols = [c for c in df.columns if c.startswith('bereich___')]
    if bereich_cols:
        mapping = {
            #'bereich___1': 'Allgemein',
            'bereich___2': 'BMC',
            #'bereich___3': 'Endokrin',
            'bereich___4': 'Chirurgische Onkologie/Sarkome',
            #'bereich___5': 'Hernien',
            #'bereich___6': 'Kolorektal',
            'bereich___7': 'Leber',
            'bereich___8': 'Pankreas',
            'bereich___9': 'Upper-GI'
        }
        # Funktion, um alle markierten Bereiche zu einem String zusammenzufassen
        def get_bereich(row):
            return ', '.join(label for col, label in mapping.items() if row.get(col) == '1') or 'Nicht angegeben'
        df['bereich'] = df.apply(get_bereich, axis=1)
        df = df.drop(columns=bereich_cols)  # Ursprüngliche Spalten löschen
    
    # Leber-Gruppen: Spalten mit 'leber_gruppen___' mappen
    leber_gruppen_cols = [c for c in df.columns if c.startswith('leber_gruppen___')]
    if leber_gruppen_cols:
        mapping = {
            'leber_gruppen___1': 'HCC',
            'leber_gruppen___2': 'CCC',
            'leber_gruppen___3': 'Metastasen',
            'leber_gruppen___4': 'Benigne',
        }
        # Funktion, um alle markierten Bereiche zu einem String zusammenzufassen
        def get_leber_gruppen(row):
            return ', '.join(label for col, label in mapping.items() if row.get(col) == '1') or 'Nicht angegeben'
        df['leber_gruppen'] = df.apply(get_leber_gruppen, axis=1)
        df = df.drop(columns=leber_gruppen_cols)  # Ursprüngliche Spalten löschen

    # Sarkom-Gruppen: Spalten mit 'gruppen_chir_onko_sark___' mappen
    gruppen_chir_onko_sark_cols = [c for c in df.columns if c.startswith('gruppen_chir_onko_sark___')]
    if gruppen_chir_onko_sark_cols:
        mapping = {
            'gruppen_chir_onko_sark___1': 'Knochen',
            'gruppen_chir_onko_sark___2': 'Weichteil',
            'gruppen_chir_onko_sark___3': 'GIST',
            'gruppen_chir_onko_sark___4': 'Andere Malignome',
        }
        # Funktion, um alle markierten Bereiche zu einem String zusammenzufassen
        def get_gruppen_chir_onko_sark(row):
            return ', '.join(label for col, label in mapping.items() if row.get(col) == '1') or 'Nicht angegeben'
        df['gruppen_chir_onko_sark'] = df.apply(get_gruppen_chir_onko_sark, axis=1)
        df = df.drop(columns=gruppen_chir_onko_sark_cols)  # Ursprüngliche Spalten löschen
    
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

    # Typ Sarkom: numerische Codes in Text umwandeln
    type_sark_mapping = {
        1: 'CRS',
        2: 'Sarkom/Weichteiltumor'
    }
    df['type_sark'] = pd.to_numeric(df['type_sark'], errors='coerce')
    df['type_sark'] = df['type_sark'].map(type_sark_mapping).fillna('Unbekannt')

    # HIPEC: numerische Codes in Text umwandeln
    hipec_mapping = {
        1: 'Ja',
        0: 'Nein'
    }
    df['hipec'] = pd.to_numeric(df['hipec'], errors='coerce')
    df['hipec'] = df['hipec'].map(hipec_mapping).fillna('Unbekannt')

    # Bereich: Spalten mit 'lokalisation_sark___' mappen
    lokalisation_sark_cols = [c for c in df.columns if c.startswith('lokalisation_sark___')]
    if lokalisation_sark_cols:
        mapping = {
            'lokalisation_sark___1': 'Kopf/Hals',
            'lokalisation_sark___2': 'Stamm',
            'lokalisation_sark___3': 'Extremitäten',
            'lokalisation_sark___4': 'Abdomen/retroperitoneal',
            'lokalisation_sark___5': 'andere'
        }
        # Funktion, um alle markierten Bereiche zu einem String zusammenzufassen
        def get_lokalisation_sark(row):
            return ', '.join(label for col, label in mapping.items() if row.get(col) == '1') or 'Nicht angegeben'
        df['lokalisation_sark'] = df.apply(get_lokalisation_sark, axis=1)
        df = df.drop(columns=lokalisation_sark_cols)  # Ursprüngliche Spalten löschen
    
    # Clavien-Dindo-Max: numerische Codes in Text umwandeln
    max_dindo_calc_mapping = {
        0: 'Keine Komplikation',
        1: 'Grade I',
        2: 'Grade Id',
        3: 'Grade II',
        4: 'Grade IId',
        5: 'Grade IIIa',
        6: 'Grade IIIa d',
        7: 'Grade IIIb',
        8: 'Grade IIIb d',
        9: 'Grade IVa',
        10: 'Grade IVa d',
        11: 'Grade IVb',
        12: 'Grade IVb d',
        13: 'Grade V'
    }
    df['max_dindo_calc'] = pd.to_numeric(df['max_dindo_calc'], errors='coerce')
    df['max_dindo_calc'] = df['max_dindo_calc'].map(max_dindo_calc_mapping).fillna('Unbekannt')

    # Numerische Felder für Analyse erstellen
    df['jahr_opdatum'] = df['opdatum'].dt.year.astype('Int64')  # Jahr extrahieren
    # Quartal erstellen: 1, 2, 3 oder 4
    df['quartal_opdatum'] = df['opdatum'].dt.quarter
    # Quartal als "Q1-2026"-Format
    df['diag_quartal_opdatum'] = df['opdatum'].dt.to_period('Q').astype(str).str.replace(
        r'(\d{4})Q(\d)', r'Q\2-\1', regex=True)
    # Quartals-Sortierung als Zahl (für Diagramme)
    df['quartal_sort'] = df['opdatum'].dt.year * 10 + df['opdatum'].dt.quarter
    
    # Zeilen ohne gültiges Datum entfernen
    df = df.dropna(subset=['jahr_opdatum'])
    
    return df

# ==================================================
# Hilfsfunktion für konsistente Farben
# ==================================================
def get_color_map(items):
    """Erstellt ein Farbmapping für eine Liste von Items"""
    unique_items = sorted(set(items))
    colors = COLOR_PALETTE * (len(unique_items) // len(COLOR_PALETTE) + 1)
    return {item: colors[i] for i, item in enumerate(unique_items)}

# ==================================================
# Streamlit App
# ==================================================
st.set_page_config(page_title="OP-Gruppierung Dashboard", layout="wide")  # Layout festlegen
st.title("Dashboard OP-Gruppierung")

# ==================================================
# Daten laden
# ==================================================
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
    st.session_state['selected_quartale'] = [1, 2, 3, 4]

# ==================================================
# CSS
# ==================================================
st.markdown(
    """
    <style>
    /* 1. Sidebar Breite stabil anpassen */
    [data-testid="stSidebar"] {
        min-width: 350px !important;
        max-width: 350px !important;
    }

    /* 2. Slider Label Styling */
    div[data-testid="stSlider"] label {
        font-size: 18px !important; 
        margin-bottom: 25px !important; /* Erzeugt Abstand zwischen Überschrift und Slider*/
    }
  
    /* Optional: Falls der Text innerhalb des Labels in einem <p> Tag liegt */
    div[data-testid="stSlider"] label p {
        font-size: 18px !important;
    }

    /* 3. Buttons Label Styling */
    div[data-testid="stButtonGroup"] label {
        font-size: 18px !important; 
        margin-bottom: 25px !important; /* Erzeugt Abstand zwischen Überschrift und Buttonsr*/
    }

    /* Optional: Falls der Text innerhalb des Labels in einem <p> Tag liegt */
    div[data-testid="stButtonGroup"] label p {
        font-size: 18px !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ==================================================
# Sidebar: Jahr-Range-Slider + Quartal-Buttons + Bereich & Zugang
# ==================================================
with st.sidebar:
    st.header("Filter")
    
    # Jahr-Range-Slider
    min_jahr = int(df['jahr_opdatum'].min())
    max_jahr = int(df['jahr_opdatum'].max())
    
    jahr_range = st.slider(
        "Zeitraum auswählen",
        min_value=min_jahr,
        max_value=max_jahr,
        value=(min_jahr, max_jahr)
    )
    
    # Sicherstellen, dass die Liste im Session State existiert
    if 'selected_quartale' not in st.session_state:
        st.session_state['selected_quartale'] = [1, 2, 3, 4]

    #st.write("Quartal(e) auswählen:")
    quartal_labels = {1: "Q1", 2: "Q2", 3: "Q3", 4: "Q4"}
    quartal_werte = [1, 2, 3, 4]

    # Anzeige der aktuell gewählten Quartale
    #st.write(", ".join([f"Q{q}" for q in sorted(st.session_state['selected_quartale'])]))

    # Spalten für die Buttons erstellen
    cols = st.columns(4)

    # 3. Pills-Widget
    selected = st.pills(
        label="Quartal(e) ab-/auswählen", # Label kann mit label_visibility="collapsed" versteckt werden
        options=quartal_werte,
        format_func=lambda x: quartal_labels[x],
        selection_mode="multi",
        default=st.session_state['selected_quartale'],
        key="pills_selection"
    )

    # 4. Update des Session States
    st.session_state['selected_quartale'] = selected

    # Anzeige der aktuell gewählten Quartale
    if st.session_state['selected_quartale']:
        anzeige_liste = [f"Q{q}" for q in sorted(st.session_state['selected_quartale'])]
        # st.write(f"Aktuell gewählt: {', '.join(anzeige_liste)}")
    else:
        st.write("Kein Quartal ausgewählt.")

    # Buttons erstellen (Logik zum An/Abwählen)
    # for i, q in enumerate(quartal_werte):
    #     is_active = q in st.session_state['selected_quartale']
    #     label = f"**{quartal_labels[i]}**" if is_active else quartal_labels[i]

    #     if cols[i].button(label, key=f"q_btn_sidebar_{q}"):
    #         if q in st.session_state['selected_quartale']:
    #             st.session_state['selected_quartale'].remove(q)
    #         else:
    #             st.session_state['selected_quartale'].append(q)
    #         st.rerun()

    # Jahre speichern
    st.session_state['selected_jahre'] = list(range(jahr_range[0], jahr_range[1] + 1))  

    st.divider()
    
    # Bereich-Filter
    bereich_filter = st.selectbox(
        "Bereich auswählen:", 
        ["Alle"] + sorted(df['bereich'].unique())
    )

    # Zugang-Filter
    zugang_filter = st.selectbox(
        "Zugang auswählen:", 
        ["Alle"] + sorted(df['zugang'].unique())
    )


# -------------------- Daten filtern --------------------
selected_jahre = st.session_state['selected_jahre']
selected_quartale = st.session_state['selected_quartale']

# Sicherheitscheck
if not selected_jahre or not selected_quartale:
    st.warning("⚠️ Bitte wählen Sie mindestens ein Jahr und ein Quartal aus.")
    st.stop() # Beendet die Ausführung der App an dieser Stelle
else:
    # Haupt-Filterung
    df_jahr_filtered = df[df['jahr_opdatum'].isin(selected_jahre)].copy()
    
    df_filtered = df[
        (df['jahr_opdatum'].isin(selected_jahre)) & 
        (df['quartal_opdatum'].isin(selected_quartale))
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
    st.metric("Gesamt Fälle", len(df_jahr_filtered))  # Anzahl gefilterter Fälle
    
with col2:
    st.metric("Bereiche", df_jahr_filtered['bereich'].nunique())  # Anzahl verschiedener Bereiche
    
with col3:
    st.metric("Zeitraum", f"{len(st.session_state['selected_jahre'])} Jahre, {len(st.session_state['selected_quartale'])} Quartale")  # Zeitraum anzeigen

st.divider()

# -------- Visualisierungen --------
st.header("Fallzahlen Übersicht")

if len(df_jahr_filtered) == 0:
    st.warning("Keine Daten für die gewählten Filter verfügbar.")
    st.stop()

col1, col2 = st.columns(2)  # Zwei Spalten für Graphen

# Graph 1: Falzahlen pro Jahr
with col1:
    if not df_jahr_filtered.empty:
        # Daten gruppieren
        jahr_counts_df = df_jahr_filtered.groupby('jahr_opdatum', as_index=False).size()
        jahr_counts_df.columns = ['jahr_opdatum', 'count']
        
        # Jahr als String für die Achse
        jahr_counts_df['jahr_str'] = jahr_counts_df['jahr_opdatum'].astype(str)

        # Diagramm erstellen mit COLOR_PALETTE
        fig_jahr = px.bar(
            jahr_counts_df, 
            x='jahr_str', 
            y='count', 
            text='count', 
            color='jahr_str',  # Farbe basierend auf dem Jahr
            color_discrete_sequence=COLOR_PALETTE,
            title="Fallzahlen pro Jahr"
        )
        
        fig_jahr.update_traces(
            textfont_size=16, 
            textposition='inside'
        )
        
        fig_jahr.update_layout(
            xaxis_title=None, 
            yaxis_title=None, 
            showlegend=False, 
            height=400,
            xaxis={'categoryorder': 'category ascending', "type": "category", "tickfont": {"size": 16}}, # Verhindert Zahlensalat auf der X-Achse
            yaxis={"tickfont": {"size": 16}} 
        )
        
        st.plotly_chart(fig_jahr, use_container_width=True)

# Graph 2: Fallzahlen pro Quartal
with col2:
    if not df_filtered.empty:
        # Gruppierung nach Jahr und Quartal
        q_counts = df_filtered.groupby(['jahr_opdatum', 'quartal_opdatum'], as_index=False).size()
        q_counts.columns = ['jahr_opdatum', 'quartal_opdatum', 'count']
        
        # Erstellung der X-Achsen-Beschriftung (Format "Q1-2026")
        # Umwandlung in int entfernt das ".0", falls vorhanden
        q_counts['x_label'] = ("Q" + q_counts['quartal_opdatum'].astype(int).astype(str) + "- " + q_counts['jahr_opdatum'].astype(int).astype(str))
        
        fig_quartal = px.bar(
            q_counts, 
            x='x_label', 
            y='count', 
            text='count',
            color=q_counts['jahr_opdatum'].astype(str),
            color_discrete_sequence=COLOR_PALETTE,
            title="Fallzahlen pro Quartal"
        )
        
        fig_quartal.update_traces(
            textfont_size=16, 
            textposition='inside'
        )
        
        fig_quartal.update_layout(
            xaxis_title=None, 
            yaxis_title=None, 
            showlegend=False, 
            height=400,
            xaxis={'categoryorder': 'category ascending', "type": "category", "tickfont": {"size": 16}}, # Verhindert Zahlensalat auf der X-Achse
            yaxis={"tickfont": {"size": 16}} 
        )
        
        st.plotly_chart(fig_quartal, use_container_width=True)
    else:
        st.warning("Keine Daten für die gewählte Filterkombination vorhanden.")
st.divider()

# -------- Weitere Analysen (Tabs) --------
st.header("Detailanalysen")

# ===== Bereiche definieren (TABS 1. Ebene) =====
bereiche = sorted(df_filtered["bereich"].dropna().unique())

# ===== Bereiche definieren (TABS 2. Ebene) =====
ANALYSEN_PRO_BEREICH = {
    "Chirurgische Onkologie/Sarkome": ["Gesamtzahl Operationen", "Übersicht Sarkome", "Gruppen (Sarkome/Weichteiltumoren)", "HIPEC bei CRS", "Lokalisation (Sarkome/Weichteiltumoren)", "Kolorektale Resektionen bei CRS ohne HIPEC", "Anastomoseinsuffizienz", "Komplikationen", "LOS"],
    "Leber": ["Gruppen", "Zugang", "Komplikationen", "HSM", "LOS", "Trends"],
    #"Kolorektal": ["Zugang", "Komplikationen", "LOS", "Trends"],
    "Upper-GI": ["Zugang", "Komplikationen", "LOS", "Trends"],
    #"Allgemein": ["Komplikationen", "LOS", "Trends"],
    "BMC": ["Komplikationen", "LOS", "Trends"],
    #"Endokrin": ["Zugang", "Komplikationen", "LOS", "Trends"],
    #"Hernien": ["Zugang", "Komplikationen", "LOS", "Trends"],
    "Pankreas": ["Zugang", "Komplikationen", "LOS", "Trends"],
}

bereiche = list(ANALYSEN_PRO_BEREICH.keys())

bereich_tabs = st.tabs(bereiche)

for i, bereich in enumerate(bereiche):
    with bereich_tabs[i]:

        df_bereich = df_filtered[df_filtered["bereich"] == bereich]

        st.subheader(f"Bereich: {bereich}")

        if df_bereich.empty:
            st.warning("Keine Daten für diesen Bereich")
            continue

        analysen = ANALYSEN_PRO_BEREICH.get(bereich)
        tabs = st.tabs(analysen)

        # ================== BEREICH CHURURGISCHE ONKOLOGIE/SARKOME ==================  

        # Drei Spalten/Kacheln definieren
        col1, col2, col3 = st.columns(3)

        # ================== Kachel 1 "Gesamtanzahl Operationen" ==================
        with col1.container(border=True):
            # Vorab-Check der Analyse-Auswahl
            if "Gesamtzahl Operationen" in analysen:
                # Sicherstellen, dass notwendige Spalten vorhanden sind
                required_cols = {"bereich", "jahr_opdatum"}
                if required_cols.issubset(df_bereich.columns):
            
                    # Effiziente Filterung
                    df_plot = df_bereich[df_bereich["bereich"] == 'Chirurgische Onkologie/Sarkome'].copy()
                    total_ops = len(df_plot)
            
                    st.metric(label="Gesamtzahl Operationen (Onkologie/Sarkome)", value=total_ops)
                    st.divider()
            
                    if total_ops > 0:
                        # Aggregation
                        grp = df_plot.groupby("jahr_opdatum").size().reset_index(name="count")
                
                        fig = px.bar(
                            grp,
                            x="jahr_opdatum",
                            y="count",
                            text="count",
                            color_discrete_sequence=COLOR_PALETTE
                        )
            
                        fig.update_traces(
                            textfont_size=14, 
                            textposition='auto',
                            marker_line_width=0 # Cleaner Look
                        )
                
                        fig.update_layout(
                            height=300, # Feste Höhe für Dashboard-Kacheln
                            margin=dict(l=10, r=10, t=10, b=10),
                            xaxis_title=None, 
                            yaxis_title=None, 
                            showlegend=False,
                            xaxis={"type": "category", "tickfont": {"size": 16}},
                            yaxis={"showticklabels": True, "showgrid": True, "tickfont": {"size": 16}} 
                        )
            
                        st.plotly_chart(fig, use_container_width=True, key="chart_ops_onkologie", config={'displayModeBar': False})
                    else:
                        st.info("Keine Daten für diesen Bereich gefunden.")
                else:
                    st.error("Fehlende Spalten im Datensatz.")
            else:
                st.metric(label="Gesamtzahl Operationen", value="-")

            # ================== Kachel 2 "èbersicht Sarkome" ==================
            with col2.container(border=True):
                if "Übersicht Sarkome" in analysen:
                    # Check auf Spalten
                    required_cols = {"type_sark", "jahr_opdatum"}
                    if required_cols.issubset(df_bereich.columns):
            
                        # Filter für Sarkome
                        df_plot = df_bereich[df_bereich["type_sark"].notna()].copy()
                        total_sark = len(df_plot)
            
                        st.metric(label="Gesamtzahl Sarkome", value=total_sark)
                        st.divider()
            
                        if total_sark > 0:
                            # Gruppierung nach Jahr und Typ
                            grp = df_plot.groupby(["jahr_opdatum", "type_sark"], as_index=False).size()
                            grp.columns = ["jahr_opdatum", "type_sark", "count"]

                            fig = px.bar(
                                grp,
                                x="jahr_opdatum",
                                y="count",
                                color="type_sark",
                                barmode="group",
                                text="count",
                                color_discrete_sequence=COLOR_PALETTE,
                                labels={"type_sark": "Sarkomtyp"}
                            )
            
                            fig.update_traces(
                                textfont_size=16, 
                                textposition='auto',
                                marker_line_width=0
                            )
        
                            fig.update_layout(
                                height=300, 
                                margin=dict(l=10, r=10, t=10, b=10),
                                xaxis_title=None, 
                                yaxis_title=None, 
                                showlegend=True,
                                legend=dict(orientation="h", yanchor="bottom", xanchor="right", x=1),
                                xaxis={"type": "category", "tickfont": {"size": 16}},
                                yaxis={"showticklabels": True, "showgrid": True, "tickfont": {"size": 16}} 
                            )
    
                            st.plotly_chart(fig, use_container_width=True, key="kachel_sarkome_chart", config={'displayModeBar': False})
                        else:
                            st.info("Keine Sarkom-Daten")
                    else:
                        st.error("Spalten fehlen")
                else:
                    st.metric(label="Übersicht Sarkome", value="-")


        # Kachel 3
        with col3.container(border=True):
            st.metric(label="Konversionsrate", value="3.2%", delta="0.5%")
        
        # ================== BEREICH CHURURGISCHE ONKOLOGIE/SARKOME ================== 

       
        
        # ================== Reiter Übersicht Sarkome ================== 
        if "Übersicht Sarkome" in analysen:
            with tabs[analysen.index("Übersicht Sarkome")]:
                if "type_sark" in df_bereich.columns and df_bereich["type_sark"].nunique() > 0:
                    grp = df_bereich.groupby(["jahr_opdatum", "type_sark"], as_index=False).size()
                    grp.columns = ["jahr_opdatum", "type_sark", "count"]

                    fig = px.bar(
                        grp,
                        x="jahr_opdatum",
                        y="count",
                        color="type_sark",
                        barmode="group",
                        text="count",
                        color_discrete_sequence=COLOR_PALETTE,
                        labels={"type_sark": "Sarkomtyp"}
                    )
                    
                    fig.update_traces(
                        textfont_size=16, 
                        textposition='inside'
                    )

                    fig.update_layout(
                        xaxis_title=None, 
                        yaxis_title=None, 
                        xaxis={"type": "category", "tickfont": {"size": 16}}, # Verhindert Zahlensalat auf der X-Achse
                        yaxis={"tickfont": {"size": 16}} 
                    )
                    
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.info("Keine Daten")

        # ================== GRUPPEN ==================
        if "Gruppen (Sarkome/Weichteiltumoren)" in analysen:
            with tabs[analysen.index("Gruppen (Sarkome/Weichteiltumoren)")]:
                if "gruppen_chir_onko_sark" in df_bereich.columns and df_bereich["gruppen_chir_onko_sark"].nunique() > 0:
                    
                    # Filter auf type_sark = '2'
                    df_plot = df_bereich[df_bereich["type_sark"] == 'Sarkom/Weichteiltumor'].copy()

                    if df_plot.empty:
                        st.info("Keine Daten für type_sark = '2'")
                    else:
                        # Gruppieren und count berechnen
                        grp = df_plot.groupby(["jahr_opdatum", "gruppen_chir_onko_sark"]).size().reset_index(name="count")
                        
                        if not grp.empty:
                            fig = px.bar(
                                grp,
                                x="jahr_opdatum",
                                y="count",
                                color="gruppen_chir_onko_sark",
                                barmode="group",
                                text="count",
                                color_discrete_sequence=COLOR_PALETTE,
                                labels={"gruppen_chir_onko_sark": "Sarkomgruppen"}
                            )

                            fig.update_traces(
                                textfont_size=16, 
                                textposition='inside'
                            )

                            fig.update_layout(
                                xaxis_title=None, 
                                yaxis_title=None, 
                                xaxis={"type": "category", "tickfont": {"size": 16}}, # Verhindert Zahlensalat auf der X-Achse
                                yaxis={"tickfont": {"size": 16}} 
                            )
                    
                            st.plotly_chart(fig, use_container_width=True)
                        else:
                            st.info("Keine Gruppendaten")

        # ================== Reiter Übersicht Sarkome ================== 
        #DEBUGGING: um zu schauen, wie die Werte angezeigt werden
        #st.write("DEBUG - Werte in Spalte type_sark:", df_bereich["type_sark"].unique())
        if "HIPEC bei CRS" in analysen:
            with tabs[analysen.index("HIPEC bei CRS")]:
                if "hipec" in df_bereich.columns and df_bereich["hipec"].nunique() > 0:

                    # Filter auf type_sark = '1'
                    df_plot = df_bereich[df_bereich["type_sark"] == 'CRS'].copy()

                    if df_plot.empty:
                        st.info("Keine Daten für type_sark = '1'")
                    else:
                        # Gruppieren und count berechnen
                        grp = df_plot.groupby(["jahr_opdatum", "hipec"]).size().reset_index(name="count")
                        
                        if not grp.empty:
                            fig = px.bar(
                                grp,
                                x="jahr_opdatum",
                                y="count",
                                color="hipec",
                                barmode="group",
                                text="count",
                                color_discrete_sequence=COLOR_PALETTE,
                                labels={"hipec": "HIPEC"}
                            )
                    
                            fig.update_traces(
                                textfont_size=16, 
                                textposition='inside'
                            )

                            fig.update_layout(
                                xaxis_title=None, 
                                yaxis_title=None, 
                                xaxis={"type": "category", "tickfont": {"size": 16}}, # Verhindert Zahlensalat auf der X-Achse
                                yaxis={"tickfont": {"size": 16}} 
                            )
                    
                            st.plotly_chart(fig, use_container_width=True)
                        else:
                            st.info("Keine Daten")

        # ================== GRUPPEN ==================
        if "Lokalisation (Sarkome/Weichteiltumoren)" in analysen:
            with tabs[analysen.index("Lokalisation (Sarkome/Weichteiltumoren)")]:
                if "lokalisation_sark" in df_bereich.columns and df_bereich["lokalisation_sark"].nunique() > 0:
                    
                    # Filter auf typ_sark = '2'
                    df_plot = df_bereich[df_bereich["type_sark"] == 'Sarkom/Weichteiltumor'].copy()

                    if df_plot.empty:
                        st.info("Keine Daten für Sarkom/Weichteiltumor")
                    else:
                        # Gruppieren und count berechnen
                        grp = df_plot.groupby(["jahr_opdatum", "lokalisation_sark"]).size().reset_index(name="count")
                        
                        if not grp.empty:
                            fig = px.bar(
                                grp,
                                x="jahr_opdatum",
                                y="count",
                                color="lokalisation_sark",
                                barmode="group",
                                text="count",
                                color_discrete_sequence=COLOR_PALETTE,
                                labels={"lokalisation_sark": "Lokalisation"}
                            )

                            fig.update_traces(
                                textfont_size=16, 
                                textposition='inside'
                            )

                            fig.update_layout(
                                xaxis_title=None, 
                                yaxis_title=None, 
                                xaxis={"type": "category", "tickfont": {"size": 16}}, # Verhindert Zahlensalat auf der X-Achse
                                yaxis={"tickfont": {"size": 16}} 
                            )
                    
                            st.plotly_chart(fig, use_container_width=True)
                        else:
                            st.info("Keine Daten")
        
        # ================== BEREICH LEBER ==================    
        # ================== GRUPPEN ==================
        if "Gruppen" in analysen:
            with tabs[analysen.index("Gruppen")]:
                if "leber_gruppen" in df_bereich.columns and df_bereich["leber_gruppen"].nunique() > 0:
                    grp = df_bereich.groupby(["jahr_opdatum", "leber_gruppen"], as_index=False).size()
                    grp.columns = ["jahr_opdatum", "leber_gruppen", "count"]

                    fig = px.bar(
                        grp,
                        x="jahr_opdatum",
                        y="count",
                        color="leber_gruppen",
                        barmode="group",
                        text="count",
                        color_discrete_sequence=COLOR_PALETTE,
                        labels={"leber_gruppen": "Lebergruppen"}
                    )

                    fig.update_traces(
                        textfont_size=16, 
                        textposition='inside'
                    )

                    fig.update_layout(
                        xaxis_title=None, 
                        yaxis_title=None, 
                        xaxis={"type": "category", "tickfont": {"size": 16}}, # Verhindert Zahlensalat auf der X-Achse
                        yaxis={"tickfont": {"size": 16}} 
                    )
                    
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.info("Keine Gruppendaten")

        # ================== ZUGANG ==================
        if "Zugang" in analysen:
            with tabs[analysen.index("Zugang")]:
                if "zugang" in df_bereich.columns and df_bereich["zugang"].nunique() > 0:
                    zug = df_bereich.groupby(["jahr_opdatum", "zugang"], as_index=False).size()
                    zug.columns = ["jahr_opdatum", "zugang", "count"]

                    fig = px.bar(
                        zug,
                        x="jahr_opdatum",
                        y="count",
                        color="zugang",
                        barmode="group",
                        text="count",
                        color_discrete_sequence=COLOR_PALETTE,
                        labels={"zugang": "Zugang"}
                    )

                    fig.update_traces(
                        textfont_size=16, 
                        textposition='inside'
                    )

                    fig.update_layout(
                        xaxis_title=None, 
                        yaxis_title=None, 
                        xaxis={"type": "category", "tickfont": {"size": 16}}, # Verhindert Zahlensalat auf der X-Achse
                        yaxis={"tickfont": {"size": 16}} 
                    )
                    
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.info("Keine Zugangsdaten")

        # ================== KOMPLIKATIONEN ==================
        if "Komplikationen" in analysen:
            with tabs[analysen.index("Komplikationen")]:
                if "max_dindo_calc" in df_bereich.columns and df_bereich["max_dindo_calc"].notna().any():
                    d = (
                        df_bereich
                        .dropna(subset=["jahr_opdatum", "max_dindo_calc"])
                        .groupby(["jahr_opdatum", "max_dindo_calc"], as_index=False)
                        .size()
                    )
                    d.columns = ["jahr_opdatum", "dindo", "count"]
                    mat = d.pivot(index="dindo", columns="jahr_opdatum", values="count").fillna(0)

                    fig = px.imshow(
                        mat,
                        text_auto=True,
                        aspect="auto",
                        color_continuous_scale="Greens"
                    )
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.info("Keine Komplikationsdaten")

        # ================== HSM ==================
        if "HSM" in analysen:
            with tabs[analysen.index("HSM")]:
                if df_bereich['hsm'].notna().any():
                    df_hsm = df_bereich.dropna(subset=['hsm','jahr_opdatum']).copy()
                    df_hsm['hsm_label'] = df_hsm['hsm'].astype(str).map({'0':'Nein','1':'Ja','0.0':'Nein','1.0':'Ja'})

                    col1, col2 = st.columns(2)

                    with col1:
                        hsm_jahr = df_hsm.groupby(['jahr_opdatum','hsm_label']).size().reset_index(name='count')
                        fig_hsm = px.bar(
                            hsm_jahr,
                            x='jahr_opdatum',
                            y='count',
                            color='hsm_label',
                            barmode='group',
                            text='count',
                            color_discrete_sequence=COLOR_PALETTE,
                            labels={"hsm_label": "HSM"}
                        )
                        
                        fig.update_layout(
                            xaxis_title=None, 
                            yaxis_title=None, 
                            xaxis={"type": "category", "tickfont": {"size": 16}}, # Verhindert Zahlensalat auf der X-Achse
                            yaxis={"tickfont": {"size": 16}} 
                        )
                        
                        st.plotly_chart(fig_hsm, use_container_width=True)

                    with col2:
                        hsm_bereich = df_hsm.groupby(['bereich','hsm_label']).size().reset_index(name='count')
                        fig_bereich = px.bar(
                            hsm_bereich,
                            x='bereich',
                            y='count',
                            color='hsm_label',
                            barmode='stack',
                            text='count',
                            color_discrete_sequence=COLOR_PALETTE,
                            labels={"hsm_label": "HSM"}
                        )
                        st.plotly_chart(fig_bereich, use_container_width=True)
                else:
                    st.info("Keine HSM-Daten für diesen Bereich")

        # ================== TRENDS ==================
        if "Trends" in analysen:
            with tabs[analysen.index("Trends")]:
                t = df_bereich.groupby(["jahr_opdatum"], as_index=False).size()
                t.columns = ["jahr_opdatum", "count"]

                fig = px.line(
                    t,
                    x="jahr_opdatum",
                    y="count",
                    markers=True,
                    color_discrete_sequence=COLOR_PALETTE,
                )

                
                fig.update_layout(
                    xaxis_title=None, 
                    yaxis_title=None, 
                    xaxis={"type": "category", "tickfont": {"size": 16}}, # Verhindert Zahlensalat auf der X-Achse
                    yaxis={"tickfont": {"size": 16}} 
                )
                st.plotly_chart(fig, use_container_width=True)

        
