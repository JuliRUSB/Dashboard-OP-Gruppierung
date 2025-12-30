import os
import requests
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def export_redcap_data(api_url):
    API_TOKEN = os.getenv("tok_op_gruppen")
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
        r = requests.post(api_url, data=data, verify=False)
        r.raise_for_status()
        df = pd.DataFrame(r.json())
        return df
    except requests.exceptions.RequestException as e:
        st.error(f"Fehler beim Export: {e}")
        return None

def prepare_data(df):
    df = df.copy()
    bereich_cols = [col for col in df.columns if col.startswith('bereich___')]
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
            return ', '.join([label for col, label in mapping.items() if row.get(col) == '1']) or 'Nicht angegeben'
        df['bereich'] = df.apply(get_bereich, axis=1)
        df = df.drop(columns=bereich_cols)
    df['jahr_opdatum'] = pd.to_numeric(df['jahr_opdatum'], errors='coerce')
    df['max_dindo_calc_surv'] = pd.to_numeric(df['max_dindo_calc_surv'], errors='coerce')
    df = df.dropna(subset=['jahr_opdatum'])
    return df

# Streamlit App
st.title("OP-Gruppierung Dashboard")

API_URL = 'https://fxdb.usb.ch/api/'
df = export_redcap_data(API_URL)

if df is not None:
    df = prepare_data(df)

    jahr_filter = st.selectbox("Jahr auswählen:", ["Alle"] + sorted(df['jahr_opdatum'].dropna().unique()))
    bereich_filter = st.selectbox("Bereich auswählen:", ["Alle"] + sorted(df['bereich'].dropna().unique()))
    zugang_filter = st.selectbox("Zugang auswählen:", ["Alle"] + sorted(df['zugang'].dropna().unique()))

    filtered_df = df.copy()
    if jahr_filter != "Alle":
        filtered_df = filtered_df[filtered_df['jahr_opdatum'] == jahr_filter]
    if bereich_filter != "Alle":
        filtered_df = filtered_df[filtered_df['bereich'] == bereich_filter]
    if zugang_filter != "Alle":
        filtered_df = filtered_df[filtered_df['zugang'] == zugang_filter]

    st.subheader("Kennzahlen")
    col1, col2, col3 = st.columns(3)
    col1.metric("Gesamt Fälle", len(filtered_df))
    avg_dindo = filtered_df['max_dindo_calc_surv'].mean()
    col2.metric("Ø Clavien-Dindo", f"{avg_dindo:.2f}" if pd.notna(avg_dindo) else "N/A")
    col3.metric("Bereiche", filtered_df['bereich'].nunique())

    st.subheader("Visualisierungen")
    st.plotly_chart(px.bar(filtered_df['jahr_opdatum'].value_counts().sort_index(), title="Fallzahlen pro Jahr"))
    st.plotly_chart(px.pie(filtered_df, names='bereich', title="Verteilung nach Bereich"))
    st.plotly_chart(px.bar(filtered_df['max_dindo_calc_surv'].value_counts().sort_index(), title="Clavien-Dindo Komplikationen"))
    st.plotly_chart(px.bar(filtered_df['zugang'].value_counts(), title="Verteilung nach Zugangsart"))

    if 'jahr_opdatum' in filtered_df.columns and 'bereich' in filtered_df.columns:
        trend_data = filtered_df.groupby(['jahr_opdatum', 'bereich']).size().reset_index(name='count')
        st.plotly_chart(px.line(trend_data, x='jahr_opdatum', y='count', color='bereich', title="Trend über Zeit nach Bereich"))


if df is not None:
    df = prepare_data(df)
    app = create_dashboard(df)
