import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from scipy.stats import norm

# Configuração da Página otimizada para mobile
st.set_page_config(
    page_title="GEX Mobile - EWZ & WIN",
    page_icon="📱",
    layout="centered"
)

# Estilização CSS personalizada para telas menores (Mobile First)
st.markdown("""
<style>
    .main .block-container {
        padding-top: 1rem;
        padding-bottom: 2rem;
        padding-left: 0.8rem;
        padding-right: 0.8rem;
    }
    h1 { font-size: 1.3rem !important; }
    h2 { font-size: 1.1rem !important; }
    h3 { font-size: 0.95rem !important; }
    .stDataFrame {
        border: 1px solid #e6e6e6;
        border-radius: 5px;
    }
</style>
""", unsafe_allow_html=True)

st.title("📱 GEX Mobile: EWZ ➔ WIN")
st.markdown("Painel institucional avançado com Black-Scholes GEX otimizado para mobile.")

# --- BARRA LATERAL / EXPANDER: UPLOAD E FILTROS ---
with st.expander("📂 1. Carregar Dados & Parâmetros", expanded=True):
    uploaded_file = st.file_uploader("Enviar CSV da CBOE (ex: ewz.csv)", type=["csv"])
    
    col_in1, col_in2 = st.columns(2)
    with col_in1:
        fechamento_ewz_input = st.number_input("Fech EWZ (D-1):", value=35.00, format="%.2f")
    with col_in2:
        fechamento_mini_input = st.number_input("Fech WIN (D-1):", value=125000.0, format="%.2f")
        
    iv_input = st.number_input("Volatilidade Implícita (IV %):", value=25.0, format="%.1f") / 100.0

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
            st.error(f"Erro ao ler o arquivo: {e}")
            return None, ""

    raw_df, file_content = load_data(uploaded_file)
    
    if raw_df is not None:
        df = raw_df.copy()
        df.columns = [str(c).strip().lower() for c in df.columns]
        
        # --- DETECÇÃO AUTOMÁTICA DO PREÇO SPOT ---
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

        st.info(f"📍 **Spot Detectado / Estimado:** {spot_price:.2f}")

        # Tratamento de colunas numéricas
        df['strike'] = pd.to_numeric(df['strike'], errors='coerce')
        df['open interest'] = pd.to_numeric(df['open interest'].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
        df['open interest.1'] = pd.to_numeric(df['open interest.1'].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
        df['volume'] = pd.to_numeric(df['volume'].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
        df['volume.1'] = pd.to_numeric(df['volume.1'].astype(str).str.replace(',', ''), errors='coerce').fillna(0)

        # Filtro de Vencimentos
        all_exp_dates = sorted(df['expiration date'].dropna().unique())
        selected_exp_dates = st.multiselect(
            "Selecione os Vencimentos:",
            options=all_exp_dates,
            default=all_exp_dates[0:1]
        )

        if selected_exp_dates:
            df = df[df['expiration date'].isin(selected_exp_dates)]

        if not df.empty:
            # Agrupar por strike
            grouped_df = df.groupby('strike').agg({
                'open interest': 'sum',
                'open interest.1': 'sum',
                'volume': 'sum',
                'volume.1': 'sum'
            }).reset_index()

            grouped_df['total_volume'] = grouped_df['volume'] + grouped_df['volume.1']

            # --- CÁLCULO DE BLACK-SCHOLES GAMMA (GEX) ---
            T = 30 / 365.0  
            r = 0.05
            sigma = iv_input if iv_input > 0 else 0.25

            def calculate_gamma(S, K, T, r, sigma):
                if T <= 0 or sigma <= 0 or S <= 0 or K <= 0:
                    return 0.0
                d1 = (np.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * np.sqrt(T))
                return norm.pdf(d1) / (S * sigma * np.sqrt(T))

            gex_list = []
            for idx, row in grouped_df.iterrows():
                K = row['strike']
                gamma = calculate_gamma(spot_price, K, T, r, sigma)
                gex_call = gamma * (spot_price ** 2) * row['open interest'] * 100 / 1e6
                gex_put = -gamma * (spot_price ** 2) * row['open interest.1'] * 100 / 1e6
                gex_list.append(gex_call + gex_put)

            grouped_df['gex_net'] = gex_list

            # Identificação Institucional
            call_wall = float(grouped_df.loc[grouped_df['open interest'].idxmax()]['strike'])
            put_wall = float(grouped_df.loc[grouped_df['open interest.1'].idxmax()]['strike'])
            gamma_risk = float(grouped_df.loc[grouped_df['volume.1'].idxmax()]['strike'])
            hvl_strike = float(grouped_df.loc[grouped_df['total_volume'].idxmax()]['strike'])

            # Gamma Flip (Cruzamento do Zero no GEX)
            df_sorted = grouped_df.sort_values('strike').reset_index(drop=True)
            gamma_flip = spot_price
            for i in range(len(df_sorted) - 1):
                g1 = df_sorted.loc[i, 'gex_net']
                g2 = df_sorted.loc[i + 1, 'gex_net']
                if g1 * g2 <= 0:
                    s1 = df_sorted.loc[i, 'strike']
                    s2 = df_sorted.loc[i + 1, 'strike']
                    gamma_flip = s1 if abs(g1) < abs(g2) else s2
                    break

            # --- PROJEÇÕES PARA O MINI ÍNDICE ---
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

            def fmt_win(val):
                return f"{val:,.0f}".replace(",", ".")

            # --- PAINEL DE MÉTRICAS (EM PILHAS VERTICAIS PARA MOBILE) ---
            st.markdown("---")
            st.subheader("🎯 Metas para o Mini Índice")
            
            st.metric("🏢 Put Wall (Suporte)", fmt_win(put_wall_mini), delta=f"{dist_put_pct:+.2f}% EWZ")
            st.metric("📊 HVL (Nó de Volume)", fmt_win(hvl_mini), delta=f"{dist_hvl_pct:+.2f}% EWZ")
            st.metric("⚡ Gamma Flip (Inflexão)", fmt_win(gamma_flip_mini), delta=f"{dist_flip_pct:+.2f}% EWZ")
            st.metric("🚨 Gamma Risk (Risco)", fmt_win(gamma_risk_mini), delta=f"{dist_risk_pct:+.2f}% EWZ")
            st.metric("🏢 Call Wall (Resistência)", fmt_win(call_wall_mini), delta=f"{dist_call_pct:+.2f}% EWZ")

            # --- GRÁFICOS EMPILHADOS (MELHOR PARA TELA VERTICAL) ---
            st.markdown("---")
            st.subheader("📈 Gráficos de Exposição")

            # Gráfico 1: GEX Líquido
            st.markdown("**Gamma Exposure (GEX) Líquido ($M)**")
            fig_gex = go.Figure()
            colors = ['#3b82f6' if val >= 0 else '#ef4444' for val in grouped_df['gex_net']]
            fig_gex.add_trace(go.Bar(
                x=grouped_df['strike'], y=grouped_df['gex_net'],
                name='GEX Líquido', marker_color=colors
            ))
            fig_gex.add_hline(y=0, line_width=1, line_color="black")
            fig_gex.add_vline(x=spot_price, line_width=2, line_color="green", annotation_text="Spot")
            fig_gex.add_vline(x=call_wall, line_width=1.5, line_dash="dash", line_color="red", annotation_text="Call Wall")
            fig_gex.add_vline(x=put_wall, line_width=1.5, line_dash="dash", line_color="blue", annotation_text="Put Wall")
            fig_gex.add_vline(x=gamma_flip, line_width=1.5, line_dash="dot", line_color="orange", annotation_text="Flip")
            fig_gex.update_layout(
                barmode='relative', height=280, margin=dict(l=5, r=5, t=10, b=10), template='plotly_white'
            )
            st.plotly_chart(fig_gex, use_container_width=True)

            # Gráfico 2: Open Interest
            st.markdown("**Open Interest (OI) por Strike**")
            fig_oi = go.Figure()
            fig_oi.add_trace(go.Bar(x=grouped_df['strike'], y=grouped_df['open interest'], name='Calls OI', marker_color='#60a5fa'))
            fig_oi.add_trace(go.Bar(x=grouped_df['strike'], y=-grouped_df['open interest.1'], name='Puts OI', marker_color='#f87171'))
            fig_oi.add_hline(y=0, line_width=1, line_color="black")
            fig_oi.add_vline(x=spot_price, line_width=2, line_color="green", annotation_text="Spot")
            fig_oi.add_vline(x=hvl_strike, line_width=1.5, line_dash="dashdot", line_color="brown", annotation_text="HVL")
            fig_oi.update_layout(
                barmode='relative', height=250, margin=dict(l=5, r=5, t=10, b=10), template='plotly_white'
            )
            st.plotly_chart(fig_oi, use_container_width=True)

            # --- PLANO OPERACIONAL E RESUMO ---
            st.markdown("---")
            st.subheader("🧠 Plano Operacional Rápido")
            st.markdown(f"""
            * **Call Wall ({fmt_win(call_wall_mini)}):** Venda de topo / exaustão.
            * **Put Wall ({fmt_win(put_wall_mini)}):** Compra de suporte / repique.
            * **Gamma Flip ({fmt_win(gamma_flip_mini)}):** Ponto de virada (Amortecedor vs Acelerador).
            * **HVL ({fmt_win(hvl_mini)}):** Ímã de liquidez e transição.
            """)

            # --- TABELA TÉCNICA ---
            st.markdown("---")
            st.subheader("🏛️ Resumo Técnico")
            niveis_data = {
                "Nível": ["Call Wall", "Put Wall", "HVL", "Gamma Flip", "Gamma Risk"],
                "Strike EWZ": [call_wall, put_wall, hvl_strike, gamma_flip, gamma_risk],
                "Dist. %": [f"{dist_call_pct:+.2f}%", f"{dist_put_pct:+.2f}%", f"{dist_hvl_pct:+.2f}%", f"{dist_flip_pct:+.2f}%", f"{dist_risk_pct:+.2f}%"],
                "Mini WIN": [fmt_win(call_wall_mini), fmt_win(put_wall_mini), fmt_win(hvl_mini), fmt_win(gamma_flip_mini), fmt_win(gamma_risk_mini)]
            }
            st.dataframe(pd.DataFrame(niveis_data), use_container_width=True)

        else:
            st.warning("Selecione um vencimento válido.")
else:
    st.info("👆 Carregue o arquivo CSV da CBOE acima para iniciar.")
