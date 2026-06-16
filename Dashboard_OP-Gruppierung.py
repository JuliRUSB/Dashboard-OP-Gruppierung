# ==================================================
# Imports – Bibliotheken laden
# ==================================================

import streamlit as st                           # Streamlit für Web-App
import os                                        # Zugriff auf Umgebungsvariablen (z.B. API-Tokens)
import requests                                  # HTTP-Requests (hier für REDCap API)
import pandas as pd                              # Datenverarbeitung mit DataFrames
# st.write("Pandas-Version:", pd.__version__)
import plotly.express as px                      # Plotly Express für Diagramme
import urllib3                                   # Bibliothek für HTTP-Kommunikation
import plotly.graph_objects as go                # Low-Level-Schnittstelle von Plotly
import streamlit.components.v1 as components     # Modul von Streamlit, mit dem man HTML/JavaScript-Code direkt im Browser ausführen kann


# Warnungen von urllib3 deaktivieren (unsicheres HTTPS)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
# ==================================================

# Konfiguration
API_URL = os.getenv("API_URL")

# ==================================================
# Session State Initialisierung
# ==================================================
if "pdf_figures" not in st.session_state:
    st.session_state.pdf_figures = {}

# ==================================================
# Globale Konstanten und Hilfsfunktionen
# ==================================================
# Reihenfolge der Clavien-Dindo-Grade
DINDO_ORDER = [
    'Grade IIIa', 'Grade IIIa d', 'Grade IIIb', 'Grade IIIb d', 
    'Grade IVa', 'Grade IVa d', 'Grade IVb', 'Grade IVb d', 'Grade V'
]

# Gibt den höchsten Clavien-Dindo-Grad aus zwei Spalten zurück
def get_highest_dindo(row):
    v1 = row['max_dindo_calc']
    v2 = row['max_dindo_calc_surv']
    valid_values = [v for v in [v1, v2] if v in DINDO_ORDER]
    if not valid_values:
        return "Unbekannt"
    return max(valid_values, key=lambda x: DINDO_ORDER.index(x))

# Globale Farbpalette
COLOR_PALETTE = px.colors.qualitative.Safe

