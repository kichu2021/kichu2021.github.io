import streamlit as st
import numpy as np
import requests

# CONFIGURACIÓN SEGURA DE LA API (Se mantiene por si se activa en el futuro)
try:
    API_KEY = st.secrets["API_FOOTBALL_KEY"]
except KeyError:
    st.error("⚠️ Falta configurar la API Key en los Secrets de Streamlit.")
    st.stop()

API_KEY = str(API_KEY).strip()

st.set_page_config(page_title="Predictor Avanzado de Corners", layout="wide")
st.title("⚽ Predictor de Corners Pro (Poisson + Montecarlo)")
st.write("Análisis estadístico predictivo mediante simulaciones masivas.")

# LECTURA DE API CON CONTROL DE ERRORES BIEN CONTROLADO
@st.cache_data(ttl=60)
def get_live_fixtures():
    url = "https://api-sports.io"
    headers = {'x-apisports-key': API_KEY}
    try:
        response = requests.get(url, headers=headers, timeout=5)
        if response.status_code == 200:
            data = response.json()
            if "errors" in data and data["errors"]:
                return {}, "Modo manual activo"
            matches = {}
            if "response" in data:
                for match in data["response"]:
                    fid = match["fixture"]["id"]
                    h = match["teams"]["home"]["name"]
                    a = match["teams"]["away"]["name"]
                    status = match["fixture"]["status"]["short"]
                    elap = match["fixture"]["status"]["elapsed"]
                    matches[f"{h} vs {a} ({status} - Min {elap}')"] = {"id": fid, "home": h, "away": a, "status": status, "elapsed": elap}
            return matches, "OK"
    except:
        pass
    return {}, "Modo manual activo"

live_matches, estado_api = get_live_fixtures()
selected_match_label = None

if estado_api == "OK" and live_matches:
    st.success("✅ Conexión exitosa con la API.")
    selected_match_label = st.sidebar.selectbox("Selecciona un partido en vivo:", list(live_matches.keys()))
else:
    st.sidebar.info("ℹ️ Servidor en modo manual (Ingreso de datos 100% libre).")

def get_match_stats(fixture_id):
    url = f"https://api-sports.io{fixture_id}"
    headers = {'x-apisports-key': API_KEY}
    try:
        response = requests.get(url, headers=headers, timeout=5).json()
        c_h, c_a = 0, 0
        if "response" in response and len(response["response"]) >= 2:
            for item in response["response"]:
                team = item["team"]["name"]
                corners = next((s["value"] for s in item["statistics"] if s["type"] == "Corner Kicks"), 0) or 0
                if live_matches and selected_match_label:
                    if team == live_matches[selected_match_label]["home"]: c_h = corners
                    else: c_a = corners
        return c_h, c_a
    except:
        return 0, 0

# --- CÁLCULO DE EXPECTATIVA BASE ---
st.header("1. Parámetros de Medias Previas")
col_input1, col_input2, col_input3 = st.columns(3)

with col_input1:
    cf_local = st.number_input("Corners a Favor - Local", min_value=0.0, value=5.5, step=0.1)
    cc_local = st.number_input("Corners en Contra - Local", min_value=0.0, value=4.2, step=0.1)
with col_input2:
    cf_visita = st.number_input("Corners a Favor - Visita", min_value=0.0, value=4.1, step=0.1)
    cc_visita = st.number_input("Corners en Contra - Visita", min_value=0.0, value=5.0, step=0.1)
with col_input3:
    prom_liga = st.number_input("Media general de la Liga", min_value=1.0, value=9.5, step=0.1)
    n_simulaciones = st.selectbox("Número de Simulaciones Montecarlo", [5000, 10000, 20000], index=1)

# Cálculo matemático Lambda
lambda_local = (cf_local / prom_liga) * (cc_visita / prom_liga) * (prom_liga / 2)
lambda_visita = (cf_visita / prom_liga) * (cc_local / prom_liga) * (prom_liga / 2)
lambda_total_pre = lambda_local + lambda_visita

