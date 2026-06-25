import streamlit as st
import requests
import numpy as np
from scipy.stats import poisson

# CONFIGURACIÓN SEGURA DE LA API
# Streamlit leerá automáticamente la clave desde su panel de control oculto
try:
    API_KEY = st.secrets["API_FOOTBALL_KEY"]
except KeyError:
    st.error("⚠️ Falta configurar la API Key en los Secrets de Streamlit.")
    st.stop()

BASE_URL = "https://api-sports.io"
headers = {
    'x-apisports-key': API_KEY
}

st.title("⚽ Predictor de Corners Automatizado")
st.write("Datos en tiempo real integrados de forma segura.")

# --- (El resto del código de la API y las pestañas se mantiene igual) ---
@st.cache_data(ttl=60)
def get_live_fixtures():
    url = f"{BASE_URL}/fixtures?live=all"
    try:
        response = requests.get(url, headers=headers).json()
        matches = {}
        if "response" in response:
            for match in response["response"]:
                fixture_id = match["fixture"]["id"]
                home_team = match["teams"]["home"]["name"]
                away_team = match["teams"]["away"]["name"]
                status = match["fixture"]["status"]["short"]
                elapsed = match["fixture"]["status"]["elapsed"]
                
                label = f"{home_team} vs {away_team} ({status} - Min {elapsed}')"
                matches[label] = {
                    "id": fixture_id, "home": home_team, "away": away_team, 
                    "status": status, "elapsed": elapsed
                }
        return matches
    except Exception as e:
        st.error(f"Error al conectar con la API: {e}")
        return {}

live_matches = get_live_fixtures()

if not live_matches:
    st.warning("No hay partidos en vivo en este momento o la API Key es inválida.")
    selected_match_label = None
else:
    selected_match_label = st.sidebar.selectbox("Selecciona un partido en vivo:", list(live_matches.keys()))

def get_match_stats(fixture_id):
    url = f"{BASE_URL}/fixtures/statistics?fixture={fixture_id}"
    response = requests.get(url, headers=headers).json()
    corners_home, corners_away = 0, 0
    if "response" in response and len(response["response"]) >= 2:
        for stat in response["response"][0]["statistics"]:
            if stat["type"] == "Corner Kicks": corners_home = stat["value"] or 0
        for stat in response["response"][1]["statistics"]:
            if stat["type"] == "Corner Kicks": corners_away = stat["value"] or 0
    return corners_home, corners_away

tab1, tab2 = st.tabs([" Bars Simulación Pre-Partido", "⏱️ Proyección En Vivo (2T)"])

with tab1:
    st.header("Análisis de Medias Previas")
    col1, col2 = st.columns(2)
    with col1:
        cf_local = st.number_input("Corners Históricos a Favor - Local", min_value=0.0, value=5.2)
        cc_visita = st.number_input("Corners Históricos en Contra - Visita", min_value=0.0, value=4.8)
    with col2:
        cf_visita = st.number_input("Corners Históricos a Favor - Visita", min_value=0.0, value=4.1)
        cc_local = st.number_input("Corners Históricos en Contra - Local", min_value=0.0, value=3.9)
    prom_liga = st.number_input("Media general de la Liga", min_value=1.0, value=9.5)
    lambda_local = (cf_local / prom_liga) * (cc_visita / prom_liga) * (prom_liga / 2)
    lambda_visita = (cf_visita / prom_liga) * (cc_local / prom_liga) * (prom_liga / 2)
    lambda_total_pre = lambda_local + lambda_visita
    st.metric("Expectativa Total Calculada (Lambda)", f"{lambda_total_pre:.2f}")

with tab2:
    st.header("Módulo de Tiempo Real")
    if selected_match_label and live_matches:
        match_data = live_matches[selected_match_label]
        c_home, c_away = get_match_stats(match_data["id"])
        corners_reales_actuales = c_home + c_away
        st.info(f"🏟️ **Datos API:** {match_data['home']} ({c_home}) - ({c_away}) {match_data['away']}")
        corners_1t_input = st.number_input("Corners actuales detectados", value=int(corners_reales_actuales))
        minuto_actual = match_data["elapsed"] or 45
    else:
        corners_1t_input = st.number_input("Corners del primer tiempo (Manual)", min_value=0, value=4)
        minuto_actual = 45

    if st.button("Proyectar 2do Tiempo con datos API"):
        minutos_restantes = max(90 - minuto_actual, 0)
        corners_por_minuto = lambda_total_pre / 90
        corners_esperados_futuro = corners_por_minuto * minutos_restantes
        total_proyectado = corners_1t_input + corners_esperados_futuro
        
        st.subheader("Resultados de la Proyección en Vivo")
        c1, c2, c3 = st.columns(3)
        c1.metric("Corners Reales", f"{corners_1t_input}")
        c2.metric("Previstos Restantes", f"{corners_esperados_futuro:.2f}")
        c3.metric("Total Final Proyectado", f"{total_proyectado:.2f}")
        
        prob_mas_de_8 = (1 - poisson.cdf(8 - corners_1t_input, corners_esperados_futuro)) * 100
        st.write(f"📈 Probabilidad de **Más de 8.5 corners totales**: **{max(0.0, min(100.0, prob_mas_de_8)):.1f}%**")