# Hilfsfunktion für konsistente Farben
def get_color_map(items):
    """Erstellt ein Farbmapping für eine Liste von Items"""
    unique_items = sorted(set(items))
    colors = COLOR_PALETTE * (len(unique_items) // len(COLOR_PALETTE) + 1)
    return {item: colors[i] for i, item in enumerate(unique_items)}
    
# ==================================================
# Datenexport aus REDCap
# ==================================================
@st.cache_data(ttl=300)  # Ergebnisse werden 5 Minuten gecacht, um wiederholte API-Aufrufe zu vermeiden
def export_redcap_data(api_url):
    projects = [
        {"name": "op_gruppen", "token_var": "tok_op_gruppen"},
        {"name": "kolorektal", "token_var": "tok_kolorektal"}
    ]

    data = {}

    for project in projects:
        token = os.getenv(project["token_var"])

        if not token:
            st.warning(f"Token '{project['token_var']}' fehlt")
            continue

        payload = {
            "token": token,
            "content": "record",
            "format": "json",
            "type": "flat"
        }

        try:
            r = requests.post(api_url, data=payload, timeout=30)
            r.raise_for_status()
            data[project["name"]] = r.json()
        except Exception as e:
            st.error(f"{project['name']} fehlgeschlagen: {e}")

    return data

#def export_redcap_data(api_url):
    #"""Exportiert Daten aus REDCap mit Caching"""
    #API_TOKEN = os.getenv("tok_op_gruppen")
    #if not API_TOKEN:
        #st.error("API Token nicht gefunden. Bitte Umgebungsvariable 'tok_op_gruppen' setzen.")
        #return None
    
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
        'fields[5]': 'gallefistel_isgls',
        'fields[6]': 'gallefistel_isgls_surv',
        'fields[7]': 'reoperation_30d',
        'fields[8]': 'max_dindo_calc',
        'fields[9]': 'max_dindo_calc_surv',
        'fields[10]': 'los_opdatum',
        'fields[11]': 'los_eintritt_austritt',
        'fields[12]': 'type_sark',
        'fields[13]': 'gruppen_chir_onko_sark',
        'fields[14]': 'malignit_t_sark',
        'fields[15]': 'lokalisation_sark',
        'fields[16]': 'hipec',
        'fields[17]': 'anastomosen_crs',
        'fields[18]': 'statistik_dindo_2',
        'fields[19]': 'crs_details',
        'fields[20]': 'kpl_was',
        'fields[21]': 'kpl_was_surv',
        # 'fields[22]': 'gruppen',            #kolorektal
        'rawOrLabel': 'raw',
        'rawOrLabelHeaders': 'raw',
        'exportCheckboxLabel': 'false',
        'exportSurveyFields': 'false',
        'exportDataAccessGroups': 'false',
        'returnFormat': 'json'
    }
    try:
        r = requests.post(api_url, data=data, verify=True, timeout=30)
        r.raise_for_status()
        result = r.json()
        if isinstance(result, dict) and "error" in result:
            st.error(f"REDCap-Fehler: {result['error']}")
            return None
        df = pd.DataFrame(result)
        if df.empty:
            st.warning("Keine Daten zurückgegeben.")
        return df
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
            #'bereich___2': 'BMC',
            #'bereich___3': 'Endokrin',
            'bereich___4': 'Chirurgische Onkologie/Sarkome',
            #'bereich___5': 'Hernien',
            #'bereich___6': 'Kolorektal',
            'bereich___7': 'Leber',
            #'bereich___8': 'Pankreas',
            #'bereich___9': 'Upper-GI'
        }
        # Funktion, um alle markierten Bereiche zu einem String zusammenzufassen
        def get_bereich(row):
            return ', '.join(label for col, label in mapping.items() if row.get(col) == '1') # or 'Nicht angegeben'
        df['bereich'] = df.apply(get_bereich, axis=1)
        df = df.drop(columns=bereich_cols)  # Ursprüngliche Spalten löschen

    # HSM: numerische Codes in Text umwandeln
    hsm_mapping = {
        1: 'Ja',
        0: 'Nein'
    }
    df['hsm'] = pd.to_numeric(df['hsm'], errors='coerce')
    df['hsm'] = df['hsm'].map(hsm_mapping).fillna('Unbekannt')
    
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
    
    # Kolorektal: Spalten mit 'gruppen___' mappen
    leber_gruppen_cols = [c for c in df.columns if c.startswith('leber_gruppen___')]
    if leber_gruppen_cols:
        mapping = {
            'gruppen___1': 'Rektum',
            'gruppen___2': 'Kolonkarzinom',
            'gruppen___3': 'Kolon nicht-onkologisch',
            'gruppen___4': 'Rektopexie',
            'gruppen___5': 'Rektum - watchful waiting',
        }
        # Funktion, um alle markierten Bereiche zu einem String zusammenzufassen
        def get_kolorektal_gruppen(row):
            return ', '.join(label for col, label in mapping.items() if row.get(col) == '1') or 'Nicht angegeben'
        df['kolorektal_gruppen'] = df.apply(get_kolorektal_gruppen, axis=1)
        df = df.drop(columns=kolorektal_gruppen_cols)  # Ursprüngliche Spalten löschen
    
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

    # Malignität: Spalten mit 'malignit_t_sark' mappen
    malignit_t_sark_cols = [c for c in df.columns if c.startswith('malignit_t_sark___')]
    if malignit_t_sark_cols:
        mapping = {
            'malignit_t_sark___1': 'maligne',
            'malignit_t_sark___3': 'intermediate',
            'malignit_t_sark___2': 'andere',
        }
    # Funktion, um alle markierten Bereiche zu einem String zusammenzufassen
        def get_malignit_t_sark(row):
            return ', '.join(label for col, label in mapping.items() if row.get(col) == '1') or 'Nicht angegeben'
        df['malignit_t_sark'] = df.apply(get_malignit_t_sark, axis=1)
        df = df.drop(columns=malignit_t_sark_cols)  # Ursprüngliche Spalten löschen    
    
    # Zugang: numerische Codes in Text umwandeln
    zugang_mapping = {
        1: 'Offen',
        2: 'Laparoskopisch',
        3: 'roboter-assistiert',
        4: 'konvertiert',
        5: 'hybrid (2Höhlen-Eingriffe)'
    }
    if 'zugang' in df.columns:
        df['zugang'] = pd.to_numeric(df['zugang'], errors='coerce')
        df['zugang'] = df['zugang'].map(zugang_mapping).fillna('Unbekannt')

    # Gallefistel_isgls: numerische Codes in Text umwandeln
    gallefistel_isgls_mapping = {
        1: 'Grade A',
        2: 'Grade B',
        3: 'Grade C'
    }
    if 'gallefistel_isgls' in df.columns:
        df['gallefistel_isgls'] = pd.to_numeric(df['gallefistel_isgls'], errors='coerce')
        df['gallefistel_isgls'] = df['gallefistel_isgls'].map(gallefistel_isgls_mapping).fillna('Unbekannt')

     # Gallefistel_isgls_surv: numerische Codes in Text umwandeln
    gallefistel_isgls_surv_mapping = {
        1: 'Grade A',
        2: 'Grade B',
        3: 'Grade C'
    }
    if 'gallefistel_isgls_surv' in df.columns:
        df['gallefistel_isgls_surv'] = pd.to_numeric(df['gallefistel_isgls_surv'], errors='coerce')
        df['gallefistel_isgls_surv'] = df['gallefistel_isgls_surv'].map(gallefistel_isgls_surv_mapping).fillna('Unbekannt')
    
    # Reoperation 30d: numerische Codes in Text umwandeln
    reoperation_30d_mapping = {
        1: 'Ja',
        0: 'Nein'
    }
    if 'reoperation_30d' in df.columns:
        df['reoperation_30d'] = pd.to_numeric(df['reoperation_30d'], errors='coerce')
        df['reoperation_30d'] = df['reoperation_30d'].map(reoperation_30d_mapping).fillna('Unbekannt')
    
    # Typ Sarkom: numerische Codes in Text umwandeln
    type_sark_mapping = {
        1: 'CRS',
        2: 'Sarkom/Weichteiltumor'
    }
    if 'type_sark' in df.columns:
        df['type_sark'] = pd.to_numeric(df['type_sark'], errors='coerce')
        df['type_sark'] = df['type_sark'].map(type_sark_mapping) #.fillna('Unbekannt')
    

    # CRS Dtetails (Für Anastomosen): numerische Codes in Text umwandeln
    crs_details_cols = [c for c in df.columns if c.startswith('crs_details___')]

    if crs_details_cols:
        mapping = {
            'crs_details___10': 'Kolon',
            'crs_details___11': 'Rektum'
        }
    
        def get_crs_details(row):
            return ', '.join(label for col, label in mapping.items() if str(row.get(col)) == '1') or 'Nicht angegeben'
    
        df['crs_details'] = df.apply(get_crs_details, axis=1)
        df = df.drop(columns=crs_details_cols)  # Ursprüngliche Spalten löschen

    # Anastomosen CRS: numerische Codes in Text umwandeln
    anastomosen_crs_cols = [c for c in df.columns if c.startswith('anastomosen_crs___')]
    
    if anastomosen_crs_cols:
        anastomosen_crs_mapping = {
            'anastomosen_crs___0': 'keine',
            'anastomosen_crs___1': 'Dünndarm',
            'anastomosen_crs___2': '>1Dünndarm',
            'anastomosen_crs___3': 'ileocolisch',
            'anastomosen_crs___4': 'rektal',
            'anastomosen_crs___5': 'Kolon-Kolon',
            'anastomosen_crs___6': 'Esophago-Jejunum',
            'anastomosen_crs___7': 'Magen-Jejunum'
        }
    
        def get_anastomosen_crs(row):
            return ', '.join(
                label for col, label in anastomosen_crs_mapping.items()
                if str(row.get(col)) == '1'
            ) or 'Nicht angegeben'
    
        df['anastomosen_crs'] = df.apply(get_anastomosen_crs, axis=1)
        df = df.drop(columns=anastomosen_crs_cols)
    
    # HIPEC: numerische Codes in Text umwandeln
    hipec_mapping = {
        1: 'Ja',
        0: 'Nein'
    }
    if 'hipec' in df.columns:
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
    
    # max_dindo_calc: numerische Codes in Text umwandeln
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
    if 'max_dindo_calc' in df.columns:
        df['max_dindo_calc'] = pd.to_numeric(df['max_dindo_calc'], errors='coerce')
        df['max_dindo_calc'] = df['max_dindo_calc'].map(max_dindo_calc_mapping).fillna('Unbekannt')

    # max_dindo_calc_surv: numerische Codes in Text umwandeln
    max_dindo_calc_surv_mapping = {
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
    if 'max_dindo_calc_surv' in df.columns:
        df['max_dindo_calc_surv'] = pd.to_numeric(df['max_dindo_calc_surv'], errors='coerce')
        df['max_dindo_calc_surv'] = df['max_dindo_calc_surv'].map(max_dindo_calc_surv_mapping).fillna('Unbekannt')
   
    # Numerische Felder für Analyse erstellen
    df['jahr_opdatum'] = df['opdatum'].dt.year.astype('Int64')  # Jahr extrahieren
    # Quartal erstellen: 1, 2, 3 oder 4
    df['quartal_opdatum'] = df['opdatum'].dt.quarter
    # Quartal als "Q1-2026"-Format
    # df['diag_quartal_opdatum'] = df['opdatum'].dt.to_period('Q').astype(str).str.replace(
    #     r'(\d{4})Q(\d)', r'Q\2-\1', regex=True)
    df['diag_quartal_opdatum'] = (
    'Q'
        + df['opdatum'].dt.quarter.astype(str)
        + '-'
        + df['opdatum'].dt.year.astype(str)
    )
    # Quartals-Sortierung als Zahl (für Diagramme)
    df['quartal_sort'] = df['opdatum'].dt.year * 10 + df['opdatum'].dt.quarter
    
    # Zeilen ohne gültiges Datum entfernen
    df = df.dropna(subset=['jahr_opdatum'])
    
    return df

# Figuren-Speicher initialisieren (nur beim ersten Laden der App)
# session_state bleibt über Streamlit-Rerenders hinweg erhalten,
# normale Variablen werden bei jedem Rerender gelöscht
if "pdf_figures" not in st.session_state:
    st.session_state.pdf_figures = {}
if "export_pdf" not in st.session_state:
    st.session_state.export_pdf = False
if "pdf_bytes" not in st.session_state:
    st.session_state.pdf_bytes = None

# ==================================================
# Streamlit App
# ==================================================
# st.set_page_config(page_title="Dashboard Kennzahlen", layout="wide")  # Layout festlegen
# st.title("Dashboard Kennzahlen")

# ==================================================
# Daten laden
# ==================================================
with st.spinner('Lade Daten...'):
     # 1. Daten von der API abrufen
    raw_dict = export_redcap_data(API_URL)
    
    # 2. OP-Gruppen separat verarbeiten
    if raw_dict.get("op_gruppen"):
        df_raw_opgrupp = pd.DataFrame(raw_dict["op_gruppen"])
        df_opgrupp = prepare_data(df_raw_opgrupp)
    else:
        df_opgrupp = pd.DataFrame() # Leerer DataFrame als Fallback
    
    # 3. Kolorektal separat verarbeiten
    if raw_dict.get("kolorektal"):
        df_raw_kolo = pd.DataFrame(raw_dict["kolorektal"])
        df_kolo = prepare_data(df_raw_kolo)
    else:
        df_kolo = pd.DataFrame() # Leerer DataFrame als Fallback

# Fehlerbehandlung: bricht nur ab, wenn wirklich gar keine Daten da sind
if df_opgrupp.empty and df_kolo.empty:
    st.error("Keine Daten verfügbar.")
    st.stop()

# -------- Session State initialisieren --------
# Alle Jahre und Quartale sammeln
# Jahre für OP-Gruppen bestimmen (nur aus der OP-Gruppierung)
if not df_opgrupp.empty and 'jahr_opdatum' in df_opgrupp.columns:
    jahre_opgrupp = sorted(df_opgrupp['jahr_opdatum'].dropna().unique().tolist())
else:
    jahre_opgrupp = []

# Jahre für Kolorektal bestimmen (nur aus der Kolorektal-DB)
if not df_kolo.empty and 'jahr_opdatum' in df_kolo.columns:
    jahre_kolo = sorted(df_kolo['jahr_opdatum'].dropna().unique().tolist())
else:
    jahre_kolo = []

# ==================================================
# Session State verwenden, damit Auswahl zwischen Reloads erhalten bleibt
# ==================================================

# 1. Alle verfügbaren Jahre für die Slider-Grenzen ermitteln
alle_jahre_kombiniert = sorted(list(set(jahre_opgrupp + jahre_kolo)))

if not alle_jahre_kombiniert:
    st.error("Keine Jahresdaten in beiden Datenbanken verfügbar.")
    st.stop()

# 2. Zentralen Session State für die Steuerung initialisieren
if 'selected_jahre' not in st.session_state:
    st.session_state.selected_jahre = alle_jahre_kombiniert

if 'selected_quartale' not in st.session_state:
    st.session_state['selected_quartale'] = [1, 2, 3, 4]

if 'slider_jahr_speicher' not in st.session_state:
    # Setzt den Slider standardmäßig auf das kleinste und größte Jahr aller Daten
    st.session_state['slider_jahr_speicher'] = (alle_jahre_kombiniert[0], alle_jahre_kombiniert[-1])

# Das Standard-Filter-Tupel einmalig beim allerersten Start merken
if 'slider_jahr_speicher' not in st.session_state:
    st.session_state['slider_jahr_speicher'] = (alle_jahre_kombiniert[0], alle_jahre_kombiniert[-1])


# =================================================================#
# Sidebar: Jahr-Range-Slider + Quartal-Buttons + Bereich & Zugang  #
# =================================================================#
with st.sidebar:
    st.header("Filter")

    # Grenzen aus der kombinierten Jahresliste ermitteln
    min_jahr = int(alle_jahre_kombiniert[0])
    max_jahr = int(alle_jahre_kombiniert[-1])

    jahr_range = st.slider(
        "Zeitraum auswählen",
        min_value=min_jahr,
        max_value=max_jahr,
        value=st.session_state.get('slider_jahr_speicher', (min_jahr, max_jahr)),
        key="jahr_slider_widget"
    )
    
    # Zustand des Sliders im Session State merken
    st.session_state['slider_jahr_speicher'] = jahr_range

    selected_quartale = st.pills(
        label="Quartal(e) ab-/auswählen",
        options=[1, 2, 3, 4],
        format_func=lambda x: f"Q{x}",
        selection_mode="multi",
        default=st.session_state.get('selected_quartale', [1, 2, 3, 4]),
        key="pills_selection"
    )
    
    # Update des Session States für Quartale
    st.session_state['selected_quartale'] = selected_quartale

    # --- DATENSTRÖME STRIKT GETRENNT FILTERN ---
    
    # 1. OP-Gruppen filtern
    df_opgrupp_filtered = df_opgrupp[
        (df_opgrupp["jahr_opdatum"] >= jahr_range[0]) &
        (df_opgrupp["jahr_opdatum"] <= jahr_range[1]) &
        (df_opgrupp["quartal_opdatum"].isin(selected_quartale))
    ]

    # 2. Kolorektal filtern
    df_kolo_filtered = df_kolo[
        (df_kolo["jahr_opdatum"] >= jahr_range[0]) &
        (df_kolo["jahr_opdatum"] <= jahr_range[1]) &
        (df_kolo["quartal_opdatum"].isin(selected_quartale))
    ]

    # Anzeige der aktuell gewählten Quartale
    if st.session_state['selected_quartale']:
        anzeige_liste = [f"Q{q}" for q in sorted(st.session_state['selected_quartale'])]
        # st.write(f"Aktuell gewählt: {', '.join(anzeige_liste)}")
    else:
        st.write("Kein Quartal ausgewählt.")


    # =================================================================#
    #                   AKTIVE FILTERUNG DER DATEN:                    #
    #          damit beim updaten der App die Grafiken nur die         #
    #        Jahre/Quartale anzeigen, die vorher gefiltert wurden      #
    # =================================================================#

    # Werte direkt aus dem Session State des Sliders holen mit dem korrekten Widget-Key
    slider_werte = st.session_state.get("jahr_slider_widget", jahr_range)
    start_jahr, end_jahr = slider_werte
    
    # --- 1. FILTERUNG FÜR OP-GRUPPEN ---
    # Filtern nach dem ausgewählten Zeitraum
    df_opgrupp_filtered = df_opgrupp[
        (df_opgrupp['jahr_opdatum'] >= start_jahr) & 
        (df_opgrupp['jahr_opdatum'] <= end_jahr)
    ].copy()
    
    # Filtern nach den ausgewählten Quartalen
    if st.session_state.get('selected_quartale'):
        df_opgrupp_filtered = df_opgrupp_filtered[df_opgrupp_filtered['quartal_opdatum'].isin(st.session_state['selected_quartale'])].copy()
    else:
        df_opgrupp_filtered = df_opgrupp_filtered.iloc[0:0].copy()
    
    
    # --- 2. FILTERUNG FÜR KOLOREKTAL (STRIKT GETRENNT) ---
    # Filtern nach dem ausgewählten Zeitraum
    df_kolo_filtered = df_kolo[
        (df_kolo['jahr_opdatum'] >= start_jahr) & 
        (df_kolo['jahr_opdatum'] <= end_jahr)
    ].copy()
    
    # Filtern nach den ausgewählten Quartalen
    if st.session_state.get('selected_quartale'):
        df_kolo_filtered = df_kolo_filtered[df_kolo_filtered['quartal_opdatum'].isin(st.session_state['selected_quartale'])].copy()
    else:
        df_kolo_filtered = df_kolo_filtered.iloc[0:0].copy()


    st.divider()
    
# -------------------- Daten filtern (Zeit-Filter wirken auf ALLES) --------------------

# ÄNDERUNG 1: Da selected_jahre statisch im State eingefroren war, generieren wir die Liste 
# jetzt dynamisch aus der aktuellen Slider-Position (jahr_range), damit die Filterung reagiert.
start_jahr, end_jahr = jahr_range 
selected_jahre = list(range(int(start_jahr), int(end_jahr) + 1))

selected_quartale = st.session_state.get('selected_quartale', [])

if not selected_jahre or not selected_quartale:
    st.warning("⚠️ Bitte wählen Sie mindestens ein Jahr und ein Quartal aus.")
    st.stop()

# 1. Basis-Filterung nach Zeit für OP-Gruppen (Graphen UND Tabs)
if not df_opgrupp.empty:
    df_opgrupp['jahr_opdatum'] = df_opgrupp['jahr_opdatum'].astype(int)
    df_opgrupp['quartal_opdatum'] = df_opgrupp['quartal_opdatum'].astype(int)

# 1. Basis-Filterung nach Zeit für Kolorektal (Graphen UND Tabs)
if not df_kolo.empty:
    df_kolo['jahr_opdatum'] = df_kolo['jahr_opdatum'].astype(int)
    df_kolo['quartal_opdatum'] = df_kolo['quartal_opdatum'].astype(int)

selected_jahre = list(map(int, selected_jahre))
selected_quartale = list(map(int, selected_quartale))

# 2. Entkoppelung: Basis-Datensätze erstellen
df_opgrupp_base = df_opgrupp[
    df_opgrupp['jahr_opdatum'].isin(selected_jahre) &
    df_opgrupp['quartal_opdatum'].isin(selected_quartale)
].copy()

df_kolo_base = df_kolo[
    df_kolo['jahr_opdatum'].isin(selected_jahre) &
    df_kolo['quartal_opdatum'].isin(selected_quartale)
].copy()

# --- TEIL 1: Filterlogik (nur für die Grafiken in Teil 2) ---

# Kopien für die Visualisierungen in Teil 2, 
# damit die Filter nicht die Detailanalysen in Teil 3 beeinflussen.
df_opgrupp_plots = df_opgrupp_base.copy()
df_kolo_plots = df_kolo_base.copy()

# if 'bereich_filter' in locals() and bereich_filter != "Alle":
#     if 'bereich' in df_opgrupp_plots.columns:
#         df_opgrupp_plots = df_opgrupp_plots[df_opgrupp_plots['bereich'] == bereich_filter]
#     if 'bereich' in df_kolo_plots.columns:
#         df_kolo_plots = df_kolo_plots[df_kolo_plots['bereich'] == bereich_filter]
# 
# if 'zugang_filter' in locals() and zugang_filter != "Alle":
#     if 'zugang' in df_opgrupp_plots.columns:
#         df_opgrupp_plots = df_opgrupp_plots[df_opgrupp_plots['zugang'] == zugang_filter]
#     if 'zugang' in df_kolo_plots.columns:
#         df_kolo_plots = df_kolo_plots[df_kolo_plots['zugang'] == zugang_filter]


# -------------------- TEIL 2: Kennzahlen & Visualisierungen --------------------

st.header("Dashboard Kennzahlen")

# Erstellt zwei Tabs auf der Hauptseite, um die Daten strikt getrennt anzuzeigen
tab_opgrupp, tab_kolo = st.tabs(["OP-Gruppierung", "Kolorektale Chirurgie"])

# =========================================================================
# TAB 1: OP-GRUPPEN
# =========================================================================
with tab_opgrupp:
    col_op1, col_op2, col_op3, col_op4 = st.columns(4)

    with col_op1:
        st.metric("Gesamt Fälle", len(df_opgrupp_plots))

    with col_op2:
        anzahl_bereiche = df_opgrupp_plots['bereich'].nunique() if 'bereich' in df_opgrupp_plots.columns else 0
        st.metric("Bereiche", anzahl_bereiche)

    with col_op3:
        # Zeitraum dynamisch aus den tatsächlichen OP-Gruppen-Daten berechnen
        if not df_opgrupp_plots.empty and 'jahr_opdatum' in df_opgrupp_plots.columns:
            opgrupp_min_j = int(df_opgrupp_plots['jahr_opdatum'].min())
            opgrupp_max_j = int(df_opgrupp_plots['jahr_opdatum'].max())
            opgrupp_jahre_anzahl = opgrupp_max_j - opgrupp_min_j + 1
            opgrupp_quartale_anzahl = df_opgrupp_plots['quartal_opdatum'].nunique()
        else:
            opgrupp_jahre_anzahl = 0
            opgrupp_quartale_anzahl = 0

        st.metric(
            "Zeitraum",
            f"{opgrupp_jahre_anzahl} Jahre, {opgrupp_quartale_anzahl} Quartale"
        )

    st.divider()
    st.header("Fallzahlen OP-Gruppierung")

    if df_opgrupp_plots.empty:
        st.warning("Keine Daten für die gewählten Filter verfügbar.")
    else:
        col_chart_op1, col_chart_op2 = st.columns(2)

        # -------------------- Jahr-Chart OP-Gruppen --------------------
        with col_chart_op1:
            jahr_counts_df = (
                df_opgrupp_plots
                .groupby('jahr_opdatum')
                .size()
                .reset_index(name='count')
            )
            jahr_counts_df['jahr_str'] = jahr_counts_df['jahr_opdatum'].astype(str)

            fig_jahr = px.bar(
                jahr_counts_df,
                x='jahr_str',
                y='count',
                text='count',
                color='jahr_str',
                color_discrete_sequence=COLOR_PALETTE,
                title=None
            )
            fig_jahr.update_traces(textposition='inside', textfont_size=16)
            fig_jahr.update_layout(
                height=400, xaxis_title=None, yaxis_title=None, showlegend=False, autosize=True,
                xaxis={'categoryorder': 'category ascending', 'type': 'category', 'tickfont': {'size': 16}}
            )
            st.plotly_chart(fig_jahr, use_container_width=True)

        # -------------------- Quartals-Chart OP-Gruppen --------------------
        with col_chart_op2:
            q_counts = (
                df_opgrupp_plots
                .groupby(["jahr_opdatum", "quartal_opdatum"], as_index=False)
                .size()
            )
            q_counts.columns = ["jahr_opdatum", "quartal_opdatum", "count"]

            # Chronologische Sortierung beibehalten
            q_counts = q_counts.sort_values(["jahr_opdatum", "quartal_opdatum"]).reset_index(drop=True)

            q_counts["quartal_label"] = (
                "Q" + q_counts["quartal_opdatum"].astype(str)
                + "-" + q_counts["jahr_opdatum"].astype(str)
            )
            quartal_order = q_counts["quartal_label"].tolist()

            fig_quartal = px.bar(
                q_counts,
                x="quartal_label",
                y="count",
                text="count",
                color=q_counts["quartal_opdatum"].astype(str),  # KORREKTUR: Färbt nach Quartal, nicht nach Jahr
                color_discrete_sequence=COLOR_PALETTE,
                category_orders={"quartal_label": quartal_order},
                title=None
            )
            fig_quartal.update_traces(textfont_size=16, textposition="auto", textangle=0)
            fig_quartal.update_layout(
                height=400, xaxis_title=None, yaxis_title=None, showlegend=False,
                xaxis={"type": "category", "tickfont": {"size": 16}}, yaxis={"tickfont": {"size": 16}},
            )

            # Jahres-Trennlinie
            for i in range(len(quartal_order) - 1):
                curr_year = quartal_order[i].split("-")[1]
                next_year = quartal_order[i + 1].split("-")[1]
                if curr_year != next_year:
                    fig_quartal.add_vline(x=i + 0.5, line_width=2, line_dash="dash", line_color="gray")

            st.plotly_chart(fig_quartal, use_container_width=True, config={"displayModeBar": False, "responsive": True})

# =========================================================================
# TAB 2: KOLOREKTAL
# =========================================================================
with tab_kolo:
    col_kolo1, col_kolo2, col_kolo3, col_kolo4 = st.columns(4)

    with col_kolo1:
        st.metric("Gesamt Fälle", len(df_kolo_plots))

    with col_kolo2:
        st.metric("Bereiche", 1)

    with col_kolo3:
        # Zeitraum dynamisch aus den tatsächlichen Kolorektal-Daten berechnen
        if not df_kolo_plots.empty and 'jahr_opdatum' in df_kolo_plots.columns:
            kolo_min_j = int(df_kolo_plots['jahr_opdatum'].min())
            kolo_max_j = int(df_kolo_plots['jahr_opdatum'].max())
            kolo_jahre_anzahl = kolo_max_j - kolo_min_j + 1
            kolo_quartale_anzahl = df_kolo_plots['quartal_opdatum'].nunique()
        else:
            kolo_jahre_anzahl = 0
            kolo_quartale_anzahl = 0

        st.metric(
            "Zeitraum",
            f"{kolo_jahre_anzahl} Jahre, {kolo_quartale_anzahl} Quartale"
        )

    st.divider()
    st.header("Fallzahlen Kolorektale Chirurgie)")

    if df_kolo_plots.empty:
        st.warning("Keine Daten für die gewählten Filter verfügbar.")
    else:
        col_chart_kolo1, col_chart_kolo2 = st.columns(2)

        # -------------------- Jahr-Chart Kolorektal --------------------
        with col_chart_kolo1:
            jahr_counts_df_kolo = (
                df_kolo_plots
                .groupby('jahr_opdatum')
                .size()
                .reset_index(name='count')
            )
            jahr_counts_df_kolo['jahr_str'] = jahr_counts_df_kolo['jahr_opdatum'].astype(str)

            fig_jahr_kolo = px.bar(
                jahr_counts_df_kolo,
                x='jahr_str',
                y='count',
                text='count',
                color='jahr_str',
                color_discrete_sequence=COLOR_PALETTE,
                title=None
            )
            fig_jahr_kolo.update_traces(textposition='inside', textfont_size=16)
            fig_jahr_kolo.update_layout(
                height=400, xaxis_title=None, yaxis_title=None, showlegend=False, autosize=True,
                xaxis={'categoryorder': 'category ascending', 'type': 'category', 'tickfont': {'size': 16}}
            )
            st.plotly_chart(fig_jahr_kolo, use_container_width=True)

        # -------------------- Quartals-Chart Kolorektal --------------------
        with col_chart_kolo2:
            q_counts_kolo = (
                df_kolo_plots
                .groupby(["jahr_opdatum", "quartal_opdatum"], as_index=False)
                .size()
            )
            q_counts_kolo.columns = ["jahr_opdatum", "quartal_opdatum", "count"]

            # Chronologische Sortierung beibehalten
            q_counts_kolo = q_counts_kolo.sort_values(["jahr_opdatum", "quartal_opdatum"]).reset_index(drop=True)

            q_counts_kolo["quartal_label"] = (
                "Q" + q_counts_kolo["quartal_opdatum"].astype(str)
                + "-" + q_counts_kolo["jahr_opdatum"].astype(str)
            )
            quartal_order_kolo = q_counts_kolo["quartal_label"].tolist()

            fig_quartal_kolo = px.bar(
                q_counts_kolo,
                x="quartal_label",
                y="count",
                text="count",
                color=q_counts_kolo["quartal_opdatum"].astype(str),  # KORREKTUR: Färbt nach Quartal, nicht nach Jahr
                color_discrete_sequence=COLOR_PALETTE,
                category_orders={"quartal_label": quartal_order_kolo},
                title=None
            )
            fig_quartal_kolo.update_traces(textfont_size=16, textposition="auto", textangle=0)
            fig_quartal_kolo.update_layout(
                height=400, xaxis_title=None, yaxis_title=None, showlegend=False,
                xaxis={"type": "category", "tickfont": {"size": 16}}, yaxis={"tickfont": {"size": 16}},
            )

            # Jahres-Trennlinie
            for i in range(len(quartal_order_kolo) - 1):
                curr_year = quartal_order_kolo[i].split("-")[1]
                next_year = quartal_order_kolo[i + 1].split("-")[1]
                if curr_year != next_year:
                    fig_quartal_kolo.add_vline(x=i + 0.5, line_width=2, line_dash="dash", line_color="gray")

            st.plotly_chart(fig_quartal_kolo, use_container_width=True, config={"displayModeBar": False, "responsive": True})

st.divider()

# --- TEIL 3: Detailanalysen (Tabs) ---

st.header("Detailanalysen")

# Nur noch die aktiven Bereiche als Liste
BEREICHE = ["Chirurgische Onkologie/Sarkome", "Kolorektale Chirurgie", "Leber"]
bereich_tabs = st.tabs(BEREICHE)

# 3. Schleife starten. Sorgt dafür, dass die Kacheln und Grafiken automatisch auf die richtigen Tabs aufgeteilt werden
for i, bereich in enumerate(BEREICHE):
    with bereich_tabs[i]:
        # LÖSUNG: Direkt auf die korrekte, gefilterte OP-Gruppen-Tabelle zugreifen
        df_bereich = df_opgrupp_base[df_opgrupp_base["bereich"] == bereich]
        
        if df_bereich.empty:
            st.warning("Keine Daten für diesen Bereich")
            continue

        st.markdown('<div class="print-area">', unsafe_allow_html=True)

        if bereich == "Chirurgische Onkologie/Sarkome":
            # Spalten werden hier für jedes Tab frisch oben gestartet
            col1, col2 = st.columns(2)
    
        # ================== ANFANG BEREICH CHURURGISCHE ONKOLOGIE/SARKOME ==================    
        # ================== Kachel 1 "Gesamtzahl Operationen - Onkologie/Sarkome" ==================
        #if bereich == "Chirurgische Onkologie/Sarkome":
            with col1.container(border=True):
                df_plot_ges = df_bereich[df_bereich["type_sark"].notna()].copy()
                total_ops = len(df_plot_ges)
        
                st.metric(label="Gesamtzahl Operationen - Onkologie/Sarkome", value=total_ops)
                st.markdown("<hr style='margin-top: -15px; margin-bottom: 5px; border: none; border-top: 1px solid #ddd;'>", unsafe_allow_html=True)
                
                if total_ops > 0:
                    grp = df_plot_ges.groupby("jahr_opdatum").size().reset_index(name="count")
        
                    fig = px.bar(
                        grp,
                        x="jahr_opdatum",
                        y="count",
                        text="count",
                        color_discrete_sequence=COLOR_PALETTE
                    )
                
                    fig.update_traces(
                        textposition='auto',
                        textangle=0,
                        cliponaxis=False,
                        textfont_size=16, 
                        insidetextfont=dict(size=16),
                        outsidetextfont=dict(size=16),
                        marker_line_width=0
                    )
                
                    fig.update_layout(
                        height=400,  
                        margin=dict(l=10, r=10, t=0, b=10),
                        xaxis_title=None, 
                        yaxis_title=None, 
                        showlegend=False,
                        xaxis={"type": "category", "tickfont": {"size": 16}},
                        yaxis={"showticklabels": True, "showgrid": True, "tickfont": {"size": 16}} 
                    )

                    st.session_state.setdefault("pdf_figures", {}).setdefault(bereich, {})
                    st.session_state["pdf_figures"][bereich]["kachel_sarkome_ges"] = fig
                    
                    st.plotly_chart(fig, use_container_width=True, key=f"kachel_sarkome_ges_{bereich}", config={"displayModeBar": False, "responsive": True})
                else:
                    st.info("Keine Daten für diesen Bereich gefunden.")
    
        # ================== Kachel 2 "Übersicht Operationen nach Sarkomtyp" ==================
        #if bereich == "Chirurgische Onkologie/Sarkome":
            with col2.container(border=True):
                # df_plot = df_bereich[df_bereich["type_sark"].notna()].copy()
                # df_plot = df_bereich.copy()
                df_plot = df_bereich[df_bereich["type_sark"].isin(['CRS', 'Sarkom/Weichteiltumor'])].copy()
                
                total_crs_und_sark = len(df_plot)
        
                st.metric(label="Übersicht Operationen", value=total_crs_und_sark)
                st.markdown("<hr style='margin-top: -15px; margin-bottom: 5px; border: none; border-top: 1px solid #ddd;'>", unsafe_allow_html=True)

                if total_crs_und_sark > 0:

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
                        textposition='auto',
                        textangle=0,
                        cliponaxis=False,
                        textfont_size=16, 
                        insidetextfont=dict(size=16),
                        outsidetextfont=dict(size=16),
                        marker_line_width=0
                    )
        
                    fig.update_layout(
                        height=400,
                        margin=dict(l=10, r=10, t=0, b=10),
                        xaxis_title=None, 
                        yaxis_title=None, 
                        showlegend=True,
                        legend=dict(orientation="h", yanchor="top", xanchor="right", x=0.99),
                        xaxis={"type": "category", "tickfont": {"size": 16}},
                        yaxis={"showticklabels": True, "showgrid": True, "tickfont": {"size": 16}} 
                    )

                    st.session_state.setdefault("pdf_figures", {}).setdefault(bereich, {})
                    st.session_state["pdf_figures"][bereich]["kachel_sarkome_typ"] = fig
                    
                    st.plotly_chart(fig, use_container_width=True, key=f"kachel_sarkome_typ_{bereich}", config={"displayModeBar": False, "responsive": True})
                else:
                    st.info("Keine Sarkom-Daten")
                
                   
        # ================== Kachel 3: HIPEC bei CRS ================== 
        #if bereich == "Chirurgische Onkologie/Sarkome":
            with col1.container(border=True):
               
                # Filter für CRS
                df_plot_crs = df_bereich[(df_bereich["type_sark"] == 'CRS') & (df_bereich["hipec"].notna()) & (df_bereich["hipec"] != "")].copy()
                total_crs = len(df_plot_crs)
                
                st.metric(label="HIPEC bei CRS", value=total_crs)
                # st.divider()
                # verkleinert den Raum oberhalb der Trennlinie
                st.markdown("<hr style='margin-top: -15px; margin-bottom: 5px; border: none; border-top: 1px solid #ddd;'>", unsafe_allow_html=True)
            
                if total_crs > 0:
                    # Gruppierung nach Jahr und HIPEC
                    grp = df_plot_crs.groupby(["jahr_opdatum", "hipec"], as_index=False).size()
                    grp.columns = ["jahr_opdatum", "hipec", "count"]
                
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
                        # 1. Positionierung & Ausrichtung (wo und wie steht der Text?)
                        textposition='auto',
                        textangle=0,            # Erzwingt, dass die Zahlen immer stehen (nicht liegend)
                        cliponaxis=False,       # Verhindert, dass Zahlen am oberen Rand abgeschnitten werden
                        # 2. Schriftgrösse
                        textfont=dict(size=16),
                        #textfont_size=16, 
                        #insidetextfont=dict(size=16),
                        #outsidetextfont=dict(size=16),
                        # 3. Visuelle Details des Balkens selbst
                        marker_line_width=0    # keine Begrenzungslinie
                    )
                
                    fig.update_layout(
                        # autosize=True,
                        height=400,
                        margin=dict(l=10, r=10, t=0, b=10),
                        xaxis_title=None, 
                        yaxis_title=None, 
                        showlegend=True,
                        legend=dict(orientation="h", yanchor="top", xanchor="right", x=0.99), #  y=-0.2,
                        xaxis={"type": "category", "tickfont": {"size": 16}},
                        yaxis={"showticklabels": True, "showgrid": True, "tickfont": {"size": 16}}
                    )

                    st.session_state.setdefault("pdf_figures", {}).setdefault(bereich, {})
                    st.session_state["pdf_figures"][bereich]["kachel_crs_hipec"] = fig
                
                    st.plotly_chart(fig, use_container_width=True, key=f"kachel_crs_hipec_{bereich}", config={"displayModeBar": False, "responsive": True})
                else:
                    st.info("Keine Daten für CRS")       
        
        # ================== Kachel 4: "Clavien-Dindo-Grad >= IIIa in % - HIPEC ja/nein bei CRS ==================
        #if bereich == "Chirurgische Onkologie/Sarkome":
            with col2.container(border=True):
                # FILTER: Nur echte CRS-Fälle behalten, bei denen HIPEC und Clavien-Dindo ausgefüllt sind
                df_plot_crs = df_bereich[df_bereich["type_sark"] == 'CRS'].copy()
                total_crs = len(df_plot_crs)
        
                # Filter auf die exakte Zahl 1, da Radio-Buttons immer als Ganzzahl kommen
                df_plot_dindo = df_plot_crs[df_plot_crs["statistik_dindo_2"] == '1'].copy()
                total_dindo = len(df_plot_dindo)
        
                metrik_prozent = round(total_dindo / total_crs * 100, 1) if total_crs > 0 else 0
        
                st.metric(
                    label="Clavien-Dindo-Grad ≥ IIIa in % - HIPEC bei CRS",
                    value=f"{metrik_prozent} % ({total_dindo} von {total_crs})",
                )
                st.markdown("<hr style='margin-top: -15px; margin-bottom: 5px; border: none; border-top: 1px solid #ddd;'>", unsafe_allow_html=True)
        
                if total_crs > 0:
                    grp = df_plot_dindo.groupby(["jahr_opdatum", "hipec"], as_index=False).size()
                    grp.columns = ["jahr_opdatum", "hipec", "count"]
        
                    grp_gesamt = df_plot_crs.groupby(["jahr_opdatum", "hipec"], as_index=False).size()
                    grp_gesamt.columns = ["jahr_opdatum", "hipec", "count_gesamt"]
        
                    grp = grp_gesamt.merge(grp, on=["jahr_opdatum", "hipec"], how="left")
                    grp["count"] = grp["count"].fillna(0) 
        
                    grp["prozent"] = (grp["count"] / grp["count_gesamt"] * 100).round(1)
        
                    # Zeigt das Label nur an, wenn der Prozentwert grösser als 0 ist
                    grp["text_label"] = grp["prozent"].apply(lambda x: f"{x}%" if x > 0 else "")
        
                    fig = px.bar(
                        grp,
                        x="jahr_opdatum",
                        y="prozent",
                        color="hipec",
                        barmode="group",
                        text="text_label",
                        color_discrete_sequence=COLOR_PALETTE,
                        labels={"hipec": "HIPEC", "prozent": "Anteil in %"},
                    )
        
                    fig.update_traces(
                        textposition='outside',
                        cliponaxis=False,
                        textfont_size=16,
                        insidetextfont=dict(size=16),
                        outsidetextfont=dict(size=16),
                        marker_line_width=0
                    )
        
                    fig.update_layout(
                        height=400,
                        uniformtext_minsize=16,
                        uniformtext_mode='show',
                        bargap=0.1,
                        margin=dict(l=10, r=10, t=30, b=10),
                        xaxis_title=None,
                        yaxis_title=None,
                        showlegend=True,
                        legend=dict(orientation="h", yanchor="top", xanchor="right", x=0.99),
                        xaxis={"type": "category", "tickfont": {"size": 16}},
                        yaxis={"showticklabels": True, "showgrid": True, "tickfont": {"size": 16}, "tick0": 0, "dtick": 10, "range": [0, 100]}
                    )
        
                    st.plotly_chart(fig, use_container_width=True, key=f"kachel_crs_hipec_claviendindo3_pct_{bereich}", config={"displayModeBar": False, "responsive": True})
                else:
                    st.info("Keine Daten für HIPEC")

        # ================== Kachel 5: "Clavien-Dindo-Grad >= IIIa - HIPEC ja/nein bei CRS" ==================
        #if bereich == "Chirurgische Onkologie/Sarkome":
            with col1:
                with st.container(border=True):
                    df_plot_crs = df_bereich[df_bereich["type_sark"] == 'CRS'].copy()
                    total_crs = len(df_plot_crs)
            
                    df_plot_dindo = df_plot_crs[df_plot_crs["statistik_dindo_2"] == '1'].copy()
                    total_dindo = len(df_plot_dindo)
            
                    st.metric(
                        label="Clavien-Dindo-Grad ≥ IIIa - HIPEC bei CRS",
                        value=f"{total_dindo} von {total_crs}",
                    )
                    st.markdown("<hr style='margin-top: -15px; margin-bottom: 5px; border: none; border-top: 1px solid #ddd;'>", unsafe_allow_html=True)
            
                    if total_crs > 0:
                        grp = df_plot_dindo.groupby(["jahr_opdatum", "hipec"], as_index=False).size()
                        grp.columns = ["jahr_opdatum", "hipec", "count"]
            
                        grp_gesamt = df_plot_crs.groupby(["jahr_opdatum", "hipec"], as_index=False).size()
                        grp_gesamt.columns = ["jahr_opdatum", "hipec", "count_gesamt"]
            
                        grp = grp.merge(grp_gesamt, on=["jahr_opdatum", "hipec"], how="left")
            
                        grp["text_label"] = grp.apply(lambda row: f"{row['count']}/{row['count_gesamt']}", axis=1)
            
                        fig = px.bar(
                            grp,
                            x="jahr_opdatum",
                            y="count",
                            color="hipec",
                            barmode="group",
                            text="text_label",
                            color_discrete_sequence=COLOR_PALETTE,
                            labels={"hipec": "HIPEC"},
                        )
            
                        fig.update_traces(
                            textposition='auto',
                            textangle=0,
                            cliponaxis=False,
                            textfont_size=16,
                            insidetextfont=dict(size=16),
                            outsidetextfont=dict(size=16),
                            marker_line_width=0
                        )
            
                        fig.for_each_annotation(lambda a: a.update(text=a.text.split("=")[-1]))
            
                        fig.update_layout(
                            height=400,
                            uniformtext_minsize=16,
                            uniformtext_mode='show',
                            bargap=0.1,
                            margin=dict(l=10, r=10, t=0, b=10),
                            xaxis_title=None,
                            yaxis_title=None,
                            showlegend=True,
                            legend=dict(orientation="h", yanchor="top", xanchor="right", x=0.99),
                            xaxis={"type": "category", "tickfont": {"size": 16}},
                            yaxis={"showticklabels": True, "showgrid": True, "tickfont": {"size": 16}, "tick0": 0, "dtick": 2}
                        )
            
                        st.plotly_chart(fig, use_container_width=True, key=f"kachel_crs_hipec_claviendindo3_abs_{bereich}", config={"displayModeBar": False, "responsive": True})
                    else:
                        st.info("Keine Daten für HIPEC")

             # ================== Kachel 6: "Aufteilung Komplikationen - CRS mit HIPEC" ==================
        #if bereich == "Chirurgische Onkologie/Sarkome":
            with col2:
                if f"expand_{bereich}_k6" not in st.session_state:
                    st.session_state[f"expand_{bereich}_k6"] = False
        
                df_crs_hipec = df_bereich[
                    (df_bereich["type_sark"] == "CRS")
                    & (df_bereich["hipec"] == "Ja")
                ].copy()
                total_crs_hipec = len(df_crs_hipec)
        
                df_crs_hipec_dindo_basis = df_crs_hipec[
                    df_crs_hipec["statistik_dindo_2"] == '1'
                ].copy()
                total_crs_hipec_dindo = len(df_crs_hipec_dindo_basis)
        
                jahr_order = sorted(
                    df_bereich["jahr_opdatum"].dropna().unique().tolist()
                )
        
                if not st.session_state[f"expand_{bereich}_k6"]:
                    if st.button(
                        "𝗔𝘂𝗳𝘁𝗲𝗶𝗹𝘂𝗻𝗴 𝗞𝗼𝗺𝗽𝗹𝗶𝗸𝗮𝘁𝗶𝗼𝗻𝗲𝗻 - 𝗖𝗥𝗦 𝗺𝗶𝘁 𝗛𝗜𝗣𝗘𝗖 ▼ anzeigen",
                        key=f"btn_{bereich}_k6",
                    ):
                        st.session_state[f"expand_{bereich}_k6"] = True
                        st.rerun()
                else:
                    # Kein verschiebendes Spalten-Layout mehr oben!
                    with st.container(border=True):
                        st.metric(
                            label="Aufteilung Komplikationen - CRS mit HIPEC",
                            value=(
                                f"{total_crs_hipec_dindo} von "
                                f"{total_crs_hipec}"
                            ),
                        )
                        st.markdown(
                            "<hr style='margin-top: -15px; margin-bottom: 5px; "
                            "border: none; border-top: 1px solid #ddd;'>",
                            unsafe_allow_html=True,
                        )
        
                        if total_crs_hipec_dindo > 0:
                            df_crs_hipec_dindo_basis["dindo_final_text"] = (
                                df_crs_hipec_dindo_basis.apply(
                                    get_highest_dindo, axis=1
                                )
                            )
        
                            df_crs_hipec_dindo = df_crs_hipec_dindo_basis[
                                df_crs_hipec_dindo_basis[
                                    "dindo_final_text"
                                ].isin(DINDO_ORDER)
                            ].copy()
        
                            grp = (
                                df_crs_hipec_dindo.groupby(
                                    ["jahr_opdatum", "dindo_final_text"],
                                    as_index=False,
                                ).size()
                            )
                            grp.columns = [
                                "jahr_opdatum",
                                "dindo_final_text",
                                "count",
                            ]
                            grp = grp.sort_values("jahr_opdatum")
        
                            fig = px.bar(
                                grp,
                                x="jahr_opdatum",
                                y="count",
                                color="dindo_final_text",
                                barmode="stack",
                                text="count",
                                color_discrete_sequence=COLOR_PALETTE,
                                labels={"jahr_opdatum": "Jahr"},
                                category_orders={
                                    "dindo_final_text": DINDO_ORDER,
                                    "jahr_opdatum": jahr_order,
                                },
                            )
        
                            fig.update_traces(
                                textposition="auto",
                                textangle=0,
                                cliponaxis=False,
                                insidetextanchor="middle",
                                textfont_size=16,
                                insidetextfont=dict(size=16),
                                outsidetextfont=dict(size=16),
                                marker_line_width=0,
                            )
        
                            fig.update_layout(
                                height=345,  
                                bargap=0.1,
                                margin=dict(l=10, r=10, t=4, b=0),
                                xaxis_title=None,
                                yaxis_title=None,
                                showlegend=True,
                                legend_title_text="",
                                legend=dict(
                                    orientation="h",
                                    yanchor="top",
                                    xanchor="right",
                                    x=0.99,
                                ),
                                xaxis={"type": "category", "tickfont": {"size": 16}},
                                yaxis={"showticklabels": True, "showgrid": True, "tickfont": {"size": 16}},
                            )
        
                            st.plotly_chart(fig, use_container_width=True, key=f"kachel_crs_mit_hipec_dindo3_{bereich}", config={"displayModeBar": False, "responsive": True})
                        else:
                            st.info("Keine Fälle mit Grade >= IIIa gefunden.")
        
                        if st.button(
                            "▲ ausblenden", key=f"btn_{bereich}_k6_close"
                        ):
                            st.session_state[f"expand_{bereich}_k6"] = False
                            st.rerun()


        # ================== Kachel 7: "Aufteilung Komplikationen - CRS ohne HIPEC" ==================
        #if bereich == "Chirurgische Onkologie/Sarkome":
            with col1:
                # Zustand initialisieren
                if f"expand_{bereich}_k7" not in st.session_state:
                    st.session_state[f"expand_{bereich}_k7"] = False
    
                # Wenn ausgeblendet: Button allein (ohne Container-Rahmen), damit col2 leer wirkt
                if not st.session_state[f"expand_{bereich}_k7"]:
                    if st.button("𝗔𝘂𝗳𝘁𝗲𝗶𝗹𝘂𝗻𝗴 𝗞𝗼𝗺𝗽𝗹𝗶𝗸𝗮𝘁𝗶𝗼𝗻𝗲𝗻 - 𝗖𝗥𝗦 𝗼𝗵𝗻𝗲 𝗛𝗜𝗣𝗘𝗖 ▼ anzeigen", key=f"btn_{bereich}_k7"):
                        st.session_state[f"expand_{bereich}_k7"] = True
                        st.rerun()
                else:
                    # Wenn eingeblendet: Button IM Container oben rechts
                    with st.container(border=True):
    
                        required_cols = {"jahr_opdatum", "hipec", "statistik_dindo_2", "type_sark", "max_dindo_calc", "max_dindo_calc_surv"}
                
                        if required_cols.issubset(df_bereich.columns):
            
                            # CRS und HIPEC = ja filtern
                            df_plot_all = df_bereich[(df_bereich["type_sark"] == "CRS") & (df_bereich["hipec"] == "Nein")].copy()
                            total_crs_ohne_hipec = len(df_plot_all)
                    
                            # 1. Wir definieren die Hierarchie (Wichtig für den Vergleich)
                            dindo_order = [
                                'Grade IIIa', 'Grade IIIa d', 'Grade IIIb', 'Grade IIIb d', 
                                'Grade IVa', 'Grade IVa d', 'Grade IVb', 'Grade IVb d', 'Grade V'
                            ]
            
                            # 2. Funktion um den höheren Grad aus den zwei Text-Spalten zu wählen
                            def get_highest_dindo(row):
                                v1 = row['max_dindo_calc']
                                v2 = row['max_dindo_calc_surv']
                                # Nur Werte berücksichtigen, die in unserer Liste oben stehen
                                valid_values = [v for v in [v1, v2] if v in dindo_order]
                                if not valid_values:
                                    return "Unbekannt"
                                # Den Wert mit dem höchsten Index in dindo_order zurückgeben
                                return max(valid_values, key=lambda x: dindo_order.index(x))
            
                            df_plot_all["dindo_final_text"] = df_plot_all.apply(get_highest_dindo, axis=1)
            
                            # 3. Nur Fälle mit Dindo >= IIIa laut Filter
                            df_plot = df_plot_all[df_plot_all["statistik_dindo_2"] == '1'].copy()
                            
                            # ZUSÄTZLICHER SICHERHEITSCHECK: "Keine Komplikation" und "Unbekannt" rauswerfen
                            df_plot = df_plot[df_plot["dindo_final_text"].isin(dindo_order)]
                            
                            total_kompl = len(df_plot)
                            
                            st.metric(
                                label="Aufteilung Komplikationen - CRS ohne HIPEC", 
                                value=f"{total_kompl} von {total_crs_ohne_hipec}",
                            )
                            # st.divider()
                            # verkleinert den Raum oberhalb der Trennlinie
                            st.markdown("<hr style='margin-top: -15px; margin-bottom: 5px; border: none; border-top: 1px solid #ddd;'>", unsafe_allow_html=True)
                            
                            if not df_plot.empty:
                                grp = df_plot.groupby(["jahr_opdatum", "dindo_final_text"], as_index=False).size()
                                grp.columns = ["jahr_opdatum", "dindo_final_text", "count"]
                                
                                # Jahre sortieren
                                grp = grp.sort_values("jahr_opdatum")
                                jahr_order = grp["jahr_opdatum"].unique().tolist()
                    
                                fig = px.bar(
                                    grp,
                                    x="jahr_opdatum",
                                    y="count",
                                    color="dindo_final_text",
                                    barmode="stack",
                                    text="count",
                                    color_discrete_sequence=COLOR_PALETTE,
                                    labels={"jahr_opdatum": "Jahr", "dindo_final_text": "Dindo-Grad"},
                                    category_orders={"dindo_final_text": dindo_order, "jahr_opdatum": jahr_order} 
                                )
                    
                                fig.update_traces(
                                    # 1. Positionierung & Ausrichtung (wo und wie steht der Text?)
                                    textposition='auto',
                                    textangle=0,                # Erzwingt, dass die Zahlen immer stehen (nicht liegend)
                                    cliponaxis=False,           # Verhindert, dass Zahlen am oberen Rand abgeschnitten werden
                                    insidetextanchor='middle',  # Zentriert die Zahl im Segment
                                    # 2. Schriftgrösse
                                    textfont_size=16, 
                                    insidetextfont=dict(size=16),
                                    outsidetextfont=dict(size=16),
                                    # 3. Visuelle Details des Balkens selbst
                                    marker_line_width=0         # keine Begrenzungslinie
                                )
                                
                                fig.update_layout(
                                    height=400,
                                    uniformtext_minsize=14,     # Verhindert, dass Zahlen bei Platzmangel verschwinden
                                    uniformtext_mode='hide',    # Versteckt Text nur, wenn er absolut nicht passt
                                    bargap=0.1,
                                    margin=dict(l=10, r=10, t=0, b=10),
                                    xaxis_title=None,
                                    yaxis_title=None,
                                    showlegend=True,
                                    legend_title_text="",
                                    legend=dict(orientation="h", yanchor="top", xanchor="right", x=0.99), # y=-0.2, 
                                    xaxis={"type": "category", "tickfont": {"size": 16}},
                                    yaxis={"showticklabels": True, "showgrid": True, "tickfont": {"size": 16}}
                                )
                    
                                st.plotly_chart(fig, use_container_width=True, key=f"kachel7_{bereich}_final", config={"displayModeBar": False, "responsive": True})
                            else:
                                st.info("Keine validen Grade >= IIIa gefunden.")
                        else:
                            st.error("Spalten fehlen")

                        if st.button("▲ ausblenden", key=f"btn_{bereich}_k7_close"):
                            st.session_state[f"expand_{bereich}_k7"] = False
                            st.rerun()

        # ================== Kachel 8: "Anastomoseinsuffizienz - CRS (Kolon und Rektum)" ================== 
        #if bereich == "Chirurgische Onkologie/Sarkome":
            with col2:
                # Zustand initialisieren
                if f"expand_{bereich}_k8" not in st.session_state:
                    st.session_state[f"expand_{bereich}_k8"] = False
    
                # Wenn ausgeblendet: Button allein (ohne Container-Rahmen), damit col2 leer wirkt
                if not st.session_state[f"expand_{bereich}_k8"]:
                    if st.button("𝗔𝗻𝗮𝘀𝘁𝗼𝗺𝗼𝘀𝗲𝗻𝗶𝗻𝘀𝘂𝗳𝗳𝗶𝘇𝗶𝗲𝗻𝘇𝗲𝗻 - 𝗖𝗥𝗦 (𝗞𝗼𝗹𝗼𝗻 𝘂𝗻𝗱 𝗥𝗲𝗸𝘁𝘂𝗺) ▼ anzeigen", key=f"btn_{bereich}_k8"):
                        st.session_state[f"expand_{bereich}_k8"] = True
                        st.rerun()
                else:
                    # Wenn eingeblendet: Button IM Container oben rechts
                    with st.container(border=True):
    
                        required_cols = {"crs_details", "anastomosen_crs", "jahr_opdatum", "kpl_was_surv", "kpl_was"}
                        if required_cols.issubset(df_bereich.columns):
                    
                            # Filter auf Kolon/Rektum und gültige Anastomosen
                            df_anastomosen = df_bereich[
                                (df_bereich["crs_details"].str.contains("Kolon|Rektum", na=False)) &
                                ((df_bereich["anastomosen_crs"] != "Nicht angegeben") & (df_bereich["anastomosen_crs"] != "keine"))
                            ].copy()
                    
                            # Nur Fälle mit Anastomoseninsuffizienz
                            df_insuff = df_anastomosen[
                                df_anastomosen["kpl_was_surv"].fillna("").str.contains("Anastomoseninsuffizienz", case=False, na=False) |
                                df_anastomosen["kpl_was"].fillna("").str.contains("Anastomoseninsuffizienz", case=False, na=False)
                            ].copy()
            
                            total_anastomosen = len(df_anastomosen)
                            total_insuff = len(df_insuff)
                            st.metric(
                                label="Anastomoseninsuffizienzen - CRS (Kolon und Rektum)",
                                value=f"{total_insuff} von {total_anastomosen}"
                            )
                            # st.divider()
                            # verkleinert den Raum oberhalb der Trennlinie
                            st.markdown("<hr style='margin-top: -15px; margin-bottom: 5px; border: none; border-top: 1px solid #ddd;'>", unsafe_allow_html=True)
                    
                            if total_insuff > 0:
                                grp = df_insuff.groupby(["jahr_opdatum"], as_index=False).size()
                                grp.columns = ["jahr_opdatum", "count"]
                    
                                fig = px.bar(
                                    grp,
                                    x="jahr_opdatum",
                                    y="count",
                                    # color="anastomosen_crs",
                                    text="count",
                                    color_discrete_sequence=COLOR_PALETTE,
                                    labels={"anastomosen_crs": "Anastomosen"}
                                )
                    
                                fig.update_traces(
                                    # 1. Positionierung & Ausrichtung (wo und wie steht der Text?)
                                    textposition='auto',
                                    textangle=0,                # Erzwingt, dass die Zahlen immer stehen (nicht liegend)
                                    cliponaxis=False,           # Verhindert, dass Zahlen am oberen Rand abgeschnitten werden
                                    # 2. Schriftgrösse
                                    textfont_size=16, 
                                    insidetextfont=dict(size=16),
                                    outsidetextfont=dict(size=16),
                                    # 3. Visuelle Details des Balkens selbst
                                    marker_line_width=0         # keine Begrenzungslinie
                                )
                    
                                fig.update_layout(
                                    height=400,
                                    barmode="group",
                                    margin=dict(l=10, r=10, t=0, b=10),
                                    xaxis_title=None,
                                    yaxis_title=None,
                                    showlegend=False,
                                    # legend=dict(orientation="h", yanchor="top", y=-0.2, xanchor="right", x=0.99),
                                    xaxis={"type": "category", "tickfont": {"size": 16}},
                                    yaxis={"showticklabels": True, "showgrid": True, "tickfont": {"size": 16}, "dtick": 1}
                                )
                    
                                st.plotly_chart(fig, use_container_width=True, key=f"kachel8_{bereich}", config={"displayModeBar": False, "responsive": True})
                            else:
                                st.info("Keine Anastomoseninsuffizienzen vorhanden")
                        else:
                            st.error("Spalten fehlen")

                        if st.button("▲ ausblenden", key=f"btn_{bereich}_k8_close"):
                            st.session_state[f"expand_{bereich}_k8"] = False
                            st.rerun()

        # ================== Kachel 9: "Aufenthaltsdauer - CRS mit HIPEC" ==================       
        #if bereich == "Chirurgische Onkologie/Sarkome":
            with col1.container(border=True):
                required_cols = {"los_opdatum", "type_sark", "jahr_opdatum", "hipec"}
                if required_cols.issubset(df_bereich.columns):
                    df_los = df_bereich[
                        (df_bereich["type_sark"] == "CRS") & (df_bereich["hipec"] == "Ja")].copy()
                    df_los["los_opdatum"] = pd.to_numeric(df_los["los_opdatum"], errors='coerce')
                    df_los = df_los.dropna(subset=["los_opdatum"])
                    total_crs_und_hipec = len(df_los)
                    st.metric(label="Aufenthaltsdauer - CRS mit HIPEC", value=total_crs_und_hipec)
                    # st.divider()
                    # verkleinert den Raum oberhalb der Trennlinie
                    st.markdown("<hr style='margin-top: -15px; margin-bottom: 5px; border: none; border-top: 1px solid #ddd;'>", unsafe_allow_html=True)
            
                    if total_crs_und_hipec > 0:
                        # Aggregation nach Jahr UND hipec
                        grp = df_los.groupby(["jahr_opdatum"], as_index=False)["los_opdatum"].agg(
                            Mittelwert="mean",
                            Median="median",
                            Minimum="min",
                            Maximum="max"
                        )
            
                        # Balkendiagramm für Mittelwert
                        fig = px.bar(
                            grp,
                            x="jahr_opdatum",
                            y="Mittelwert",
                            text="Mittelwert",
                            color_discrete_sequence=COLOR_PALETTE,
                            labels={"Mittelwert": "Tage", "jahr_opdatum": "Jahr"}
                        )
            
                        fig.update_traces(
                            # 1. Positionierung & Ausrichtung (wo und wie steht der Text?)
                            textposition='auto',
                            textangle=0,                # Erzwingt, dass die Zahlen immer stehen (nicht liegend)
                            cliponaxis=False,           # Verhindert, dass Zahlen am oberen Rand abgeschnitten werden
                            insidetextanchor='middle',  # Zentriert die Zahl im Segment
                            # 2. Schriftgrösse etc.
                            textfont_size=16, 
                            insidetextfont=dict(size=16),
                            outsidetextfont=dict(size=16),
                            texttemplate='%{text:.2f}',
                            # 3. Visuelle Details des Balkens selbst
                            marker_line_width=0         # keine Begrenzungslinie
                        )
            
                        # Linien für Median, Min, Max
                        fig.add_trace(go.Scatter(
                            x=grp["jahr_opdatum"],
                            y=grp["Median"],
                            mode="lines+markers",
                            name="Median",
                            line=dict(color="green", dash="dash"),
                            marker=dict(size=8)
                        ))
                        fig.add_trace(go.Scatter(
                            x=grp["jahr_opdatum"],
                            y=grp["Minimum"],
                            mode="lines+markers",
                            name="Minimum",
                            line=dict(color="red", dash="dot"),
                            marker=dict(size=8)
                        ))
                        fig.add_trace(go.Scatter(
                            x=grp["jahr_opdatum"],
                            y=grp["Maximum"],
                            mode="lines+markers",
                            name="Maximum",
                            line=dict(color="blue", dash="dot"),
                            marker=dict(size=8)
                        ))
            
                        fig.update_layout(
                            height=400,
                            margin=dict(l=10, r=10, t=10, b=10),
                            xaxis_title=None,
                            yaxis_title=None,
                            legend=dict(orientation="h", yanchor="top", xanchor="right", x=0.99),
                            xaxis={"type": "category", "tickfont": {"size": 16}},
                            yaxis={"showticklabels": True, "showgrid": True, "tickfont": {"size": 16}},
                        )
            
                        st.plotly_chart(fig, use_container_width=True, key=f"kachel16_{bereich}", config={"displayModeBar": False, "responsive": True})
                    else:
                        st.info("Keine Daten für Sarkome/Weichteiltumore ohne Knochen")
                else:
                    st.error("Spalten fehlen")

        # ================== Kachel 10: "Aufenthaltsdauer - CRS ohne HIPEC" ==================       
        #if bereich == "Chirurgische Onkologie/Sarkome":
            with col2.container(border=True):
                required_cols = {"los_opdatum", "type_sark", "jahr_opdatum", "hipec"}
                if required_cols.issubset(df_bereich.columns):
                    df_los = df_bereich[(df_bereich["type_sark"] == "CRS") & (df_bereich["hipec"] == "Nein")].copy()
                    df_los["los_opdatum"] = pd.to_numeric(df_los["los_opdatum"], errors='coerce')
                    df_los = df_los.dropna(subset=["los_opdatum"])
                    total_crs_ohne_hipec = len(df_los)
                    st.metric(label="Aufenthaltsdauer - CRS ohne HIPEC", value=total_crs_ohne_hipec)
                    # st.divider()
                    # verkleinert den Raum oberhalb der Trennlinie
                    st.markdown("<hr style='margin-top: -15px; margin-bottom: 5px; border: none; border-top: 1px solid #ddd;'>", unsafe_allow_html=True)
            
                    if total_crs_ohne_hipec > 0:
                        # Aggregation nach Jahr UND hipec
                        grp = df_los.groupby(["jahr_opdatum"], as_index=False)["los_opdatum"].agg(
                            Mittelwert="mean",
                            Median="median",
                            Minimum="min",
                            Maximum="max"
                        )
            
                        # Balkendiagramm für Mittelwert
                        fig = px.bar(
                            grp,
                            x="jahr_opdatum",
                            y="Mittelwert",
                            text="Mittelwert",
                            color_discrete_sequence=COLOR_PALETTE,
                            labels={"Mittelwert": "Tage", "jahr_opdatum": "Jahr"}
                        )
            
                        fig.update_traces(
                            # 1. Positionierung & Ausrichtung (wo und wie steht der Text?)
                            textposition='auto',
                            textangle=0,                # Erzwingt, dass die Zahlen immer stehen (nicht liegend)
                            cliponaxis=False,           # Verhindert, dass Zahlen am oberen Rand abgeschnitten werden
                            insidetextanchor='middle',  # Zentriert die Zahl im Segment
                            # 2. Schriftgrösse etc.
                            textfont_size=16, 
                            insidetextfont=dict(size=16),
                            outsidetextfont=dict(size=16),
                            texttemplate='%{text:.2f}',
                            # 3. Visuelle Details des Balkens selbst
                            marker_line_width=0         # keine Begrenzungslinie
                        )
            
                        # Linien für Median, Min, Max
                        fig.add_trace(go.Scatter(
                            x=grp["jahr_opdatum"],
                            y=grp["Median"],
                            mode="lines+markers",
                            name="Median",
                            line=dict(color="green", dash="dash"),
                            marker=dict(size=8)
                        ))
                        fig.add_trace(go.Scatter(
                            x=grp["jahr_opdatum"],
                            y=grp["Minimum"],
                            mode="lines+markers",
                            name="Minimum",
                            line=dict(color="red", dash="dot"),
                            marker=dict(size=8)
                        ))
                        fig.add_trace(go.Scatter(
                            x=grp["jahr_opdatum"],
                            y=grp["Maximum"],
                            mode="lines+markers",
                            name="Maximum",
                            line=dict(color="blue", dash="dot"),
                            marker=dict(size=8)
                        ))
            
                        fig.update_layout(
                            height=400,
                            margin=dict(l=10, r=10, t=10, b=10),
                            xaxis_title=None,
                            yaxis_title=None,
                            xaxis={"type": "category", "tickfont": {"size": 16}},
                            yaxis={"showticklabels": True, "showgrid": True, "tickfont": {"size": 16}},
                            legend=dict(orientation="h", yanchor="top", xanchor="right", x=0.99)
                        )
            
                        st.plotly_chart(fig, use_container_width=True, key=f"kachel_los_crs_ohne_hipec_{bereich}", config={'displayModeBar': False})
                    else:
                        st.info("Keine Daten für Sarkome/Weichteiltumore ohne Knochen")
                else:
                    st.error("Spalten fehlen")    

        # ================== Kachel 11: "Gruppe - Sarkome/Weichteiltumoren" ==================
        #if bereich == "Chirurgische Onkologie/Sarkome":
            with col1.container(border=True):
                # if "Gruppen (Sarkome/Weichteiltumoren)" in analysen:
                # Check auf Spalten
                required_cols = {"type_sark", "jahr_opdatum", "gruppen_chir_onko_sark"}
                if required_cols.issubset(df_bereich.columns):
                
                    # Filter für Sarkom/Weichteiltumor mit knochen
                    df_plot = df_bereich[df_bereich["type_sark"] == 'Sarkom/Weichteiltumor'].copy()
                    total_sark_weichteil = len(df_plot)
                
                    st.metric(label="Gruppe - Sarkome/Weichteiltumoren", value=total_sark_weichteil) 
                    # st.divider()
                    # verkleinert den Raum oberhalb der Trennlinie
                    st.markdown("<hr style='margin-top: -15px; margin-bottom: 5px; border: none; border-top: 1px solid #ddd;'>", unsafe_allow_html=True)
                
                    if total_sark_weichteil > 0:
                        # Gruppierung nach Jahr und Sarkomgruppe
                        grp = df_plot.groupby(["jahr_opdatum", "gruppen_chir_onko_sark"], as_index=False).size()
                        grp.columns = ["jahr_opdatum", "gruppen_chir_onko_sark", "count"]
    
                        # Schwellenwert: ab welcher Balkenhöhe die Zahl reinpasst
                        threshold = grp["count"].max() * 0.15
    
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
                            # 1. Positionierung & Ausrichtung (wo und wie steht der Text?)
                            textposition='auto',
                            textangle=0,                # Erzwingt, dass die Zahlen immer stehen (nicht liegend)
                            cliponaxis=False,           # Verhindert, dass Zahlen am oberen Rand abgeschnitten werden
                            # 2. Schriftgrösse etc.
                            textfont_size=16, 
                            insidetextfont=dict(size=16),
                            outsidetextfont=dict(size=16),
                            # 3. Visuelle Details des Balkens selbst
                            marker_line_width=0         # keine Begrenzungslinie
                        )
    
                        # Pro Balken: textposition basierend auf Wert setzen
                        for trace in fig.data:
                            positions = []
                            for val in trace.y:
                                if val >= threshold:
                                    positions.append('inside')
                                else:
                                    positions.append('outside')
                            trace.textposition = positions
                    
                        fig.update_layout(
                            autosize=True,
                            height=None, 
                            # ERZWINGT 16px: Wenn 16px nicht in den Balken passen, schiebt Plotly die Zahl automatisch nach draussen.
                            margin=dict(l=10, r=10, t=0, b=0),
                            xaxis_title=None, 
                            yaxis_title=None, 
                            showlegend=True,
                            legend=dict(orientation="h", yanchor="top", xanchor="right", x=0.96),
                            xaxis={"type": "category", "tickfont": {"size": 16}},
                            yaxis={"showticklabels": True, "showgrid": True, "tickfont": {"size": 16}} 
                        )
                    
                        st.plotly_chart(fig, use_container_width=True, key=f"kachel9_{bereich}", config={"displayModeBar": False, "responsive": True})
                    else:
                        st.info("Keine Gruppendaten")
                else:
                    st.error("Spalten fehlen")
        
        # ================== Kachel 12: "Lokalisation - Weichteiltumoren" ==================
        #if bereich == "Chirurgische Onkologie/Sarkome":
            with col2.container(border=True):
                # if "Lokalisation (Sarkome/Weichteiltumoren)" in analysen:
                # Check auf Spalten
                required_cols = {"type_sark", "jahr_opdatum", "lokalisation_sark", "gruppen_chir_onko_sark"}
                if required_cols.issubset(df_bereich.columns):
                
                    # Filter für Sarkom/Weichteiltumor ohne Knochen
                    df_plot = df_bereich[(df_bereich["type_sark"] == "Sarkom/Weichteiltumor") & (df_bereich["gruppen_chir_onko_sark"] != "Knochen")].copy()
                    total_weichteil = len(df_plot)
                
                    st.metric(label="Lokalisation Weichteiltumoren", value=f"{total_weichteil} von {total_sark_weichteil}")
                    # st.divider()
                    # verkleinert den Raum oberhalb der Trennlinie
                    st.markdown("<hr style='margin-top: -15px; margin-bottom: 5px; border: none; border-top: 1px solid #ddd;'>", unsafe_allow_html=True)
                
                    if total_weichteil > 0:
                        # Gruppierung nach Jahr und Lokalisation
                        grp = df_plot.groupby(["jahr_opdatum", "lokalisation_sark"], as_index=False).size()
                        grp.columns = ["jahr_opdatum", "lokalisation_sark", "count"]
                    
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
                            # 1. Positionierung & Ausrichtung (wo und wie steht der Text?)
                            textposition='auto',
                            textangle=0,                # Erzwingt, dass die Zahlen immer stehen (nicht liegend)
                            cliponaxis=False,           # Verhindert, dass Zahlen am oberen Rand abgeschnitten werden
                            # 2. Schriftgrösse etc.
                            textfont_size=16, 
                            insidetextfont=dict(size=16),
                            outsidetextfont=dict(size=16),
                            # 3. Visuelle Details des Balkens selbst
                            marker_line_width=0         # keine Begrenzungslinie
                        )
                    
                        fig.update_layout(
                            autosize=True,
                            height=None, 
                            margin=dict(l=10, r=10, t=0, b=10),
                            xaxis_title=None, 
                            yaxis_title=None, 
                            showlegend=True,
                            legend=dict(orientation="h", yanchor="top", xanchor="right", x=0.99),
                            xaxis={"type": "category", "tickfont": {"size": 16}},
                            yaxis={"showticklabels": True, "showgrid": True, "tickfont": {"size": 16}} 
                        )
                    
                        st.plotly_chart(fig, use_container_width=True, key=f"kachel10_{bereich}", config={"displayModeBar": False, "responsive": True})
                    else:
                        st.info("Keine Daten für Sarkom/Weichteiltumor")
                else:
                    st.error("Spalten fehlen")
        
        # ================== Kachel 13: "Sarkomzentrum Weichteiltumoren /GIST - maligne und intermediate" ==================
        #if bereich == "Chirurgische Onkologie/Sarkome":
            with col1.container(border=True):
                required_cols = {"type_sark", "jahr_opdatum", "lokalisation_sark", "gruppen_chir_onko_sark", "malignit_t_sark"}
                if required_cols.issubset(df_bereich.columns):
    
                    # Filter: nur maligne + intermediate (alles ausser "andere") und ohne Knochen
                    df_plot = df_bereich[(df_bereich["type_sark"] == "Sarkom/Weichteiltumor") & (df_bereich["malignit_t_sark"] != "andere") & ((df_bereich["gruppen_chir_onko_sark"] != "Knochen") & (df_bereich["gruppen_chir_onko_sark"] != "Andere Malignome"))].copy()
                    total_malign = len(df_plot)
    
                    st.metric(label="Sarkomzentrum - Weichteiltumoren", value=total_malign)
                    # st.divider()
                    # verkleinert den Raum oberhalb der Trennlinie
                    st.markdown("<hr style='margin-top: -15px; margin-bottom: 5px; border: none; border-top: 1px solid #ddd;'>", unsafe_allow_html=True)
    
                    if total_malign > 0:
                        # Gruppierung nach Jahr und Lokalisation
                        grp = (
                            df_plot
                            .groupby(["jahr_opdatum", "lokalisation_sark"], as_index=False)
                            .size()
                        )
                        grp.columns = ["jahr_opdatum", "lokalisation_sark", "count"]
    
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
                            # 1. Positionierung & Ausrichtung (wo und wie steht der Text?)
                            textposition='auto',
                            textangle=0,                # Erzwingt, dass die Zahlen immer stehen (nicht liegend)
                            cliponaxis=False,           # Verhindert, dass Zahlen am oberen Rand abgeschnitten werden
                            # 2. Schriftgrösse etc.
                            textfont_size=16, 
                            insidetextfont=dict(size=16),
                            outsidetextfont=dict(size=16),
                            # 3. Visuelle Details des Balkens selbst
                            marker_line_width=0         # keine Begrenzungslinie
                        )
    
                        fig.update_layout(
                            autosize=True,
                            height=None,
                            margin=dict(l=10, r=10, t=0, b=10),
                            xaxis_title=None,
                            yaxis_title=None,
                            showlegend=True,
                            legend=dict(orientation="h", yanchor="top", xanchor="right", x=0.99),
                            xaxis={"type": "category", "tickfont": {"size": 16}},
                            yaxis={"showticklabels": True, "showgrid": True, "tickfont": {"size": 16}}
                        )
    
                        st.plotly_chart(fig, use_container_width=True, key=f"kachel11_{bereich}", config={"displayModeBar": False, "responsive": True})
                    else:
                        st.info("Keine Daten für Malignität")
                else:
                    st.error("Spalten fehlen")     
        
        # ================== Kachel 14: "Clavien-Dindo-Grad >= IIIa - Lokalisation Weichteiltumoren" ==================
        #if bereich == "Chirurgische Onkologie/Sarkome":
            with col2.container(border=True):
                # if "Lokalisation (Sarkome/Weichteiltumoren)" in analysen:
                # Check auf Spalten
                required_cols = {"jahr_opdatum", "lokalisation_sark", "statistik_dindo_2", "type_sark"}
                if required_cols.issubset(df_bereich.columns):
    
                    # Filter für Sarkom/Weichteiltumor ohne Knochen
                    df_plot_all = df_bereich[(df_bereich["type_sark"] == "Sarkom/Weichteiltumor") & (df_bereich["gruppen_chir_onko_sark"] != "Knochen")].copy()
                    total_weichteil = len(df_plot_all)
    
                    # Dindo ≥ IIIa
                    df_plot = df_plot_all[df_plot_all["statistik_dindo_2"] == '1'].copy()
                    total_dindo = len(df_plot)
    
                    st.metric(
                        label="Clavien-Dindo-Grad ≥ IIIa - Lokalisation Weichteiltumoren", 
                        value=f"{total_dindo} von {total_weichteil}",
                    )
                    # st.divider()
                    # verkleinert den Raum oberhalb der Trennlinie
                    st.markdown("<hr style='margin-top: -15px; margin-bottom: 5px; border: none; border-top: 1px solid #ddd;'>", unsafe_allow_html=True)
                    
                    if total_dindo > 0:
                        # Gruppierung nach Jahr, Lokalisation (nur Komplikationen >= IIIa)
                        grp = df_plot.groupby(
                            ["jahr_opdatum", "lokalisation_sark"],
                            as_index=False
                        ).size()
                        grp.columns = ["jahr_opdatum", "lokalisation_sark", "count"]
    
                        # Gesamtzahl pro Jahr UND Lokalisation (alle Weichteiltumoren-Fälle)
                        grp_gesamt = df_plot_all.groupby(["jahr_opdatum", "lokalisation_sark"], as_index=False).size()
                        grp_gesamt.columns = ["jahr_opdatum", "lokalisation_sark", "count_gesamt"]
    
                        grp = grp.merge(grp_gesamt, on=["jahr_opdatum", "lokalisation_sark"], how="left")
    
                        grp["text_label"] = grp.apply(
                            lambda row: f"{row['count']}<br>(von {row['count_gesamt']})", axis=1
                        )
                        
                        fig = px.bar(
                            grp,
                            x="jahr_opdatum",
                            y="count",
                            color="lokalisation_sark",
                            barmode="group",
                            text="text_label",
                            color_discrete_sequence=COLOR_PALETTE,
                            labels={"lokalisation_sark": "Lokalisation", "Dindo_Status": "Dindo-Grad"},
                            # category_orders={"jahr_opdatum": quartal_order}
                        )
                   
                        fig.update_traces(
                            # 1. Positionierung & Ausrichtung (wo und wie steht der Text?)
                            textposition='auto',
                            textangle=0,                # Erzwingt, dass die Zahlen immer stehen (nicht liegend)
                            cliponaxis=False,           # Verhindert, dass Zahlen am oberen Rand abgeschnitten werden
                            insidetextanchor='middle',  # Zentriert die Zahl im Segment
                            # 2. Schriftgrösse etc.
                            textfont_size=16, 
                            insidetextfont=dict(size=16),
                            outsidetextfont=dict(size=16),
                            # 3. Visuelle Details des Balkens selbst
                            marker_line_width=0         # keine Begrenzungslinie
                        )
    
                        fig.for_each_annotation(lambda a: a.update(text=a.text.split("=")[-1]))
                   
                        fig.update_layout(
                            autosize=True,
                            height=None,
                            bargap=0.1,  
                            margin=dict(l=10, r=10, t=30, b=10),
                            xaxis_title=None,
                            yaxis_title=None,
                            showlegend=True,
                            legend=dict(orientation="h", yanchor="top", xanchor="right", x=0.99), #  y=-0.2,
                            xaxis={"type": "category", "tickfont": {"size": 16}},
                            yaxis={"showticklabels": True, "showgrid": True, "tickfont": {"size": 16}}
                        )
                   
                        st.plotly_chart(fig, use_container_width=True, key=f"kachel19_{bereich}", config={"displayModeBar": False, "responsive": True})
                    else:
                            st.info("Keine Daten für Weichteiltumoren")
                else:
                    st.error("Spalten fehlen")
               
        # ================== Kachel 20 "Clavien-Dindo-Grad >= IIIa in % - Lokalisation Weichteiltumoren" ==================
        #if bereich == "Chirurgische Onkologie/Sarkome":
            with col2.container(border=True):
                # Check auf Spalten
                required_cols = {"jahr_opdatum", "lokalisation_sark", "statistik_dindo_2", "type_sark"}
                if required_cols.issubset(df_bereich.columns):
            
                    # Filter für Sarkom/Weichteiltumor ohne Knochen
                    df_plot_all = df_bereich[(df_bereich["type_sark"] == "Sarkom/Weichteiltumor") & (df_bereich["gruppen_chir_onko_sark"] != "Knochen")].copy()
                    total_weichteil = len(df_plot_all)
            
                    # Dindo ≥ IIIa
                    df_plot = df_plot_all[df_plot_all["statistik_dindo_2"] == '1'].copy()
                    total_dindo = len(df_plot)
            
                    # Korrekte Berechnung mit Python-round
                    metrik_prozent = round(total_dindo / total_weichteil * 100, 1) if total_weichteil > 0 else 0
            
                    st.metric(
                        label="Clavien-Dindo-Grad ≥ IIIa in % - Lokalisation Weichteiltumoren", 
                        value=f"{metrik_prozent} % ({total_dindo} von {total_weichteil})",
                    )
                    # st.divider()
                    # verkleinert den Raum oberhalb der Trennlinie
                    st.markdown("<hr style='margin-top: -15px; margin-bottom: 5px; border: none; border-top: 1px solid #ddd;'>", unsafe_allow_html=True)
                    
                    if total_dindo > 0:
                        # Gruppierung nach Jahr, Lokalisation (nur Komplikationen >= IIIa)
                        grp = df_plot.groupby(["jahr_opdatum", "lokalisation_sark"], as_index=False).size()
                        grp.columns = ["jahr_opdatum", "lokalisation_sark", "count"]
            
                        # Gesamtzahl pro Jahr UND Lokalisation (alle Weichteiltumoren-Fälle)
                        grp_gesamt = df_plot_all.groupby(["jahr_opdatum", "lokalisation_sark"], as_index=False).size()
                        grp_gesamt.columns = ["jahr_opdatum", "lokalisation_sark", "count_gesamt"]
            
                        # Zusammenführen für korrekte Prozentbasis
                        grp = grp.merge(grp_gesamt, on=["jahr_opdatum", "lokalisation_sark"], how="left")
            
                        # Hier funktioniert .round(1), da es ein Pandas-Objekt ist
                        grp["prozent"] = (grp["count"] / grp["count_gesamt"] * 100).round(1)
            
                        # Nur Prozent im Label
                        grp["text_label"] = grp["prozent"].apply(lambda x: f"{x}%")
                        
                        fig = px.bar(
                            grp,
                            x="jahr_opdatum",
                            y="prozent", 
                            color="lokalisation_sark",
                            barmode="group", 
                            text="text_label",
                            color_discrete_sequence=COLOR_PALETTE,
                            labels={"lokalisation_sark": "Lokalisation", "prozent": "Anteil in %"},
                        )
                   
                        fig.update_traces(
                            # 1. Positionierung & Ausrichtung (wo und wie steht der Text?)
                            textposition='auto',
                            textangle=-45, # Damit die Zahlen im 45 Grad Winkel dargestellt werden
                            cliponaxis=False,           # Verhindert, dass Zahlen am oberen Rand abgeschnitten werden
                            insidetextanchor='middle',  # Zentriert die Zahl im Segment
                            # 2. Schriftgrösse etc.
                            textfont_size=16, 
                            insidetextfont=dict(size=16),
                            outsidetextfont=dict(size=16),
                            # 3. Visuelle Details des Balkens selbst
                            marker_line_width=0         # keine Begrenzungslinie
                        )
            
                        fig.for_each_annotation(lambda a: a.update(text=a.text.split("=")[-1]))
                   
                        fig.update_layout(
                            autosize=True,
                            height=None,
                            uniformtext_minsize=16,
                            uniformtext_mode='show',
                            bargap=0.1,  
                            margin=dict(l=10, r=10, t=30, b=10),
                            xaxis_title=None,
                            yaxis_title=None,
                            showlegend=True,
                            legend=dict(orientation="h", yanchor="top", xanchor="right", x=0.99), #  y=-0.2,
                            xaxis={"type": "category", "tickfont": {"size": 16}},
                            yaxis={"showticklabels": True, "showgrid": True, "tickfont": {"size": 16}, "tick0": 0, "dtick": 10} # "range": [0, 105],
                        )
                   
                        st.plotly_chart(fig, use_container_width=True, key=f"kachel20_{bereich}", config={"displayModeBar": False, "responsive": True})
                    else:
                        st.info("Keine Daten für Weichteiltumoren")
                else:
                    st.error("Spalten fehlen") 

        # ================== Kachel 13: "Aufteilung Komplikationen - Weichteiltumoren" ==================
        #if bereich == "Chirurgische Onkologie/Sarkome":
            with col1:
                # Zustand initialisieren
                if f"expand_{bereich}_k13" not in st.session_state:
                    st.session_state[f"expand_{bereich}_k13"] = False
    
                # Wenn ausgeblendet: Button allein (ohne Container-Rahmen), damit col2 leer wirkt
                if not st.session_state[f"expand_{bereich}_k13"]:
                    if st.button("𝗔𝘂𝗳𝘁𝗲𝗶𝗹𝘂𝗻𝗴 𝗞𝗼𝗺𝗽𝗹𝗶𝗸𝗮𝘁𝗶𝗼𝗻𝗲𝗻 - 𝗪𝗲𝗶𝗰𝗵𝘁𝗲𝗶𝗹𝘁𝘂𝗺𝗼𝗿𝗲𝗻 ▼ anzeigen", key=f"btn_{bereich}_k13"):
                        st.session_state[f"expand_{bereich}_k13"] = True
                        st.rerun()
                else:
                    # Wenn eingeblendet: Button IM Container oben rechts
                    with st.container(border=True):
                        
                        required_cols = {"jahr_opdatum", "lokalisation_sark", "statistik_dindo_2", "gruppen_chir_onko_sark", "max_dindo_calc", "max_dindo_calc_surv"}
                        if required_cols.issubset(df_bereich.columns):
                    
                            df_plot = df_bereich[
                                (df_bereich["type_sark"] == "Sarkom/Weichteiltumor") &
                                (df_bereich["gruppen_chir_onko_sark"] != "Knochen") &
                                (df_bereich["statistik_dindo_2"] == '1')
                            ].copy()
                    
                            dindo_order = [
                                'Grade IIIa', 'Grade IIIa d', 'Grade IIIb', 'Grade IIIb d',
                                'Grade IVa', 'Grade IVa d', 'Grade IVb', 'Grade IVb d', 'Grade V'
                            ]
                    
                            def get_highest_dindo(row):
                                v1 = row['max_dindo_calc']
                                v2 = row['max_dindo_calc_surv']
                                valid_values = [v for v in [v1, v2] if v in dindo_order]
                                return max(valid_values, key=lambda x: dindo_order.index(x)) if valid_values else "Unbekannt"
                    
                            df_plot["dindo_final_text"] = df_plot.apply(get_highest_dindo, axis=1)
                            df_plot = df_plot[df_plot["dindo_final_text"].isin(dindo_order)]
                    
                            total_dindo = len(df_plot)
                            st.metric(label="Aufteilung Komplikationen - Weichteiltumoren", value=f"{total_dindo} von {total_weichteil}")
                            # st.divider()
                            # verkleinert den Raum oberhalb der Trennlinie
                            st.markdown("<hr style='margin-top: -15px; margin-bottom: 5px; border: none; border-top: 1px solid #ddd;'>", unsafe_allow_html=True)
                    
                            if total_dindo > 0:
                                grp = df_plot.groupby(["jahr_opdatum", "dindo_final_text"], as_index=False).size()
                                grp.columns = ["jahr_opdatum", "dindo_final_text", "count"]
                                grp = grp.sort_values("jahr_opdatum")
                                jahr_order = grp["jahr_opdatum"].unique().tolist()
                    
                                fig = px.bar(
                                    grp,
                                    x="jahr_opdatum",
                                    y="count",
                                    color="dindo_final_text",
                                    barmode="stack",
                                    text="count",
                                    color_discrete_sequence=COLOR_PALETTE,
                                    labels={"jahr_opdatum": "Jahr", "dindo_final_text": "Dindo-Grad"},
                                    category_orders={"dindo_final_text": dindo_order, "jahr_opdatum": jahr_order}
                                )
                    
                                fig.update_traces(
                                    # 1. Positionierung & Ausrichtung (wo und wie steht der Text?)
                                    textposition='auto',
                                    textangle=0,                # Erzwingt, dass die Zahlen immer stehen (nicht liegend)
                                    cliponaxis=False,           # Verhindert, dass Zahlen am oberen Rand abgeschnitten werden
                                    insidetextanchor='middle',  # Zentriert die Zahl im Segment
                                    # 2. Schriftgrösse etc.
                                    textfont_size=16, 
                                    insidetextfont=dict(size=16),
                                    outsidetextfont=dict(size=16),
                                    # 3. Visuelle Details des Balkens selbst
                                    marker_line_width=0         # keine Begrenzungslinie
                                )
                    
                                fig.update_layout(
                                    height=395,
                                    bargap=0.1,
                                    margin=dict(l=10, r=10, t=10, b=10), # Margin oben minimiert
                                    xaxis_title=None,
                                    yaxis_title=None,
                                    showlegend=True,
                                    legend_title_text="",
                                    legend=dict(orientation="h", yanchor="top", xanchor="right", x=0.99), # y=-0.2, 
                                    xaxis={"type": "category", "tickfont": {"size": 16}},
                                    yaxis={"showticklabels": True, "showgrid": True, "tickfont": {"size": 16}}
                                )
                    
                                st.plotly_chart(fig, use_container_width=True, key=f"kachel13_{bereich}", config={"displayModeBar": False, "responsive": True})
                            else:
                                st.info("Keine Daten für Sarkom/Weichteiltumor")
                        else:
                            st.error("Spalten fehlen")

                        if st.button("▲ ausblenden", key=f"btn_{bereich}_k13_close"):
                            st.session_state[f"expand_{bereich}_k13"] = False
                            st.rerun()

        # ================== Kachel 15 "Aufenthaltsdauer - Weichteiltumoren" ==================       
        #if bereich == "Chirurgische Onkologie/Sarkome":
            with col1.container(border=True):
                required_cols = {"los_opdatum", "type_sark", "jahr_opdatum", "gruppen_chir_onko_sark"}
                if required_cols.issubset(df_bereich.columns):
                    # Filter identisch zu Kachel 10 (nur Weichteiltumoren ohne Knochen)
                    df_los = df_bereich[
                        (df_bereich["type_sark"] == "Sarkom/Weichteiltumor") & 
                        (df_bereich["gruppen_chir_onko_sark"] != "Knochen")
                    ].copy()
                    
                    df_los["los_opdatum"] = pd.to_numeric(df_los["los_opdatum"], errors='coerce')
                    df_los = df_los.dropna(subset=["los_opdatum"])
                    
                    total_faelle_los = len(df_los)
                    
                    st.metric(label="Aufenthaltsdauer - Weichteiltumoren", value=f"{total_faelle_los}")
                    # st.divider()
                    # verkleinert den Raum oberhalb der Trennlinie
                    st.markdown("<hr style='margin-top: -15px; margin-bottom: 5px; border: none; border-top: 1px solid #ddd;'>", unsafe_allow_html=True)
            
                    if total_faelle_los > 0:
                        # Aggregation pro Jahr
                        grp = df_los.groupby("jahr_opdatum", as_index=False)["los_opdatum"].agg(
                            Mittelwert="mean",
                            Median="median",
                            Minimum="min",
                            Maximum="max"
                        )
            
                        # Balkendiagramm für Mittelwert
                        fig = px.bar(
                            grp,
                            x="jahr_opdatum",
                            y="Mittelwert",
                            text="Mittelwert",
                            color_discrete_sequence=COLOR_PALETTE,
                            labels={"Mittelwert": "Tage", "jahr_opdatum": "Jahr"}
                        )
            
                        fig.update_traces(
                            # 1. Positionierung & Ausrichtung (wo und wie steht der Text?)
                            textposition='outside',
                            textangle=0,                # Erzwingt, dass die Zahlen immer stehen (nicht liegend)
                            cliponaxis=False,           # Verhindert, dass Zahlen am oberen Rand abgeschnitten werden
                            # 2. Schriftgrösse etc.
                            textfont_size=16, 
                            texttemplate='%{text:.2f}',
                            # 3. Visuelle Details des Balkens selbst
                            marker_line_width=0         # keine Begrenzungslinie
                        )
            
                        # Linien für Median, Min, Max
                        fig.add_trace(go.Scatter(
                            x=grp["jahr_opdatum"],
                            y=grp["Median"],
                            mode="lines+markers",
                            name="Median",
                            line=dict(color="green", dash="dash"),
                            marker=dict(size=8)
                        ))
                        fig.add_trace(go.Scatter(
                            x=grp["jahr_opdatum"],
                            y=grp["Minimum"],
                            mode="lines+markers",
                            name="Minimum",
                            line=dict(color="red", dash="dot"),
                            marker=dict(size=8)
                        ))
                        fig.add_trace(go.Scatter(
                            x=grp["jahr_opdatum"],
                            y=grp["Maximum"],
                            mode="lines+markers",
                            name="Maximum",
                            line=dict(color="blue", dash="dot"),
                            marker=dict(size=8)
                        ))
            
                        fig.update_layout(
                            height=400,
                            margin=dict(l=10, r=10, t=20, b=10), # T etwas erhöht für Text 'outside'
                            xaxis_title=None,
                            yaxis_title=None,
                            xaxis={"type": "category", "tickfont": {"size": 16}},
                            yaxis={"showticklabels": True, "showgrid": True, "tickfont": {"size": 16}},
                            legend=dict(orientation="h", yanchor="top", xanchor="right", x=0.99)
                        )
            
                        st.plotly_chart(fig, use_container_width=True, key=f"kachel15_{bereich}", config={"displayModeBar": False, "responsive": True})
                    else:
                        st.info("Keine Daten für Sarkome/Weichteiltumore ohne Knochen")
                else:
                    st.error("Spalten fehlen")
            
            st.markdown('</div>', unsafe_allow_html=True)
        
        # ================== ENDE BEREICH CHURURGISCHE ONKOLOGIE/SARKOME ================== 

        if bereich == "Leber":
            col1, col2 = st.columns(2)

        # ========================= ANFANG BEREICH LEBERCHIRURGIE ========================= 
            
        # 1. Grafik: Leber HSM JA / NEIN in absoluten Zahlen und % + Gesamtergebnis pro Jahr
        # ================== Kachel 1 "Leber HSM" % und absolute Zahlen ==================
        #if bereich == "Leber":
            with col1.container(border=True):
                pattern = "HCC|CCC|Metastasen|Benigne"
                df_leber_hsm = df_bereich[df_bereich["leber_gruppen"].str.contains(pattern, na=False)].copy()
                #df_leber_hsm = df_bereich.copy()
                df_hsm = df_leber_hsm[df_leber_hsm['hsm'].isin(['Ja', 'Nein'])].copy()
                total_hsm = len(df_hsm)

                st.metric(label="Leberchirurgie - HSM", value=total_hsm)
                st.markdown("<hr style='margin-top: -15px; margin-bottom: 5px; border: none; border-top: 1px solid #ddd;'>", unsafe_allow_html=True)

                if total_hsm > 0:
                    leber_hsm_jahr = df_hsm.groupby(['jahr_opdatum', 'hsm']).size().reset_index(name='count')
                    leber_hsm_jahr['pct'] = leber_hsm_jahr.groupby('jahr_opdatum')['count'].transform(lambda x: (x / x.sum()) * 100)
                    
                    # Einfacher Text: Anzahl (Prozent%)
                    leber_hsm_jahr['text_label'] = leber_hsm_jahr.apply(lambda r: f"{r['count']}<br>({r['pct']:.1f}%)", axis=1)
                    
                    fig_leber_hsm = px.bar(
                        leber_hsm_jahr,
                        x='jahr_opdatum',
                        y='count',            
                        color='hsm',
                        barmode='group',
                        text='text_label',  
                        color_discrete_sequence=COLOR_PALETTE,
                        labels={'hsm': 'HSM'} 
                    )
                        
                    fig_leber_hsm.update_traces(
                        textposition='auto', 
                        textfont_size=16,       
                        textangle=0,            
                        cliponaxis=False,       # Verhindert Abschneiden am oberen Rand
                        marker_line_width=0
                    )
                        
                    fig_leber_hsm.update_layout(
                        height=400,
                        margin=dict(l=10, r=10, t=30, b=10), # Platz für die Beschriftung oben
                        xaxis_title=None, 
                        yaxis_title=None, 
                        xaxis={"type": "category", "tickfont": {"size": 16}},
                        yaxis={"showticklabels": True, "showgrid": True, "tickfont": {"size": 16}},
                        legend=dict(orientation="h", yanchor="top", xanchor="right", x=0.99)
                    )
                        
                    st.plotly_chart(fig_leber_hsm, use_container_width=True, key=f"kachel_leber_hsm_{bereich}", config={"displayModeBar": False})
                else:
                    st.info("Keine auswertbaren HSM-Daten für die Leberchirurgie vorhanden.")


        # 2. Grafik: Zugang Roboterassistiert / Offen in absoluten Zahlen und % 
        # ================== Kachel 2: Leberchirurgie - Zugang (HCC|CCC|Metastasen|Benigne) ==================
        #if bereich == "Leber":
            with col2.container(border=True):
                #pattern = "HCC|CCC|Metastasen|Benigne"
                #df_leber_zugang = df_bereich[df_bereich["leber_gruppen"].str.contains(pattern, na=False)].copy()
                df_leber_zugang = df_bereich.copy()
                df_zugang = df_leber_zugang[df_leber_zugang['zugang'].isin(['Offen', 'Laparoskopisch', 'roboter-assistiert'])].copy()
                total_zugang = len(df_zugang)

                st.metric(label="Leberchirurgie - Zugang (HCC|CCC|Metastasen|Benigne)", value=total_zugang)
                st.markdown("<hr style='margin-top: -15px; margin-bottom: 5px; border: none; border-top: 1px solid #ddd;'>", unsafe_allow_html=True)
                
                if "zugang" in df_zugang.columns and df_zugang["zugang"].nunique() > 0:
                    # 1. Groupby auf den gefilterten Leber-Daten ausführen
                    leber_zugang_jahr = df_zugang.groupby(["jahr_opdatum", "zugang"], as_index=False).size()
                    leber_zugang_jahr.columns = ["jahr_opdatum", "zugang", "count"]

                    # Prozentberechnung pro Jahr hinzufügen
                    leber_zugang_jahr['pct'] = leber_zugang_jahr.groupby('jahr_opdatum')['count'].transform(lambda x: (x / x.sum()) * 100)

                    # 2. Custom Label korrekt von leber_zugang_jahr ableiten
                    leber_zugang_jahr['text_label'] = leber_zugang_jahr.apply(lambda r: f"{r['count']}<br>({r['pct']:.1f}%)", axis=1)
                    
                    fig_leber_zugang = px.bar(
                        leber_zugang_jahr,
                        x='jahr_opdatum',
                        y='count',            
                        color='zugang',
                        barmode='group',
                        text='text_label',  
                        color_discrete_sequence=COLOR_PALETTE,
                        labels={'zugang': 'Zugang'} 
                    )
                        
                    fig_leber_zugang.update_traces(
                        textposition='auto', 
                        textfont_size=16,       
                        textangle=0,            
                        cliponaxis=False,       
                        marker_line_width=0
                    )
                        
                    fig_leber_zugang.update_layout(
                        height=400,
                        margin=dict(l=10, r=10, t=30, b=10), 
                        xaxis_title=None, 
                        yaxis_title=None, 
                        xaxis={"type": "category", "tickfont": {"size": 16}},
                        yaxis={"showticklabels": True, "showgrid": True, "tickfont": {"size": 16}},
                        legend=dict(orientation="h", yanchor="top", xanchor="right", x=0.99)
                    )
                        
                    st.plotly_chart(fig_leber_zugang, use_container_width=True, key=f"kachel_leber_zugang_{bereich}", config={"displayModeBar": False})
                else:
                    st.info("Keine Zugangsdaten")

        # 3. Grafik: Roboterassistierte Eingriffe nach Lebergruppen darstellen in % + insgesamt in % für HCC, CCC und Metastasen (ohne Benigne)
        # ================== Kachel 3: Roboterassistierte Eingriffe nach Lebergruppen (HCC|CCC|Metastasen) ==================
        #if bereich == "Leber":
            with col1.container(border=True):
                pattern = "HCC|CCC|Metastasen"
                df_leber_robot = df_bereich[df_bereich["leber_gruppen"].str.contains(pattern, na=False)].copy()
                df_zugang = df_leber_robot[df_leber_robot['zugang'].isin(['roboter-assistiert'])].copy()
                total_zugang_robot = len(df_zugang)

                st.metric(label="Leberchirurgie - Roboterassistierte Eingriffe nach Gruppen (HCC|CCC|Metastasen)", value=total_zugang_robot)
                st.markdown("<hr style='margin-top: -15px; margin-bottom: 5px; border: none; border-top: 1px solid #ddd;'>", unsafe_allow_html=True)
                
                if "zugang" in df_zugang.columns and df_zugang["zugang"].nunique() > 0:
                    # 1. Groupby auf den gefilterten Leber-Daten ausführen
                    leber_robot_jahr = df_zugang.groupby(["jahr_opdatum", "leber_gruppen"], as_index=False).size()
                    leber_robot_jahr.columns = ["jahr_opdatum", "leber_gruppen", "count"]

                    # Prozentberechnung pro Jahr hinzufügen
                    leber_robot_jahr['pct'] = leber_robot_jahr.groupby('jahr_opdatum')['count'].transform(lambda x: (x / x.sum()) * 100)

                    # 2. Custom Label korrekt von leber_zugang_jahr ableiten
                    leber_robot_jahr['text_label'] = leber_robot_jahr.apply(lambda r: f"{r['count']}<br>({r['pct']:.1f}%)", axis=1)
                    
                    fig_leber_robot = px.bar(
                        leber_robot_jahr,
                        x='jahr_opdatum',
                        y='count',            
                        color='leber_gruppen', 
                        barmode='group',
                        text='text_label',  
                        color_discrete_sequence=COLOR_PALETTE,
                        labels={'leber_gruppen': 'Lebergruppen'} 
                    )
                        
                    fig_leber_robot.update_traces(
                        # 1. Positionierung & Ausrichtung (wo und wie steht der Text?)
                        textposition='auto',
                        textangle=0,                # Erzwingt, dass die Zahlen immer stehen (nicht liegend)
                        cliponaxis=False,           # Verhindert, dass Zahlen am oberen Rand abgeschnitten werden
                        #insidetextanchor='middle',  # Zentriert die Zahl im Segment
                        # 2. Schriftgrösse etc.
                        textfont_size=16, 
                        insidetextfont=dict(size=16),
                        outsidetextfont=dict(size=16),
                        # 3. Visuelle Details des Balkens selbst
                        marker_line_width=0         # keine Begrenzungslinie
                    )
                        
                    fig_leber_robot.update_layout(
                        height=400,
                        margin=dict(l=10, r=10, t=30, b=10), 
                        xaxis_title=None, 
                        yaxis_title=None, 
                        xaxis={"type": "category", "tickfont": {"size": 16}},
                        yaxis={"showticklabels": True, "showgrid": True, "tickfont": {"size": 16}},
                        legend=dict(orientation="h", yanchor="top", xanchor="right", x=0.99),
                        bargap=0.1,        # Abstand zwischen Jahres-Gruppen (0 = kein Abstand, 1 = max)
                    )
                        
                    st.plotly_chart(fig_leber_robot, use_container_width=True, key=f"kachel_leber_robot_{bereich}", config={"displayModeBar": False})
                else:
                    st.info("Keine Daten")


        # 4. Grafik: Hospital Stay
        # ================== Kachel 4: "Aufenthaltsdauer - Leberchirurgie" ==================       
        #if bereich == "Leber":
            with col2.container(border=True):
                required_cols = {"los_opdatum", "leber_gruppen", "jahr_opdatum"}
                if required_cols.issubset(df_bereich.columns):
                    pattern = "HCC|CCC|Metastasen|Benigne"
                    df_los = df_bereich[df_bereich["leber_gruppen"].str.contains(pattern, na=False)].copy()
                    df_los["los_opdatum"] = pd.to_numeric(df_los["los_opdatum"], errors='coerce')
                    df_los = df_los.dropna(subset=["los_opdatum"])
                    total_leber_gruppen = len(df_los)
                    st.metric(label="Aufenthaltsdauer - Leberchirurgie", value=total_leber_gruppen)
                    # st.divider()
                    # verkleinert den Raum oberhalb der Trennlinie
                    st.markdown("<hr style='margin-top: -15px; margin-bottom: 5px; border: none; border-top: 1px solid #ddd;'>", unsafe_allow_html=True)
            
                    if total_leber_gruppen > 0:
                        # Aggregation nach Jahr
                        grp = df_los.groupby(["jahr_opdatum"], as_index=False)["los_opdatum"].agg(
                            Mittelwert="mean",
                            Median="median",
                            Minimum="min",
                            Maximum="max"
                        )
            
                        # Balkendiagramm für Mittelwert
                        fig = px.bar(
                            grp,
                            x="jahr_opdatum",
                            y="Mittelwert",
                            text="Mittelwert",
                            color_discrete_sequence=COLOR_PALETTE,
                            labels={"Mittelwert": "Tage", "jahr_opdatum": "Jahr"}
                        )
            
                        fig.update_traces(
                            # 1. Positionierung & Ausrichtung (wo und wie steht der Text?)
                            textposition='outside',
                            textangle=0,                # Erzwingt, dass die Zahlen immer stehen (nicht liegend)
                            cliponaxis=False,           # Verhindert, dass Zahlen am oberen Rand abgeschnitten werden
                            # 2. Schriftgrösse etc.
                            textfont_size=16, 
                            texttemplate='%{text:.2f}',
                            # 3. Visuelle Details des Balkens selbst
                            marker_line_width=0         # keine Begrenzungslinie
                        )
            
                        # Linien für Median, Min, Max
                        fig.add_trace(go.Scatter(
                            x=grp["jahr_opdatum"],
                            y=grp["Median"],
                            mode="lines+markers",
                            name="Median",
                            line=dict(color="green", dash="dash"),
                            marker=dict(size=8)
                        ))
                        fig.add_trace(go.Scatter(
                            x=grp["jahr_opdatum"],
                            y=grp["Minimum"],
                            mode="lines+markers",
                            name="Minimum",
                            line=dict(color="red", dash="dot"),
                            marker=dict(size=8)
                        ))
                        fig.add_trace(go.Scatter(
                            x=grp["jahr_opdatum"],
                            y=grp["Maximum"],
                            mode="lines+markers",
                            name="Maximum",
                            line=dict(color="blue", dash="dot"),
                            marker=dict(size=8)
                        ))
            
                        fig.update_layout(
                            height=400,
                            margin=dict(l=10, r=10, t=10, b=10),
                            xaxis_title=None,
                            yaxis_title=None,
                            xaxis={"type": "category", "tickfont": {"size": 16}},
                            yaxis={"showticklabels": True, "showgrid": True, "tickfont": {"size": 16}},
                            legend=dict(orientation="h", yanchor="top", xanchor="right", x=0.99)
                        )
            
                        st.plotly_chart(fig, use_container_width=True, key=f"kachel_leber_los_{bereich}", config={'displayModeBar': False})
                    else:
                        st.info("Keine Daten für Leberchirurgie")
                else:
                    st.error("Spalten fehlen")
            
            # 5. Grafik: Mortality [max_dindo_calc] = 13 (Grade V) oder [max_dindo_calc_surv] = 13 (Grade V), in absoluten Zahlen und % 
            # ================== Kachel 5: "Mortalität - Leberchirurgie" ==================
            #if bereich == "Leber":
                with col1.container(border=True):
                    pattern = "HCC|CCC|Metastasen|Benigne"
                    df_leber_mortalitaet = df_bereich[df_bereich["leber_gruppen"].str.contains(pattern, na=False)].copy()
            
                    # Fälle mit Mortalität (Grade V)
                    df_mortalitaet = df_leber_mortalitaet[
                        (df_leber_mortalitaet["max_dindo_calc"] == 13) |
                        (df_leber_mortalitaet["max_dindo_calc_surv"] == 13)
                    ].copy()
            
                    total_mortalitaet = len(df_mortalitaet)
            
                    st.metric(label="Leberchirurgie - Mortalität (Grade V)", value=total_mortalitaet)
                    st.markdown("<hr style='margin-top: -15px; margin-bottom: 5px; border: none; border-top: 1px solid #ddd;'>", unsafe_allow_html=True)
            
                    if total_mortalitaet > 0:
                        leber_mortalitaet_pro_jahr = (
                            df_mortalitaet.groupby("jahr_opdatum")
                            .size()
                            .reset_index(name="count")
                        )
            
                        gesamt_pro_jahr = (
                            df_leber_mortalitaet.groupby("jahr_opdatum")
                            .size()
                        )
            
                        leber_mortalitaet_pro_jahr["pct"] = leber_mortalitaet_pro_jahr.apply(
                            lambda r: (r["count"] / gesamt_pro_jahr[r["jahr_opdatum"]]) * 100
                            if r["jahr_opdatum"] in gesamt_pro_jahr.index else 0,
                            axis=1
                        )
            
                        leber_mortalitaet_pro_jahr["text_label"] = leber_mortalitaet_pro_jahr.apply(
                            lambda r: f"{int(r['count'])} ({r['pct']:.1f}%)", axis=1
                        )
            
                        fig_leber_mortalitaet = px.bar(
                            leber_mortalitaet_pro_jahr,
                            x="jahr_opdatum",
                            y="count",
                            text="text_label",
                            color_discrete_sequence=COLOR_PALETTE
                        )
            
                        fig_leber_mortalitaet.update_traces(
                            textposition="auto",
                            textfont_size=16,
                            textangle=0,
                            cliponaxis=False,
                            marker_line_width=0
                        )
            
                        fig_leber_mortalitaet.update_layout(
                            height=400,
                            margin=dict(l=10, r=10, t=30, b=10),
                            xaxis_title=None,
                            yaxis_title=None,
                            xaxis={"type": "category", "tickfont": {"size": 16}},
                            yaxis={"showticklabels": True, "showgrid": True, "tickfont": {"size": 16}, "dtick": 1},
                            legend=dict(orientation="h", yanchor="top", xanchor="right", x=0.99)
                        )
            
                        st.plotly_chart(
                            fig_leber_mortalitaet,
                            use_container_width=True,
                            key=f"kachel_leber_mortalitaet_{bereich}",
                            config={"displayModeBar": False}
                        )
                    else:
                        st.info("Keine auswertbaren Mortalitätsdaten für die Leberchirurgie vorhanden.")
            
            # 6. Grafik: Bile Leak [kpl_was] = Gallenfistel oder [kpl_was] = Gallenfistel, in absoluten Zahlen und % 
            # ================== Kachel 6: "Gallefisteln - Leber" ================== 
            #if bereich == "Leber":
                with col2.container(border=True):
                    pattern = "HCC|CCC|Metastasen|Benigne"
                    df_leber_gallefistel = df_bereich[
                        df_bereich["leber_gruppen"].str.contains(pattern, na=False)
                    ].copy()
            
                    # Fälle mit Gallefistel (aus beiden Spalten)
                    df_gallefistel = df_leber_gallefistel[
                        df_leber_gallefistel["kpl_was_surv"].fillna("").str.contains("Gallenfistel", case=False) |
                        df_leber_gallefistel["kpl_was"].fillna("").str.contains("Gallenfistel", case=False)
                    ].copy()
            
                    total_gallefistel = len(df_gallefistel)
            
                    st.metric(label="Leberchirurgie - Gallefistel als Komplikation", value=total_gallefistel)
                    st.markdown("<hr style='margin-top: -15px; margin-bottom: 5px; border: none; border-top: 1px solid #ddd;'>", unsafe_allow_html=True)
            
                    if total_gallefistel > 0:
                        # Gallefisteln pro Jahr zählen
                        leber_gallefistel_pro_jahr = (
                            df_gallefistel.groupby("jahr_opdatum")
                            .size()
                            .reset_index(name="count")
                        )
                        
                        gesamt_pro_jahr = (
                        df_leber_gallefistel.groupby("jahr_opdatum")
                        .size()
                        )
                        
                        # Prozentwert berechnen
                        leber_gallefistel_pro_jahr["pct"] = leber_gallefistel_pro_jahr.apply(
                            lambda r: (r["count"] / gesamt_pro_jahr[r["jahr_opdatum"]]) * 100
                            if r["jahr_opdatum"] in gesamt_pro_jahr.index else 0,
                            axis=1
                        )
                        
                        leber_gallefistel_pro_jahr["text_label"] = leber_gallefistel_pro_jahr.apply(
                            lambda r: f"{int(r['count'])} ({r['pct']:.1f}%)", axis=1
                        )
                        
                        fig_leber_gallefistel = px.bar(
                            leber_gallefistel_pro_jahr,
                            x="jahr_opdatum",
                            y="count",
                            text="text_label",
                            color_discrete_sequence=COLOR_PALETTE
                        )
                        
                        fig_leber_gallefistel.update_traces(
                            textposition="auto",
                            textfont_size=16,
                            textangle=0,
                            cliponaxis=False,
                            marker_line_width=0
                        )
            
                        fig_leber_gallefistel.update_layout(
                            height=400,
                            margin=dict(l=10, r=10, t=30, b=10),
                            xaxis_title=None,
                            yaxis_title=None,
                            xaxis={"type": "category", "tickfont": {"size": 16}},
                            yaxis={"showticklabels": True, "showgrid": True, "tickfont": {"size": 16}, "dtick": 1},
                            legend=dict(orientation="h", yanchor="top", xanchor="right", x=0.99)
                        )
            
                        st.plotly_chart(
                            fig_leber_gallefistel,
                            use_container_width=True,
                            key=f"kachel_leber_gallefistel_{bereich}",
                            config={"displayModeBar": False}
                        )
                    else:
                        st.info("Keine auswertbaren Gallefistel-Daten für die Leberchirurgie vorhanden.")
            
            # 7. Grafik: Reoperation [reoperation_30d] = 1 in absoluten Zahlen und % 
            # ================== Kachel 7: "Leber Reoperation 30 Tage" % und absolute Zahlen ==================
            #if bereich == "Leber":
                with col2.container(border=True):
                    pattern = "HCC|CCC|Metastasen|Benigne"
                    df_leber_reop = df_bereich[df_bereich["leber_gruppen"].str.contains(pattern, na=False)].copy()
                    
                    # Nur die echten Reoperationen filtern
                    df_reoperation_30d = df_leber_reop[df_leber_reop['reoperation_30d'].isin(['Ja'])].copy()
                    total_reop = len(df_reoperation_30d)
    
                    st.metric(label="Leberchirurgie - Reoperation 30 Tage postoperativ", value=total_reop)
                    st.markdown("<hr style='margin-top: -15px; margin-bottom: 5px; border: none; border-top: 1px solid #ddd;'>", unsafe_allow_html=True)
    
                    if total_reop > 0:
                        # Absolute Zahlen der Reoperationen pro Jahr zählen
                        leber_reop_jahr = df_reoperation_30d.groupby(['jahr_opdatum', 'reoperation_30d']).size().reset_index(name='count')
                        
                        # Basis ermitteln: Wie viele Fälle gab es insgesamt pro Jahr (Ja + Nein)?
                        gesamt_pro_jahr = df_leber_reop[df_leber_reop['reoperation_30d'].isin(['Ja', 'Nein'])].groupby('jahr_opdatum').size()
                        
                        # Prozentwert korrekt im Verhältnis zur Jahresgesamtzahl berechnen
                        leber_reop_jahr['pct'] = leber_reop_jahr.apply(
                            lambda r: (r['count'] / gesamt_pro_jahr[r['jahr_opdatum']]) * 100 if r['jahr_opdatum'] in gesamt_pro_jahr else 0, 
                            axis=1
                        )
                        
                        # Text-Label: Anzahl (Prozent%)
                        leber_reop_jahr['text_label'] = leber_reop_jahr.apply(lambda r: f"{r['count']} ({r['pct']:.1f}%)", axis=1)
                        
                        fig_leber_reop = px.bar(
                            leber_reop_jahr,
                            x='jahr_opdatum',
                            y='count',            
                            color='reoperation_30d', # Tippfehler behoben
                            barmode='group',
                            text='text_label',  
                            color_discrete_sequence=COLOR_PALETTE
                        )
                            
                        fig_leber_reop.update_traces(
                            textposition='auto', 
                            textfont_size=16,       
                            textangle=0,            
                            cliponaxis=False,       
                            marker_line_width=0
                        )
                            
                        fig_leber_reop.update_layout(
                            height=400,
                            margin=dict(l=10, r=10, t=30, b=10), 
                            xaxis_title=None, 
                            yaxis_title=None, 
                            xaxis={"type": "category", "tickfont": {"size": 16}},
                            yaxis={"showticklabels": True, "showgrid": True, "tickfont": {"size": 16}},
                            legend=dict(orientation="h", yanchor="top", xanchor="right", x=0.99)
                        )
                            
                        st.plotly_chart(fig_leber_reop, use_container_width=True, key=f"kachel_leber_reop_{bereich}", config={"displayModeBar": False})
                    else:
                        st.info("Keine auswertbaren Reoperation-Daten für die Leberchirurgie vorhanden.")

 # Grafiken 4 - 7: Prüfen, was in diesem Zusammenhang Benchmarkdaten bedeuten. Evtl. Vergleich mit dem letzten Qurtal, oder mit dem selben Quartal des Vorjahres
            
