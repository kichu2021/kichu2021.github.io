import streamlit as st
import numpy as np
import requests
import plotly.express as px
import plotly.graph_objects as go

# CONFIGURACIÓN SEGURA DE LA API
try:
    API_KEY = st.secrets["API_FOOTBALL_KEY"]
except KeyError:
    st.error("⚠️ Falta configurar la API Key en los Secrets de Streamlit.")
    st.stop()

API_KEY = str(API_KEY).strip()

st.set_page_config(page_title="Predictor Avanzado de Corners", layout="wide")
st.title("⚽ Predictor de Corners Pro (Poisson + Montecarlo)")
st.write("Análisis estadístico predictivo mediante simulaciones masivas y ajuste por marcador dinámico.")

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
        c_h, c_a, g_h, g_a = 0, 0, 0, 0
        if "response" in response and len(response["response"]) >= 2:
            g_h = response["response"]["goals"]["home"] or 0
            g_a = response["response"]["goals"]["away"] or 0
            for item in response["response"]:
                team = item["team"]["name"]
                corners = next((s["value"] for s in item["statistics"] if s["type"] == "Corner Kicks"), 0) or 0
                if live_matches and selected_match_label:
                    if team == live_matches[selected_match_label]["home"]: c_h = corners
                    else: c_a = corners
        return c_h, c_a, g_h, g_a
    except:
        return 0, 0, 0, 0

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

# Cálculo matemático Lambda Base CORREGIDO (Escala Real de Partido)
lambda_local_base = (cf_local * cc_visita) / prom_liga
lambda_visita_base = (cf_visita * cc_local) / prom_liga

# --- PESTAÑAS DE ANÁLISIS ---
tab1, tab2 = st.tabs(["📊 Simulación Pre-Partido", "⏱️ Proyección En Vivo (Ajustada por Marcador)"])

# FUNCIÓN CENTRAL MONTECARLO
def simular_montecarlo(corners_base, minutos_restantes, lambda_total, n_sim):
    if minutos_restantes <= 0:
        return np.full(n_sim, corners_base)
    lambda_minuto = lambda_total / 90
    tiros_por_minuto = np.random.poisson(lambda_minuto, size=(n_sim, minutos_restantes))
    totales_simulados = corners_base + np.sum(tiros_por_minuto, axis=1)
    return totales_simulados

# NUEVA FUNCIÓN PARA RENDERIZAR GRÁFICOS INTERACTIVOS
def graficar_probabilidades(resultados_simulados):
    lineas = [7.5, 8.5, 9.5, 10.5, 11.5, 12.5, 13.5]
    valores_lineas = []
    porcentajes = []
    
    for linea in lineas:
        prob = np.mean(resultados_simulados > linea) * 100
        valores_lineas.append(f"Más de {linea}")
        porcentajes.append(round(prob, 1))
    
    # Gráfico 1: Barras de Probabilidad de Mercados
    fig_barras = px.bar(
        x=valores_lineas, 
        y=porcentajes, 
        text=[f"{p}%" for p in porcentajes],
        labels={'x': 'Mercado de Corners', 'y': 'Probabilidad (%)'},
        title="📈 Probabilidad de Superar Líneas de Corners",
        color=porcentajes,
        color_continuous_scale="Viridis"
    )
    fig_barras.update_traces(textposition='outside')
    fig_barras.update_layout(yaxis_range=[0, 110], coloraxis_showscale=False)
    
    # Gráfico 2: Histograma de Distribución Exacta
    valores_unicos, conteos = np.unique(resultados_simulados, return_counts=True)
    prob_exactas = (conteos / len(resultados_simulados)) * 100
    
    fig_hist = go.Figure(data=[go.Bar(
        x=valores_unicos,
        y=prob_exactas,
        text=[f"{p:.1f}%" for p in prob_exactas],
        textposition='outside',
        marker_color='#2ca02c'
    )])
    fig_hist.update_layout(
        title="🎯 Probabilidad del Número Exacto de Corners Finales",
        xaxis=dict(title="Cantidad de Corners Exactos", tickmode='linear'),
        yaxis=dict(title="Probabilidad (%)", range=[0, max(prob_exactas) * 1.2])
    )
    
    # Desplegar gráficos en columnas autónomas
    col_g1, col_g2 = st.columns(2)
    with col_g1:
        st.plotly_chart(fig_barras, use_container_width=True)
    with col_g2:
        st.plotly_chart(fig_hist, use_container_width=True)
