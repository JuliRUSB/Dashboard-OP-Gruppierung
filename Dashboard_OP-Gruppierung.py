import requests
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from dash import Dash, dcc, html, Input, Output
import dash_bootstrap_components as dbc
import urllib3
import os
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def export_redcap_data(api_url):
    API_TOKEN = os.getenv("tok_op_gruppen")  # Umgebungsvariable mit Token
    data = {
        'token': API_TOKEN,
        'content': 'record',
        'action': 'export',
        'format': 'json',
        'type': 'flat',
        'csvDelimiter': '',
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
        print(f"✓ {len(df)} Datensätze erfolgreich exportiert")
        print(f"✓ Variablen: {list(df.columns)}")
        return df
    except requests.exceptions.RequestException as e:
        print(f"✗ Fehler beim Export: {e}")
        return None

def prepare_data(df):
    df = df.copy()
    bereich_cols = [col for col in df.columns if col.startswith('bereich___')]
    
    if bereich_cols:
        bereich_mapping = {
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
            bereiche = []
            for col, label in bereich_mapping.items():
                if col in row.index and row[col] == '1':
                    bereiche.append(label)
            return ', '.join(bereiche) if bereiche else 'Nicht angegeben'
        
        df['bereich'] = df.apply(get_bereich, axis=1)
        df = df.drop(columns=bereich_cols)
    df['jahr_opdatum'] = pd.to_numeric(df['jahr_opdatum'], errors='coerce')
    df['max_dindo_calc_surv'] = pd.to_numeric(df['max_dindo_calc_surv'], errors='coerce')
    df = df.dropna(subset=['jahr_opdatum'])
    return df

def create_dashboard(df):
    app = Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP])
    
    app.layout = dbc.Container([
        dbc.Row([
            dbc.Col([
                html.H1("OP-Gruppierung", className="text-center mb-4"),
            ])
        ]),
        
        dbc.Row([
            dbc.Col([
                html.Label("Jahr auswählen:"),
                dcc.Dropdown(
                    id='jahr-filter',
                    options=[{'label': 'Alle', 'value': 'alle'}] + 
                            [{'label': str(int(j)), 'value': j} 
                             for j in sorted(df['jahr_opdatum'].dropna().unique())],
                    value='alle',
                    clearable=False
                )
            ], width=3),
            
            dbc.Col([
                html.Label("Bereich auswählen:"),
                dcc.Dropdown(
                    id='bereich-filter',
                    options=[{'label': 'Alle', 'value': 'alle'}] + 
                            [{'label': b, 'value': b} 
                             for b in sorted(df['bereich'].dropna().unique())],
                    value='alle',
                    clearable=False
                )
            ], width=3),
            
            dbc.Col([
                html.Label("Zugang auswählen:"),
                dcc.Dropdown(
                    id='zugang-filter',
                    options=[{'label': 'Alle', 'value': 'alle'}] + 
                            [{'label': z, 'value': z} 
                             for z in sorted(df['zugang'].dropna().unique())],
                    value='alle',
                    clearable=False
                )
            ], width=3),
        ], className="mb-4"),
        
        dbc.Row([
            dbc.Col([
                dbc.Card([
                    dbc.CardBody([
                        html.H4("Gesamt Fälle", className="card-title"),
                        html.H2(id="total-cases", className="text-primary")
                    ])
                ])
            ], width=3),
            
            dbc.Col([
                dbc.Card([
                    dbc.CardBody([
                        html.H4("Ø Clavien-Dindo", className="card-title"),
                        html.H2(id="avg-dindo", className="text-info")
                    ])
                ])
            ], width=3),
            
            dbc.Col([
                dbc.Card([
                    dbc.CardBody([
                        html.H4("Bereiche", className="card-title"),
                        html.H2(id="unique-bereiche", className="text-success")
                    ])
                ])
            ], width=3),
        ], className="mb-4"),
        
        dbc.Row([
            dbc.Col([
                dcc.Graph(id='jahr-verteilung')
            ], width=6),
            
            dbc.Col([
                dcc.Graph(id='bereich-verteilung')
            ], width=6),
        ], className="mb-4"),
        
        dbc.Row([
            dbc.Col([
                dcc.Graph(id='dindo-verteilung')
            ], width=6),
            
            dbc.Col([
                dcc.Graph(id='zugang-verteilung')
            ], width=6),
        ], className="mb-4"),
        
        dbc.Row([
            dbc.Col([
                dcc.Graph(id='trend-analyse')
            ], width=12),
        ]),
        
    ], fluid=True)
    
    @app.callback(
        [Output('total-cases', 'children'),
         Output('avg-dindo', 'children'),
         Output('unique-bereiche', 'children'),
         Output('jahr-verteilung', 'figure'),
         Output('bereich-verteilung', 'figure'),
         Output('dindo-verteilung', 'figure'),
         Output('zugang-verteilung', 'figure'),
         Output('trend-analyse', 'figure')],
        [Input('jahr-filter', 'value'),
         Input('bereich-filter', 'value'),
         Input('zugang-filter', 'value')]
    )
    def update_dashboard(jahr, bereich, zugang):
        filtered_df = df.copy()
        
        if jahr != 'alle':
            filtered_df = filtered_df[filtered_df['jahr_opdatum'] == jahr]
        if bereich != 'alle':
            filtered_df = filtered_df[filtered_df['bereich'] == bereich]
        if zugang != 'alle':
            filtered_df = filtered_df[filtered_df['zugang'] == zugang]
        
        total = len(filtered_df)
        avg_dindo = filtered_df['max_dindo_calc_surv'].mean()
        avg_dindo_str = f"{avg_dindo:.2f}" if pd.notna(avg_dindo) else "N/A"
        unique_bereiche = filtered_df['bereich'].nunique()
        
        jahr_counts = filtered_df['jahr_opdatum'].value_counts().sort_index()
        fig_jahr = px.bar(
            x=jahr_counts.index, 
            y=jahr_counts.values,
            labels={'x': 'Jahr', 'y': 'Anzahl Fälle'},
            title='Fallzahlen pro Jahr'
        )
        
        bereich_counts = filtered_df['bereich'].value_counts()
        fig_bereich = px.pie(
            values=bereich_counts.values,
            names=bereich_counts.index,
            title='Verteilung nach Bereich'
        )
        
        dindo_counts = filtered_df['max_dindo_calc_surv'].value_counts().sort_index()
        fig_dindo = px.bar(
            x=dindo_counts.index,
            y=dindo_counts.values,
            labels={'x': 'Clavien-Dindo Grad', 'y': 'Anzahl'},
            title='Clavien-Dindo Komplikationen'
        )
        
        zugang_counts = filtered_df['zugang'].value_counts()
        fig_zugang = px.bar(
            x=zugang_counts.index,
            y=zugang_counts.values,
            labels={'x': 'Zugang', 'y': 'Anzahl'},
            title='Verteilung nach Zugangsart'
        )
        
        if 'jahr_opdatum' in filtered_df.columns and 'bereich' in filtered_df.columns:
            trend_data = filtered_df.groupby(['jahr_opdatum', 'bereich']).size().reset_index(name='count')
            fig_trend = px.line(
                trend_data,
                x='jahr_opdatum',
                y='count',
                color='bereich',
                labels={'jahr_opdatum': 'Jahr', 'count': 'Anzahl Fälle'},
                title='Trend über Zeit nach Bereich'
            )
        else:
            fig_trend = go.Figure()
        
        return (total, avg_dindo_str, unique_bereiche, 
                fig_jahr, fig_bereich, fig_dindo, fig_zugang, fig_trend)
    
    return app

# Lokaler Export / Test – auf Streamlit Cloud nicht nötig
# if __name__ == "__main__":
#     API_URL = 'https://fxdb.usb.ch/api/'
#     
#     print("Starte REDCap Export...")
#     df = export_redcap_data(API_URL)
#     
#     if df is not None:
#         print("\nBereite Daten vor...")
#         df = prepare_data(df)
#         
#         print("\nErstelle Dashboard...")
#         app = create_dashboard(df)
#         
#         print("\n" + "="*50)
#         print("Dashboard läuft unter: http://127.0.0.1:8050/")
#         print("Öffne diese URL in deinem Browser!")
#         print("Drücke Ctrl+C zum Beenden")
#         print("="*50 + "\n")
#         
#         try:
#             get_ipython()
#             app.run(debug=True, mode='inline', port=8050)
#         except:
#             app.run(debug=True, port=8050)
#     else:
#         print("Export fehlgeschlagen. Bitte API URL und Token prüfen.")

# Für Streamlit Cloud einfach die App definieren
API_URL = 'https://fxdb.usb.ch/api/'
df = export_redcap_data(API_URL)

if df is not None:
    df = prepare_data(df)
    app = create_dashboard(df)