# --- PESTAÑAS DE ANÁLISIS ---
tab1, tab2 = st.tabs(["📊 Simulación Pre-Partido", "⏱️ Proyección En Vivo / 2T"])

# FUNCIÓN CENTRAL MONTECARLO
def simular_montecarlo(corners_base, minutos_restantes, lambda_total, n_sim):
    lambda_minuto = lambda_total / 90
    # Generamos una matriz de Poisson: filas = simulaciones, columnas = minutos restantes
    tiros_por_minuto = np.random.poisson(lambda_minuto, size=(n_sim, minutos_restantes))
    # Sumamos los corners generados en cada simulación al valor base inicial
    totales_simulados = corners_base + np.sum(tiros_por_minuto, axis=1)
    return totales_simulados

def mostrar_tabla_probabilidades(resultados_simulados):
    lineas = [7.5, 8.5, 9.5, 10.5, 11.5, 12.5]
    st.write("### 📈 Probabilidades de Mercados Disponibles")
    
    cols = st.columns(len(lineas))
    for i, linea in enumerate(lineas):
        prob = np.mean(resultados_simulados > linea) * 100
        cols[i].metric(f"Más de {linea}", f"{prob:.1f}%")

with tab1:
    st.subheader("Análisis Probabilístico Pre-Partido")
    st.metric("Expectativa de Corners del Partido (Lambda)", f"{lambda_total_pre:.2f}")
    
    if st.button("Ejecutar Simulador Pre-Partido"):
        with st.spinner("Corriendo algoritmos de Montecarlo..."):
            resultados_pre = simular_montecarlo(0, 90, lambda_total_pre, n_simulaciones)
            
            st.success(f"¡Simulación de {n_simulaciones} partidos completada!")
            st.write(f"**Promedio final simulado:** {np.mean(resultados_pre):.2f} corners.")
            st.write(f"**Mínimo detectado:** {np.min(resultados_pre)} | **Máximo detectado:** {np.max(resultados_pre)}")
            
            mostrar_tabla_probabilidades(resultados_pre)

with tab2:
    st.subheader("Módulo de Proyección en Tiempo Real")
    
    if selected_match_label and live_matches:
        match_data = live_matches[selected_match_label]
        c_h, c_a = get_match_stats(match_data["id"])
        corners_actuales = c_h + c_a
        st.info(f"🏟️ **Datos API:** {match_data['home']} ({c_h}) - ({c_a}) {match_data['away']}")
        corners_1t_input = st.number_input("Corners actuales detectados", value=int(corners_actuales))
        minuto_actual = match_data["elapsed"] or 45
    else:
        col_manual1, col_manual2 = st.columns(2)
        with col_manual1:
            corners_1t_input = st.number_input("Corners acumulados hasta el momento", min_value=0, value=4)
        with col_manual2:
            minuto_actual = st.number_input("Minuto actual del encuentro", min_value=1, max_value=90, value=45)

    if st.button("Ejecutar Simulador En Vivo"):
        with st.spinner("Proyectando tramo final del partido..."):
            minutos_restantes = max(90 - minuto_actual, 0)
            
            # Montecarlo en vivo: iniciamos con los corners reales y simulamos los minutos faltantes
            resultados_vivo = simular_montecarlo(corners_1t_input, minutos_restantes, lambda_total_pre, n_simulaciones)
            promedio_proyectado = np.mean(resultados_vivo)
            
            st.subheader("🎯 Resultados de la Proyección en Vivo")
            c1, c2, c3 = st.columns(3)
            c1.metric("Corners Reales anotados", f"{corners_1t_input}")
            c2.metric("Promedio Esperado Restante", f"{(promedio_proyectado - corners_1t_input):.2f}")
            c3.metric("Total Final Proyectado", f"{promedio_proyectado:.2f}")
            
            mostrar_tabla_probabilidades(resultados_vivo)
