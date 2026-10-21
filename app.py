import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go

# Configuração da Página otimizada para dispositivos móveis
st.set_page_config(
    page_title="GEX Mobile - EWZ & WIN",
    page_icon="📱",
    layout="centered"
)

# Estilização CSS para melhor visualização no iPhone
st.markdown("""
<style>
    .main .block-container {
        padding-top: 1rem;
        padding-bottom: 2rem;
        padding-left: 1rem;
        padding-right: 1rem;
    }
    h1 {
        font-size: 1.5rem !important;
    }
    h2 {
        font-size: 1.2rem !important;
    }
    h3 {
        font-size: 1.0rem !important;
    }
</style>
""", unsafe_allow_html=True)

st.title("📱 GEX Mobile: EWZ ➔ WIN")
st.markdown("Leitura de Gamma Levels e projeção institucional na palma da mão.")

# --- SEÇÃO 1: INPUTS E DADOS (TELA PRINCIPAL PARA FACILITAR NO IPHONE) ---
with st.expander("📂 1. Carregar Dados & Fechamentos", expanded=True):
    uploaded_file = st.file_uploader("Enviar CSV da CBOE (ex: ewz.csv)", type=["csv"])
    
    # Inputs de Fechamento D-1
    col_in1, col_in2 = st.columns(2)
    with col_in1:
        fechamento_ewz_input = st.number_input("Fech EWZ (D-1):", value=35.00, format="%.2f")
    with col_in2:
        fechamento_mini_input = st.number_input("Fech WIN (D-1):", value=125000.0, format="%.2f")