# 8. Grafik Clavien Dindo >III und V getrennt darstellen, in absoluten Zahlen und % 
        
        # ================== ENDE BEREICH LEBER ================== 

        # ================== ANFANG BEREICH KOLOREKTALE CHIRURGIE ================== 
        
            if bereich == "Kolorektale Chirurgie":
                col1, col2 = st.columns(2)

        # ================== ENDE BEREICH KOLOREKTALE CHIRURGIE ================== 
        

        
        
       

        # ================== BEREICH LEBER ==================    
        # ================== GRUPPEN ==================
        # if "Gruppen" in analysen:
        # with st.container():
            # if "leber_gruppen" in df_bereich.columns and df_bereich["leber_gruppen"].nunique() > 0:
                # grp = df_bereich.groupby(["jahr_opdatum", "leber_gruppen"], as_index=False).size()
                # grp.columns = ["jahr_opdatum", "leber_gruppen", "count"]

                # fig = px.bar(
                    # grp,
                    # x="jahr_opdatum",
                    # y="count",
                    # color="leber_gruppen",
                    # barmode="group",
                    # text="count",
                    # color_discrete_sequence=COLOR_PALETTE,
                    # labels={"leber_gruppen": "Lebergruppen"}
                # )

                # fig.update_traces(
                    # textfont_size=16, 
                    # textposition='inside'
                # )

                # fig.update_layout(
                    # xaxis_title=None, 
                    # yaxis_title=None, 
                    # xaxis={"type": "category", "tickfont": {"size": 16}},
                    # yaxis={"tickfont": {"size": 16}} 
                # )
                    
                # st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False, "responsive": True})
                # # else:
                    # # st.info("Keine Gruppendaten")

        

        # ================== KOMPLIKATIONEN ==================
        # if "Komplikationen" in analysen:
        # with st.container():
            # if "max_dindo_calc" in df_bereich.columns and df_bereich["max_dindo_calc"].notna().any():
                # d = (
                    # df_bereich
                    # .dropna(subset=["jahr_opdatum", "max_dindo_calc", "max_dindo_calc_surv"])
                    # .groupby(["jahr_opdatum", "max_dindo_calc", "max_dindo_calc_surv"], as_index=False)
                    # .size()
                # )
                # d.columns = ["jahr_opdatum", "dindo", "count"]
                # mat = d.pivot(index="dindo", columns="jahr_opdatum", values="count").fillna(0)

                # fig = px.imshow(
                    # mat,
                    # text_auto=True,
                    # aspect="auto",
                    # color_continuous_scale="Greens"
                # )
                # st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False, "responsive": True})
                # # else:
                    # # st.info("Keine Komplikationsdaten")

       

        # ------------------- Export Button erstellen ---------------------
        def figures_to_html(figures: dict) -> bytes:
            import plotly.io as pio
            
            titles = {
                "kachel_sarkome_ges": "Gesamtzahl Operationen - Onkologie/Sarkome",
                "kachel_sarkome_typ": "Übersicht Operationen",
                "kachel_crs_hipec": "HIPEC bei CRS"
            }
            
            # 1. Breite im Body auf 100% setzen und Ränder entfernen
            html = """<html><body style="display:flex; flex-direction:column; align-items:center; width:100%; margin:0; padding:0;">"""
            
            for name, fig in figures.items():
                # 2. Festen Breitenwert bei der Grafik entfernen
                fig.update_layout(
                    height=500,
                    title=titles.get(name, ""),
                    margin=dict(l=60, r=40, t=60, b=60)
                )
                # 3. Div auf volle Breite oder einen Prozentsatz setzen (z. B. 95%)
                html += "<div style='width:95%; max-width:1000px; margin-bottom:40px;'>"
                html += pio.to_html(fig, full_html=False, include_plotlyjs='cdn')
                html += "</div>"
                fig.update_layout(height=None, width=None, title=None, margin=dict(l=10, r=10, t=0, b=10))
            
            html += "</body></html>"
            return html.encode('utf-8')
        
        #.get() verhindert den Absturz, falls das Objekt beim ersten Laden noch nicht existiert
        st.download_button(
            label=f"📄 Grafiken exportieren - {bereich}",
            data=figures_to_html(
                st.session_state.get("pdf_figures", {}).get(bereich, {})
            ),
            file_name="dashboard_export.html",
            mime="text/html"
        )
        
        
