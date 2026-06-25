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

# LIMPIEZA AUTOMÁTICA POR SI HAY ESPACIOS INVISIBLES
API_KEY = str(API_KEY).strip()

st.title("⚽ Predictor de Corners Automatizado")
st.write("Datos en tiempo real integrados de forma segura.")

# SISTEMA INTELIGENTE DE AUTO-DETECCIÓN DE SERVIDOR
@st.cache_data(ttl=60)
def get_live_fixtures():
    # Intento 1: Servidor Directo de API-Sports
    url_directa = "https://api-sports.io"
    headers_directa = {'x-apisports-key': API_KEY}
    
    # Intento 2: Servidor Alternativo por RapidAPI
    url_rapid = "https://rapidapi.com"
    headers_rapid = {
        'x-rapidapi-key': API_KEY,
        'x-rapidapi-host': "://rapidapi.com"
    }
    
    # Ejecutar Intento 1
    try:
        response = requests.get(url_directa, headers=headers_directa)
        if response.status_code == 200 and not response.json().get("errors"):
            st.success("✅ Conectado exitosamente al servidor Directo")
            return procesar_json_partidos(response.json()), "directo"
    except:
        pass
        
    # Si falla el 1, Ejecutar Intento 2 (RapidAPI)
    try:
        response = requests.get(url_rapid, headers=headers_rapid)
        if response.status_code == 200 and not response.json().get("errors"):
            st.success("✅ Conectado exitosamente al servidor RapidAPI")
            return procesar_json_partidos(response.json()), "rapidapi"
        elif response.status_code == 403:
            st.error("🚨 Error 403: Tu API Key no tiene un plan activo o es inválida en ambos servidores.")
    except Exception as e:
        st.error(f"❌ Error crítico de red: {e}")
        
    return {}, "error"

def procesar_json_partidos(data):
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
    return matches

# Llamada inicial
live_matches, tipo_servidor = get_live_fixtures()

if not live_matches:
    st.warning("No hay partidos en vivo disponibles usando esta credencial.")
    selected_match_label = None
else:
    selected_match_label = st.sidebar.selectbox("Selecciona un partido en vivo:", list(live_matches.keys()))

def get_match_stats(fixture_id, servidor):
    if servidor == "directo":
        url = f"https://api-sports.io{fixture_id}"
        headers = {'x-apisports-key': API_KEY}
    else:
        url = f"https://://rapidapi.com/v3/fixtures/statistics?fixture={fixture_id}"
        headers = {'x-rapidapi-key': API_KEY, 'x-rapidapi-host': "://rapidapi.com"}
        
    try:
        response = requests.get(url, headers=headers).json()
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

# --- PESTAÑAS ---
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
        c_home, c_away = get_match_stats(match_data["id"], tipo_servidor)
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
        
        st.subheader("Resultados de la Proyección")
        c1, c2, c3 = st.columns(3)
        c1.metric("Corners Reales", f"{corners_1t_input}")
        c2.metric("Previstos Restantes", f"{corners_esperados_futuro:.2f}")
        c3.metric("Total Final Proyectado", f"{total_proyectado:.2f}")
        
        prob_mas_de_8 = (1 - poisson.cdf(8 - corners_1t_input, corners_esperados_futuro)) * 100
        st.write(f"📈 Probabilidad de **Más de 8.5 corners totales**: **{max(0.0, min(100.0, prob_mas_de_8)):.1f}%**")