# PESTAÑA 1: PRE-PARTIDO
with tab1:
    st.subheader("Análisis Probabilístico Pre-Partido")
    lambda_total_pre = lambda_local_base + lambda_visita_base
    st.metric("Expectativa Inicial del Partido (Lambda)", f"{lambda_total_pre:.2f}")
    
    if st.button("Ejecutar Simulador Pre-Partido"):
        with st.spinner("Corriendo algoritmos de Montecarlo..."):
            resultados_pre = simular_montecarlo(0, 90, lambda_total_pre, n_simulaciones)
            
            st.success(f"¡Simulación de {n_simulaciones} partidos completada!")
            
            c_p1, c_p2, c_p3 = st.columns(3)
            c_p1.metric("Promedio Simulado", f"{np.mean(resultados_pre):.2f}")
            c_p2.metric("Mínimo Esperado", f"{np.min(resultados_pre)}")
            c_p3.metric("Máximo Detectado", f"{np.max(resultados_pre)}")
            
            graficar_probabilidades(resultados_pre)

# PESTAÑA 2: EN VIVO CON LÓGICA DE GOLES
with tab2:
    st.subheader("Módulo de Proyección en Tiempo Real (Efecto Marcador)")
    
    if selected_match_label and live_matches:
        match_data = live_matches[selected_match_label]
        c_h, c_a, g_h, g_a = get_match_stats(match_data["id"])
        corners_actuales = c_h + c_a
        st.info(f"🏟️ **Datos API:** {match_data['home']} [{g_h}] vs [{g_a}] {match_data['away']} | Corners Actuales: {corners_actuales}")
        
        col_m1, col_m2 = st.columns(2)
        with col_m1:
            goles_local = st.number_input("Goles Local", value=int(g_h), min_value=0)
            corners_1t_input = st.number_input("Corners acumulados totales", value=int(corners_actuales), min_value=0)
        with col_m2:
            goles_visita = st.number_input("Goles Visita", value=int(g_a), min_value=0)
            minuto_actual = st.number_input("Minuto actual", value=int(match_data["elapsed"] or 45), min_value=1, max_value=90)
    else:
        col_manual1, col_manual2 = st.columns(2)
        with col_manual1:
            goles_local = st.number_input("Goles Local (1T / Actual)", min_value=0, value=0)
            corners_1t_input = st.number_input("Corners acumulados hasta el momento", min_value=0, value=4)
        with col_manual2:
            goles_visita = st.number_input("Goles Visita (1T / Actual)", min_value=0, value=1)
            minuto_actual = st.number_input("Minuto actual del encuentro", min_value=1, max_value=90, value=45)

    if st.button("Ejecutar Simulador En Vivo"):
        with st.spinner("Calculando impacto del marcador y proyectando tramo final..."):
            minutos_restantes = max(90 - minuto_actual, 0)
            
            # --- LÓGICA MATEMÁTICA: INFLUENCIA DE GOLES EN CORNERS ---
            factor_local = 1.0
            factor_visita = 1.0
            diff_goles = goles_local - goles_visita
            
            if diff_goles < 0: # Local va perdiendo
                factor_local += abs(diff_goles) * 0.18 
                factor_visita -= abs(diff_goles) * 0.08 
            elif diff_goles > 0: # Visita va perdiendo
                factor_visita += diff_goles * 0.15
                factor_local -= diff_goles * 0.05
                
            factor_local = max(factor_local, 0.6)
            factor_visita = max(factor_visita, 0.6)
            
            # Re-cálculo de Lambdas Ajustados por Escenario de Partido
            lambda_local_ajustado = lambda_local_base * factor_local
            lambda_visita_ajustado = lambda_visita_base * factor_visita
            lambda_total_vivo = lambda_local_ajustado + lambda_visita_ajustado
            
            # Simulación con la nueva tasa de corners modificada por los goles
            resultados_vivo = simular_montecarlo(corners_1t_input, minutos_restantes, lambda_total_vivo, n_simulaciones)
            promedio_proyectado = np.mean(resultados_vivo)
            
            # Cartas de Métricas Principales
            st.subheader("🎯 Resultados de la Proyección en Vivo")
            st.caption(f"💡 **Ajuste de flujo táctico aplicado:** Multiplicador Local: **{factor_local:.2f}x** | Multiplicador Visita: **{factor_visita:.2f}x**")
            
            c1, c2, c3 = st.columns(3)
            c1.metric("Corners Reales Registrados", f"{corners_1t_input}")
            c2.metric("Promedio Esperado (2T / Restante)", f"{(promedio_proyectado - corners_1t_input):.2f}")
            c3.metric("Total Final Proyectado", f"{promedio_proyectado:.2f}")
            
            graficar_probabilidades(resultados_vivo)
