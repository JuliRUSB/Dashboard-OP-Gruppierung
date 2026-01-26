# ==================================================
# Imports – Bibliotheken laden
# ==================================================
import plotly.graph_objects as go
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

# Globale Farbpalette
COLOR_PALETTE = px.colors.qualitative.Safe

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
    # Quartal als "Q1-2026"-Format
    df['quartal_opdatum'] = df['opdatum'].dt.to_period('Q').astype(str).str.replace(
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
        width: 300px !important; 
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
        "Operationsjahr durch Verschieben auswählen:",
        min_value=min_jahr,
        max_value=max_jahr,
        value=(min_jahr, max_jahr)
    )
    
    # 1. Sicherstellen, dass die Liste im Session State existiert
    if 'selected_quartale' not in st.session_state:
        st.session_state['selected_quartale'] = [1, 2, 3, 4]

    # 2. Definition der Variablen (Sicherstellen, dass sie existieren)
    quartal_labels = ["Q1", "Q2", "Q3", "Q4"]
    quartal_werte = [1, 2, 3, 4]
    
    st.write("Ausgewählte Quartale:", ", ".join([f"Q{q}" for q in sorted(st.session_state['selected_quartale'])]))

    # 3. Spalten für die Buttons erstellen
    cols = st.columns(4)
    
    # 4. Die Schleife
    for i, q in enumerate(quartal_werte):
        # Prüfung: Existiert cols[i] und quartal_labels[i]?
        button_label = quartal_labels[i]
        
        # Button-Logik
        if cols[i].button(button_label, key=f"btn_q_{q}"):
            if q in st.session_state['selected_quartale']:
                st.session_state['selected_quartale'].remove(q)
            else:
                st.session_state['selected_quartale'].append(q)
            st.rerun() # Seite neu laden, um Filter anzuwenden

    # Jahre speichern
    st.session_state['selected_jahre'] = list(range(jahr_range[0], jahr_range[1]+1))

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
df_jahr_filtered = df[df['jahr_opdatum'].isin(st.session_state['selected_jahre'])].copy()
df_filtered = df[
    (df['jahr_opdatum'].isin(st.session_state['selected_jahre'])) &
    (df['quartal_opdatum'].isin(st.session_state['selected_quartale']))
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
    st.metric("Bereiche", df_filtered['bereich'].nunique())  # Anzahl verschiedener Bereiche
    
with col3:
    st.metric("Zeitraum", f"{len(st.session_state['selected_jahre'])} Jahre, {len(st.session_state['selected_quartale'])} Quartale")  # Zeitraum anzeigen

st.divider()

# -------- Visualisierungen --------
st.header("Fallzahlen Übersicht")

if len(df_filtered) == 0:
    st.warning("Keine Daten für die gewählten Filter verfügbar.")
    st.stop()

col1, col2 = st.columns(2)  # Zwei Spalten für Graphen

# Graph 1: Jahr
with col1:
    if len(df_jahr_filtered) > 0:
        jahr_counts_df = df_jahr_filtered.groupby('jahr_opdatum', as_index=False).size()
        jahr_counts_df.columns = ['jahr_opdatum', 'count']
        jahr_counts_df['jahr_str'] = jahr_counts_df['jahr_opdatum'].astype(str)
        
        jahr_farben = get_color_map(jahr_counts_df['jahr_str'])
        marker_colors = [jahr_farben[str(jahr)] for jahr in jahr_counts_df['jahr_opdatum']]
        
        fig_jahr = px.bar(
            jahr_counts_df, 
            x='jahr_opdatum', 
            y='count', 
            text='count', 
            title="Fallzahlen pro Jahr"
        )
        fig_jahr.update_traces(marker_color=marker_colors, textfont_size=16, textposition='inside')
        fig_jahr.update_layout(xaxis_title=None, yaxis_title=None, showlegend=False, height=400)
        st.plotly_chart(fig_jahr, use_container_width=True)

# Graph 2: Quartal
with col2:
    if len(df_filtered) > 0:
        quartal_counts_df = df_filtered.groupby('quartal_opdatum', as_index=False).size()
        quartal_counts_df.columns = ['quartal_opdatum', 'count']
        
        quartal_counts_df['jahr'] = quartal_counts_df['quartal_opdatum'].str.split('-').str[1]
        quartal_farben = get_color_map(quartal_counts_df['jahr'])
        marker_colors_quartal = [quartal_farben[jahr] for jahr in quartal_counts_df['jahr']]
        
        fig_quartal = px.bar(
            quartal_counts_df, 
            x='quartal_opdatum', 
            y='count', 
            text='count', 
            title="Fallzahlen pro Quartal"
        )
        fig_quartal.update_traces(marker_color=marker_colors_quartal, textfont_size=16, textposition='inside')
        fig_quartal.update_layout(xaxis_title=None, yaxis_title=None, showlegend=False, height=400)
        st.plotly_chart(fig_quartal, use_container_width=True)

st.divider()

# -------- Weitere Analysen (Tabs) --------
st.header("Detailanalysen")
tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs(["Bereich", "Gruppen", "Zugang", "Komplikationen", "HSM", "Aufenthaltsdauer", "Trends"])

# Bereich-Piechart
with tab1:
    if df_filtered['bereich'].nunique() > 0:
        fig_bereich = px.pie(
            df_filtered, 
            names='bereich', 
            title="Verteilung nach Bereich", 
            hole=0.3,
            color_discrete_sequence=COLOR_PALETTE
        )
        st.plotly_chart(fig_bereich, use_container_width=True)
    else:
        st.info("Keine Bereichsdaten verfügbar")

# Leber-Gruppen-Balkendiagramm
with tab2:
    if df_filtered['leber_gruppen'].nunique() > 0:
        leber_gruppen_counts = (
            df_filtered
            .groupby(['jahr_opdatum', 'leber_gruppen'], as_index=False)
            .size()
        )
        leber_gruppen_counts.columns = ['jahr_opdatum', 'leber_gruppen', 'count']

        fig_leber_gruppen = px.bar(
            leber_gruppen_counts,
            x='jahr_opdatum',
            y='count',
            color='leber_gruppen',
            barmode='group',
            text='count',
            title="Verteilung nach Gruppen",
            labels={'leber_gruppen': 'Leber-Gruppen'},
            color_discrete_sequence=COLOR_PALETTE
        )
        fig_leber_gruppen.update_traces(textposition='inside', textfont_size=16)
        fig_leber_gruppen.update_layout(xaxis_title=None, yaxis_title=None)
        st.plotly_chart(fig_leber_gruppen, use_container_width=True)
    else:
        st.info("Keine Daten verfügbar")

# Zugang-Balkendiagramm
with tab3:
    if df_filtered['zugang'].nunique() > 0:
        zugang_counts = (
            df_filtered
            .groupby(['jahr_opdatum', 'zugang'], as_index=False)
            .size()
        )
        zugang_counts.columns = ['jahr_opdatum', 'zugang', 'count']

        fig_zugang = px.bar(
            zugang_counts,
            x='jahr_opdatum',
            y='count',
            color='zugang',
            barmode='group',
            text='count',
            title="Verteilung nach Zugangsart",
            color_discrete_sequence=COLOR_PALETTE
        )
        fig_zugang.update_traces(textposition='inside', textfont_size=16)
        fig_zugang.update_layout(xaxis_title=None, yaxis_title=None)
        st.plotly_chart(fig_zugang, use_container_width=True)
    else:
        st.info("Keine Zugangsdaten verfügbar")

# Komplikationen-Balkendiagramm (Clavien-Dindo)
with tab4:
    if df_filtered['max_dindo_calc'].notna().any():
        # Aggregation nach Jahr und Clavien-Dindo-Grad
        dindo_counts = (
            df_filtered
            .dropna(subset=['jahr_opdatum', 'max_dindo_calc'])
            .groupby(['jahr_opdatum', 'max_dindo_calc'], as_index=False)
            .size()
        )
        dindo_counts.columns = ['jahr_opdatum', 'dindo', 'count']
        dindo_counts['jahr_opdatum'] = dindo_counts['jahr_opdatum'].astype(str)

        # Reihenfolge der Dindo-Kategorien
        dindo_order = sorted(dindo_counts['dindo'].unique(), reverse=True)

        # Balkendiagramm erstellen
        fig_dindo = px.bar(
            dindo_counts,
            x='count',
            y='dindo',
            color='jahr_opdatum',
            orientation='h',
            barmode='group',
            title="Clavien-Dindo Komplikationen",
            color_discrete_sequence=COLOR_PALETTE,
            text='count'
        )

        # Balken-Einstellungen
        fig_dindo.update_traces(
            marker_line_width=1,
            textposition='outside',
            texttemplate='%{text}'
        )

        # Dynamische Höhe für mehr Abstand zwischen den Balken
        n_dindo = len(dindo_order)

        fig_dindo.update_layout(
            height=120 * n_dindo,
            bargap=0.001,
            bargroupgap=0.25,
            margin=dict(r=120),
            plot_bgcolor="rgba(0,0,0,0)",
            xaxis=dict(
                title=None,
                tickmode="linear",
                tick0=0,
                dtick=10
            ),
            yaxis=dict(
                title="Höchster Clavien-Dindo Grad",
                type="category",
                categoryorder="array",
                categoryarray=dindo_order,
                tickson="boundaries",
                showgrid=True,
                gridcolor="rgba(0,0,0,0.3)",
                gridwidth=1
            ),
            legend_title_text="Jahr"
        )

        st.plotly_chart(fig_dindo, use_container_width=True)
    else:
        st.info("Keine Komplikationsdaten verfügbar")

# HSM-Balkendiagramm
with tab5:
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
            color_discrete_sequence=COLOR_PALETTE
        )
        fig_hsm.update_traces(textposition='inside', textfont_size=18)
        fig_hsm.update_layout(xaxis_title=None, yaxis_title="Anzahl Fälle")
        st.plotly_chart(fig_hsm, use_container_width=True)
    else:
        st.info("Keine HSM-Informationen verfügbar")

