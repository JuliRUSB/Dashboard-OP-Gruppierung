# -------- Weitere Analysen (Tabs) --------
st.header("Detailanalysen")
tab1, tab2, tab3, tab4, tab5 =st.tabs(["Bereich", "Zugang", "Komplikationen", "HSM", "Trends"])

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
        fig_zugang.update_traces(textposition='outside')
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
        fig_dindo.update_traces(marker_color=dindo_farben, textposition='outside')
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
        fig_hsm.update_traces(textposition='inside', textfont_size=18)
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
