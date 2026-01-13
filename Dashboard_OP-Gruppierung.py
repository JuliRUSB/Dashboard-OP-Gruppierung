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
API_URL = "https://fxdb.usb.ch/api/"

# ==================================================
# Datenexport aus REDCap
# ==================================================
def export_redcap_data(api_url):
    API_TOKEN = os.getenv("tok_op_gruppen")

    data = {
        "token": API_TOKEN,
        "content": "record",
        "action": "export",
        "format": "json",
        "type": "flat",
        "fields[0]": "opdatum",
        "fields[1]": "bereich",
        "fields[2]": "hsm",
        "fields[3]": "zugang",
        "fields[4]": "max_dindo_calc_surv",
        "rawOrLabel": "raw",
        "rawOrLabelHeaders": "raw",
        "exportCheckboxLabel": "false",
        "exportSurveyFields": "false",
        "exportDataAccessGroups": "false",
        "returnFormat": "json",
    }

    r = requests.post(api_url, data=data, verify=False)
    r.raise_for_status()
    return pd.DataFrame(r.json())

# ==================================================
# Datenaufbereitung
# ==================================================
def prepare_data(df):
    df = df.copy()
    df["opdatum"] = pd.to_datetime(df["opdatum"], errors="coerce")

    # Bereich (Checkboxen)
    bereich_cols = [c for c in df.columns if c.startswith("bereich___")]
    if bereich_cols:
        mapping = {
            "bereich___1": "Allgemein",
            "bereich___2": "BMC",
            "bereich___3": "Endokrin",
            "bereich___4": "Chirurgische Onkologie/Sarkome",
            "bereich___5": "Hernien",
            "bereich___6": "Kolorektal",
            "bereich___7": "Leber",
            "bereich___8": "Pankreas",
            "bereich___9": "Upper-GI",
        }

        def get_bereich(row):
            return ", ".join(
                label for col, label in mapping.items() if row.get(col) == "1"
            ) or "Nicht angegeben"

        df["bereich"] = df.apply(get_bereich, axis=1)
        df = df.drop(columns=bereich_cols)

    # Zugang
    zugang_mapping = {
        1: "Offen",
        2: "Laparoskopisch",
        3: "roboter-assistiert",
        4: "konvertiert",
        5: "hybrid (2Höhlen-Eingriffe)",
    }
    df["zugang"] = pd.to_numeric(df["zugang"], errors="coerce").map(zugang_mapping).fillna("Unbekannt")

    # Zeitfelder
    df["jahr_opdatum"] = df["opdatum"].dt.year.astype("Int64")
    df["quartal_opdatum"] = (
        df["opdatum"]
        .dt.to_period("Q")
        .astype(str)
        .str.replace(r"(\d{4})Q(\d)", r"Q\2-\1", regex=True)
    )
    df["max_dindo_calc_surv"] = pd.to_numeric(df["max_dindo_calc_surv"], errors="coerce")
    df = df.dropna(subset=["jahr_opdatum"])

    return df

# ==================================================
# Streamlit App
# ==================================================
st.title("OP-Gruppierung Dashboard")

df = prepare_data(export_redcap_data(API_URL))

# ==================================================
# Filter
# ==================================================
jahre = sorted(df["jahr_opdatum"].dropna().astype(int).unique())
jahr_filter = st.multiselect("Jahr auswählen:", jahre, default=jahre)

quartale_df = (
    df[df["jahr_opdatum"].isin(jahr_filter)]
    [["jahr_opdatum", "quartal_opdatum"]]
    .drop_duplicates()
    .sort_values(["jahr_opdatum", "quartal_opdatum"])
)

quartal_filter = st.multiselect(
    "Quartal auswählen:",
    quartale_df["quartal_opdatum"].tolist(),
    default=quartale_df["quartal_opdatum"].tolist(),
)

bereich_filter = st.selectbox(
    "Bereich auswählen:",
    ["Alle"] + sorted(df["bereich"].dropna().unique()),
)

zugang_filter = st.selectbox(
    "Zugang auswählen:",
    ["Alle"] + sorted(df["zugang"].dropna().unique()),
)

# ==================================================
# Datenzustand
# ==================================================
df_jahr = df[df["jahr_opdatum"].isin(jahr_filter)]

if bereich_filter != "Alle":
    df_jahr = df_jahr[df_jahr["bereich"] == bereich_filter]

if zugang_filter != "Alle":
    df_jahr = df_jahr[df_jahr["zugang"] == zugang_filter]

df_quartal = df_jahr.copy()
if quartal_filter:
    df_quartal = df_quartal[df_quartal["quartal_opdatum"].isin(quartal_filter)]

# ==================================================
# Kennzahlen
# ==================================================
st.subheader("Kennzahlen")
c1, c2, c3 = st.columns(3)

c1.metric("Gesamt Fälle", len(df_jahr))
c2.metric(
    "Ø Clavien-Dindo",
    f"{df_jahr['max_dindo_calc_surv'].mean():.2f}"
    if df_jahr["max_dindo_calc_surv"].notna().any()
    else "N/A",
)
c3.metric("Bereiche", df_jahr["bereich"].nunique())

# ==================================================
# Visualisierungen
# ==================================================
st.subheader("Visualisierungen")
col1, col2 = st.columns(2)

# --- pro Jahr ---
jahr_counts = df_jahr.groupby("jahr_opdatum").size().reset_index(name="count")
fig_jahr = px.bar(
    jahr_counts,
    x="jahr_opdatum",
    y="count",
    text="count",
    title="Fallzahlen pro Jahr",
)
fig_jahr.update_layout(xaxis_title=None, yaxis_title=None, showlegend=False)
col1.plotly_chart(fig_jahr, use_container_width=True)

# --- pro Quartal ---
quartal_counts = df_quartal.groupby("quartal_opdatum").size().reset_index(name="count")
fig_quartal = px.bar(
    quartal_counts,
    x="quartal_opdatum",
    y="count",
    text="count",
    title="Fallzahlen pro Quartal",
)
fig_quartal.update_layout(xaxis_title=None, yaxis_title=None, showlegend=False)
col2.plotly_chart(fig_quartal, use_container_width=True)

# ==================================================
# Weitere Plots
# ==================================================
st.plotly_chart(px.pie(df_jahr, names="bereich", title="Verteilung nach Bereich"))
st.plotly_chart(
    px.bar(
        df_jahr["max_dindo_calc_surv"].value_counts().sort_index(),
        title="Clavien-Dindo Komplikationen",
    )
)
st.plotly_chart(
    px.bar(df_jahr["zugang"].value_counts(), title="Verteilung nach Zugangsart")
)

# ==================================================
# Trendanalyse
# ==================================================
trend = (
    df_jahr.groupby(["jahr_opdatum", "bereich"])
    .size()
    .reset_index(name="count")
)

st.plotly_chart(
    px.line(
        trend,
        x="jahr_opdatum",
        y="count",
        color="bereich",
        title="Trend über Zeit nach Bereich",
    )
)