# LOS (Length of Stay)
with tab6:
    df_los = df_filtered.copy()

    if len(df_los) == 0:
        st.info("Keine LOS-Daten verfügbar")
    else:
        # --- Berechnung 1: Eintritt/Austritt ---
        df_los['los_ea'] = pd.to_numeric(df_los['los_eintritt_austritt'], errors='coerce')
        valid_ea = df_los.dropna(subset=['los_ea'])
        
        # --- Berechnung 2: OP-Datum ---
        df_los['los_op'] = pd.to_numeric(df_los['los_opdatum'], errors='coerce')
        valid_op = df_los.dropna(subset=['los_op'])

        if valid_ea.empty and valid_op.empty:
            st.info("Keine gültigen LOS-Daten vorhanden")
        else:
            # Daten für Zeile 1 sammeln
            count_ea = valid_ea['los_ea'].count()
            mean_ea = valid_ea['los_ea'].mean() if count_ea > 0 else 0
            median_ea = valid_ea['los_ea'].median() if count_ea > 0 else 0

            # Daten für Zeile 2 sammeln
            count_op = valid_op['los_op'].count()
            mean_op = valid_op['los_op'].mean() if count_op > 0 else 0
            median_op = valid_op['los_op'].median() if count_op > 0 else 0

            # Zusammenführen in das DataFrame
            los_summary = pd.DataFrame({
                "Kategorie": [
                    "LOS (Eintrittsdatum/Austrittsdatum)", 
                    "LOS (OP-Datum/Austrittsdatum)"
                ],
                "Count": [count_ea, count_op],
                "Mean": [f"{mean_ea:.2f}", f"{mean_op:.2f}"],
                "Median": [f"{median_ea:.0f}", f"{median_op:.0f}"]
            })

            # Tabelle anzeigen
            st.markdown(los_summary.to_html(index=False, escape=False), unsafe_allow_html=True)
            
# Trends über Jahre nach Bereich
with tab7:
    if len(df_filtered) > 0 and df_filtered['bereich'].nunique() > 1:
        trend_data = df_filtered.groupby(['jahr_opdatum', 'bereich'], as_index=False).size()
        trend_data.columns = ['jahr_opdatum', 'bereich', 'count']
        
        fig_trend = px.line(
            trend_data, 
            x='jahr_opdatum', 
            y='count', 
            color='bereich', 
            title="Trend über Zeit nach Bereich", 
            markers=True,
            color_discrete_sequence=COLOR_PALETTE
        )
        st.plotly_chart(fig_trend, use_container_width=True)
    else:
        st.info("Nicht genügend Daten für Trendanalyse")
