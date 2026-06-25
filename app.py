import streamlit as st
import requests
import numpy as np
from scipy.stats import poisson

# CONFIGURACIÓN SEGURA DE LA API
try:
    API_KEY = st.secrets["API_FOOTBALL_KEY"]
except KeyError:
    st.error("⚠️ Falta configurar la API Key en los Secrets de Streamlit.")
    st.stop()

# Limpieza por seguridad
API_KEY = str(API_KEY).strip()

st.title("⚽ Predictor de Corners Automatizado")
st.write("Datos en tiempo real integrados de forma segura.")

@st.cache_data(ttl=60)
def get_live_fixtures():
    url = "https://api-sports.io"
    headers = {'x-apisports-key': API_KEY}
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code != 200:
            return {}, f"Error de Servidor (Código HTTP {response.status_code})"
            
        data = response.json()
        
        if "errors" in data and data["errors"]:
            return {}, f"Error de la API: {data['errors']}"
            
        matches = {}
        if "response" in data:
            for match in data["response"]:
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
        return matches, "OK"
    except Exception as e:
        return {}, f"No se pudo decodificar el formato. Modo manual activado."

# Intentar lectura
live_matches, estado_api = get_live_fixtures()

# Mostrar notificaciones limpias según el estado de la conexión
if estado_api == "OK" and live_matches:
    st.success("✅ Conexión exitosa. Partidos en vivo detectados.")
    selected_match_label = st.sidebar.selectbox("Selecciona un partido en vivo:", list(live_matches.keys()))
else:
    if estado_api != "OK":
        st.info(f"ℹ️ {estado_api}")
    st.warning("⚠️ No se detectaron partidos en vivo. Puedes usar el Módulo Manual abajo.")
    selected_match_label = None

def get_match_stats(fixture_id):
    url = f"https://api-sports.io{fixture_id}"
    headers = {'x-apisports-key': API_KEY}
    try:
        response = requests.get(url, headers=headers, timeout=10).json()
        corners_home, corners_away = 0, 0
        if "response" in response and len(response["response"]) >= 2:
            for item in response["response"]:
                team_name = item["team"]["name"]
                stats = item["statistics"]
                corners = 0
                for stat in stats:
                    if stat["type"] == "Corner Kicks":
                        corners = stat["value"] or 0
                
                if live_matches and selected_match_label:
                    if team_name == live_matches[selected_match_label]["home"]:
                        corners_home = corners
                    else:
                        corners_away = corners
        return corners_home, corners_away
    except:
        return 0, 0

# --- DISPARADORES DE PESTAÑAS ---
tab1, tab2 = st.tabs(["📊 Simulación Pre-Partido", "⏱️ Proyección En Vivo (2T)"])

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
        corners_1t_input = st.number_input("Corners acumulados (Ingreso Manual)", min_value=0, value=4)
        minuto_actual = st.number_input("Minuto actual del partido", min_value=1, max_value=90, value=45)

    if st.button("Proyectar 2do Tiempo"):
        minutos_restantes = max(90 - minuto_actual, 0)
        corners_por_minuto = lambda_total_pre / 90
        corners_esperados_futuro = corners_por_minuto * minutos_restantes
        total_proyectado = corners_1t_input + corners_esperados_futuro
        
        st.subheader("Resultados de la Proyección")
        c1, c2, c3 = st.columns(3)
        c1.metric("Corners Reales", f"{corners_1t_input}")
        c2.metric("Previstos Restantes", f"{corners_esperados_futuro:.2f}")
        c3.metric("Total Final Proyectado", f"{total_proyectado:.2f}")
        
        prob_mas_de_8 = (1 - poisson.cdf(8 - corners_1t_input, corners_esperados_futuro)) * 100
        st.write(f"📈 Probabilidad de **Más de 8.5 corners totales**: **{max(0.0, min(100.0, prob_mas_de_8)):.1f}%**")