if uploaded_file is not None:
    @st.cache_data
    def load_data(file):
        try:
            file.seek(0)
            content = file.read().decode('utf-8', errors='ignore')
            file.seek(0)
            df = pd.read_csv(file, skiprows=3)
            return df, content
        except Exception as e:
            st.error(f"Erro: {e}")
            return None, ""

    raw_df, file_content = load_data(uploaded_file)
    
    if raw_df is not None:
        df = raw_df.copy()
        df.columns = [str(c).strip().lower() for c in df.columns]
        
        # Detecção automática do Spot
        spot_price = None
        for line in file_content.split('\n')[:5]:
            line_lower = line.lower()
            if 'last' in line_lower or 'underlying' in line_lower or 'price' in line_lower:
                parts = line.split(',')
                for p in parts:
                    try:
                        val = float(p.strip().replace('$', ''))
                        if val > 1.0:
                            spot_price = val
                            break
                    except ValueError:
                        continue
        
        if spot_price is None or spot_price == 0:
            temp_strike = pd.to_numeric(df['strike'], errors='coerce')
            if not temp_strike.dropna().empty:
                spot_price = float(temp_strike.median())

        # Tratamento numérico
        df['strike'] = pd.to_numeric(df['strike'], errors='coerce')
        df['open interest'] = pd.to_numeric(df['open interest'].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
        df['open interest.1'] = pd.to_numeric(df['open interest.1'].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
        df['volume'] = pd.to_numeric(df['volume'].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
        df['volume.1'] = pd.to_numeric(df['volume.1'].astype(str).str.replace(',', ''), errors='coerce').fillna(0)

        # Filtro de Vencimento (Seleciona o primeiro por padrão para agilizar no mobile)
        all_exp_dates = sorted(df['expiration date'].dropna().unique())
        selected_exp_dates = st.multiselect("Vencimentos:", options=all_exp_dates, default=all_exp_dates[0:1])

        if selected_exp_dates:
            df = df[df['expiration date'].isin(selected_exp_dates)]

        if not df.empty:
            grouped_df = df.groupby('strike').agg({
                'open interest': 'sum',
                'open interest.1': 'sum',
                'volume': 'sum',
                'volume.1': 'sum'
            }).reset_index()

            grouped_df['total_volume'] = grouped_df['volume'] + grouped_df['volume.1']

            # Níveis Institucionais
            call_wall = float(grouped_df.loc[grouped_df['open interest'].idxmax()]['strike'])
            put_wall = float(grouped_df.loc[grouped_df['open interest.1'].idxmax()]['strike'])
            gamma_flip = float(grouped_df.loc[grouped_df['volume'].idxmax()]['strike'])
            gamma_risk = float(grouped_df.loc[grouped_df['volume.1'].idxmax()]['strike'])
            hvl_strike = float(grouped_df.loc[grouped_df['total_volume'].idxmax()]['strike'])

            # Distâncias e Projeções
            dist_put_pct = ((put_wall - fechamento_ewz_input) / fechamento_ewz_input) * 100
            dist_call_pct = ((call_wall - fechamento_ewz_input) / fechamento_ewz_input) * 100
            dist_flip_pct = ((gamma_flip - fechamento_ewz_input) / fechamento_ewz_input) * 100
            dist_risk_pct = ((gamma_risk - fechamento_ewz_input) / fechamento_ewz_input) * 100
            dist_hvl_pct = ((hvl_strike - fechamento_ewz_input) / fechamento_ewz_input) * 100

            put_wall_mini = fechamento_mini_input * (1 + (dist_put_pct / 100))
            call_wall_mini = fechamento_mini_input * (1 + (dist_call_pct / 100))
            gamma_flip_mini = fechamento_mini_input * (1 + (dist_flip_pct / 100))
            gamma_risk_mini = fechamento_mini_input * (1 + (dist_risk_pct / 100))
            hvl_mini = fechamento_mini_input * (1 + (dist_hvl_pct / 100))

            # --- PAINEL DE METRICAS (OTIMIZADO PARA VERTICAL) ---
            st.markdown("---")
            st.subheader("🎯 Metas Projetadas para o Mini Índice")
            
            st.metric("🏢 Put Wall (Suporte)", f"{put_wall_mini:,.0f}".replace(",", "."), delta=f"{dist_put_pct:+.2f}% EWZ")
            st.metric("📊 HVL (Nó de Volume)", f"{hvl_mini:,.0f}".replace(",", "."), delta=f"{dist_hvl_pct:+.2f}% EWZ")
            st.metric("⚡ Gamma Flip (Inflexão)", f"{gamma_flip_mini:,.0f}".replace(",", "."), delta=f"{dist_flip_pct:+.2f}% EWZ")
            st.metric("🚨 Gamma Risk (Risco)", f"{gamma_risk_mini:,.0f}".replace(",", "."), delta=f"{dist_risk_pct:+.2f}% EWZ")
            st.metric("🏢 Call Wall (Resistência)", f"{call_wall_mini:,.0f}".replace(",", "."), delta=f"{dist_call_pct:+.2f}% EWZ")

            # --- GRÁFICOS COMPactos PARA MOBILE ---
            st.markdown("---")
            st.subheader("📈 Exposição por Strike")
            
            fig_oi = go.Figure()
            fig_oi.add_trace(go.Bar(x=grouped_df['strike'], y=grouped_df['open interest'], name='Calls', marker_color='#3b82f6'))
            fig_oi.add_trace(go.Bar(x=grouped_df['strike'], y=-grouped_df['open interest.1'], name='Puts', marker_color='#ef4444'))
            fig_oi.add_hline(y=0, line_width=1, line_color="black")
            fig_oi.add_vline(x=call_wall, line_dash="dash", line_color="red", annotation_text="Call Wall")
            fig_oi.add_vline(x=put_wall, line_dash="dash", line_color="blue", annotation_text="Put Wall")
            fig_oi.update_layout(barmode='relative', height=300, margin=dict(l=10, r=10, t=10, b=10), template='plotly_white')
            st.plotly_chart(fig_oi, use_container_width=True)

            # --- PLANO DE AÇÃO OPERACIONAL ---
            st.markdown("---")
            st.subheader("🧠 Plano Operacional")
            st.markdown(f"""
            * **Call Wall ({call_wall_mini:,.0f}):** Venda de topo / exaustão de alta.
            * **Put Wall ({put_wall_mini:,.0f}):** Compra de suporte / repique.
            * **Gamma Flip ({gamma_flip_mini:,.0f}):** Gatilho de volatilidade (Positivo x Negativo).
            * **HVL ({hvl_mini:,.0f}):** Ponto magnético de maior liquidez.
            """)

        else:
            st.warning("Selecione um vencimento válido.")
else:
    st.info("👆 Envie o arquivo CSV da CBOE no topo para calcular as metas.")