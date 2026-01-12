# ==================================================
# Imports
# ==================================================
import os                          # Zugriff auf Umgebungsvariablen (API-Token)
import requests                    # HTTP-Requests zur REDCap-API
import pandas as pd                # Datenverarbeitung mit DataFrames
import plotly.express as px         # Plotly Express für Diagramme
import plotly.graph_objects as go   # Erweiterte Plotly-Funktionen (hier nicht zwingend genutzt)
import streamlit as st              # Streamlit für das Web-Dashboard
import urllib3                      # Unterdrücken von SSL-Warnungen

# SSL-Warnungen deaktivieren (weil verify=False verwendet wird)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


# ==================================================
# Konfiguration
# ==================================================
API_URL = 'https://fxdb.usb.ch/api/'


# ==================================================
# Datenexport aus REDCap
# ==================================================
def export_redcap_data(api_url):
    # API-Token aus Umgebungsvariable lesen
    API_TOKEN = os.getenv("tok_op_gruppen")

    # Parameter für den REDCap-API-Export
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
        # POST-Request an die REDCap-API
        r = requests.post(api_url, data=data, verify=False)
        r.raise_for_status()  # Fehler bei HTTP-Status ≠ 200

        # JSON-Antwort in DataFrame umwandeln
        return pd.DataFrame(r.json())

    except requests.exceptions.RequestException as e:
        # Fehlermeldung im Streamlit-UI anzeigen
        st.error(f"Fehler beim Export: {e}")
        return None


# ==================================================
# Datenaufbereitung
# ==================================================
def prepare_data(df):
    # Kopie erstellen, um Originaldaten nicht zu verändern
    df = df.copy()

    # Sicherstellen, dass opdatum ein datetime ist
    df['opdatum'] = pd.to_datetime(df['opdatum'], errors='coerce')


    # -------- Bereich (Checkboxen aus REDCap) --------
    # Checkboxen erzeugen mehrere Spalten: bereich___1, bereich___2, ...
    bereich_cols = [col for col in df.columns if col.startswith('bereich___')]

    if bereich_cols:
        # Mapping der Checkbox-Codes auf Klartext
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

        # Pro Zeile alle gesetzten Checkboxen (Wert == '1') sammeln
        def get_bereich(row):
            return ', '.join(
                label for col, label in mapping.items() if row.get(col) == '1'
            ) or 'Nicht angegeben'

        # Neue Spalte "bereich" erzeugen
        df['bereich'] = df.apply(get_bereich, axis=1)

        # Ursprüngliche Checkbox-Spalten entfernen
        df = df.drop(columns=bereich_cols)

    # -------- Zugang (Radiobutton aus REDCap) --------
    zugang_mapping = {
        1: 'Offen',
        2: 'Laparoskopisch',
        3: 'roboter-assistiert',
        4: 'konvertiert',
        5: 'hybrid (2Höhlen-Eingriffe)'
    }

    # Zugang in numerischen Typ umwandeln
    df['zugang'] = pd.to_numeric(df['zugang'], errors='coerce')

    # Numerische Codes in Klartext übersetzen
    df['zugang'] = df['zugang'].map(zugang_mapping).fillna('Unbekannt')

    # -------- Numerische Felder --------
    df['jahr_opdatum'] = df['opdatum'].dt.year.astype('Int64')  
    df['quartal_opdatum'] = df['opdatum'].dt.to_period('Q').astype(str).str.replace(r'(\d{4})Q(\d)', r'Q\2-\1', regex=True) # Quartale im Format QX-JJJJ
    df['quartal_sort'] = df['opdatum'].dt.year * 10 + df['opdatum'].dt.quarter 
    df['max_dindo_calc_surv'] = pd.to_numeric(df['max_dindo_calc_surv'], errors='coerce')
    # Zeilen ohne Jahr entfernen
    df = df.dropna(subset=['jahr_opdatum'])

    return df


# ==================================================
# Streamlit App
# ==================================================
st.title("OP-Gruppierung Dashboard")

# Daten laden
df = export_redcap_data(API_URL)

if df is not None:
    # Daten vorbereiten
    df = prepare_data(df)

# --------Filterblock--------
filtered_df = df.copy()

# Jahr
jahre = sorted(df['jahr_opdatum'].dropna().astype(int).unique())
jahr_filter = st.multiselect(
     "Jahr auswählen:",
    options=jahre,
    default=jahre  # standardmäßig alle Jahre auswählen
)

if jahr_filter: 
    filtered_df = filtered_df[filtered_df['jahr_opdatum'].isin(jahr_filter)]

