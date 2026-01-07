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
        'fields[0]': 'jahr_opdatum',
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
    df['jahr_opdatum'] = pd.to_numeric(df['jahr_opdatum'], errors='coerce').astype('Int64')  # Jahr als Integer anzeigen
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

    # -------- Filter --------
    # -------- Filter für Jahr (Mehrfachauswahl + "Alle") --------
    jahre = sorted(df['jahr_opdatum'].dropna().unique())
    jahr_filter = st.multiselect(
        "Jahr auswählen:",
        options=["Alle"] + jahre,
        default=["Alle"]  # standardmäßig Alle ausgewählt
    )

    filtered_df = df.copy()
    if not ("Alle" in jahr_filter):
        filtered_df = filtered_df[filtered_df['jahr_opdatum'].isin(jahr_filter)]



    bereich_filter = st.selectbox(
        "Bereich auswählen:",
        ["Alle"] + sorted(df['bereich'].dropna().unique())
    )

    zugang_filter = st.selectbox(
        "Zugang auswählen:",
        ["Alle"] + sorted(df['zugang'].dropna().unique())
    )

    # Daten filtern
    filtered_df = df.copy()

    if jahr_filter != "Alle":
         filtered_df = filtered_df[filtered_df['jahr_opdatum'].isin(jahr_filter)]

    if bereich_filter != "Alle":
        filtered_df = filtered_df[filtered_df['bereich'] == bereich_filter]

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

    st.plotly_chart(
        px.bar(
            filtered_df['jahr_opdatum'].value_counts().sort_index(),
            title="Fallzahlen pro Jahr"
        )
    )

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