# Quartal
quartale_df = df[df['jahr_opdatum'].isin(jahr_filter)][['jahr_opdatum', 'quartal_opdatum']].drop_duplicates()

# Sortieren: zuerst Jahr, dann Quartal (Q1-Q4)
quartale_df = quartale_df.sort_values(['jahr_opdatum', 'quartal_opdatum'])

# Liste der Quartale für st.multiselect erstellen
quartale_options = quartale_df['quartal_opdatum'].tolist()  #nur echte Quartale, keine Trennzeilen ---

quartal_filter = st.multiselect(
    "Quartal auswählen:",
    options=quartale_options,
    default=quartale_options  #alle Quartale standardmässig auswählen ---
)

# Filter anwenden
if quartal_filter:
    filtered_df = filtered_df[filtered_df['quartal_opdatum'].isin(quartal_filter)]
    
# Bereich
bereich_filter = st.selectbox(
    "Bereich auswählen:",
    ["Alle"] + sorted(df['bereich'].dropna().unique())
)

if bereich_filter != "Alle":
    filtered_df = filtered_df[filtered_df['bereich'] == bereich_filter]


# Zugang
zugang_filter = st.selectbox(
    "Zugang auswählen:",
    ["Alle"] + sorted(df['zugang'].dropna().unique())
)
if zugang_filter != "Alle":
    filtered_df = filtered_df[filtered_df['zugang'] == zugang_filter] 

    

# -------- Kennzahlen --------
st.subheader("Kennzahlen")

col1, col2, col3 = st.columns(3)

col1.metric("Gesamt Fälle", len(filtered_df))

avg_dindo = filtered_df['max_dindo_calc_surv'].mean()
col2.metric(
    "Ø Clavien-Dindo",
    f"{avg_dindo:.2f}" if pd.notna(avg_dindo) else "N/A"
)

col3.metric("Bereiche", filtered_df['bereich'].nunique())

# -------- Visualisierungen --------
st.subheader("Visualisierungen")
col1, col2 = st.columns(2)

# --- Farbdictionary pro Jahr ---
jahre_unique = sorted(filtered_df['jahr_opdatum'].unique())
farben = {jahr: f"rgb({50+jahr%5*40},{100+jahr%3*50},{150+jahr%4*30})" for jahr in jahre_unique}

# --- Jahr ---
#jahr_counts = filtered_df['jahr_opdatum'].value_counts().sort_index()
#st.plotly_chart(
 #   px.bar(
 #       x=jahr_counts.index,
 #       y=jahr_counts.values,
 #       labels={'x': 'Jahr', 'y': 'Anzahl Fälle'},
 #       title="Fallzahlen pro Jahr"
 #   )
#)

# --- Quartal ---
#quartal_counts = filtered_df['quartal_opdatum'].value_counts().sort_index()
#st.plotly_chart(
 #   px.bar(
 #       x=quartal_counts.index,
 #       y=quartal_counts.values,
 #       labels={'x': 'Quartal', 'y': 'Anzahl Fälle'},
 #       title="Fallzahlen pro Quartal"
 #   )
#)

# --- Graph 1: Fallzahlen pro Jahr ---
jahr_counts_df = filtered_df.groupby('jahr_opdatum').size().reset_index(name='count')
fig_jahr = px.bar(
    jahr_counts_df,
    x='jahr_opdatum',
    y='count',
    color='jahr_opdatum',
    #color_discrete_map=farben,
    #labels={'jahr_opdatum':'Jahr','count':'Anzahl Fälle'},
    title="Fallzahlen pro Jahr"
)
col1.plotly_chart(fig_jahr, use_container_width=True)

# --- Graph 2: Fallzahlen pro Quartal (farblich nach Jahr) ---
quartal_counts_df = (
    filtered_df.groupby(['quartal_opdatum', 'jahr_opdatum'])
    .size()
    .reset_index(name='count')
)
fig_quartal = px.bar(
    quartal_counts_df,
    x='quartal_opdatum',
    y='count',
    color='jahr_opdatum',
    #color_discrete_map=farben,
    #labels={'quartal_opdatum':'Quartal','count':'Anzahl Fälle','jahr_opdatum':'Jahr'},
    title="Fallzahlen pro Quartal"
)
col2.plotly_chart(fig_quartal, use_container_width=True)

st.plotly_chart(
    px.pie(
        filtered_df,
        names='bereich',
        title="Verteilung nach Bereich"
    )
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

# -------- Trendanalyse --------
if 'jahr_opdatum' in filtered_df.columns and 'bereich' in filtered_df.columns:
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


#if df is not None:
#    df = prepare_data(df)
#    app = create_dashboard(df)
