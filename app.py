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

# Estilização CSS para melhor visualização no telemóvel
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

# --- SEÇÃO 1: INPUTS E DADOS ---
with st.expander("📂 1. Carregar Dados & Fechamentos", expanded=True):
    uploaded_file = st.file_uploader("Enviar CSV da CBOE (ex: ewz.csv)", type=["csv"])
    
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

            # Função para formatar os pontos do Mini Índice (ex: 204.100)
            def fmt_win(val):
                return f"{val:,.0f}".replace(",", ".")

            # --- PAINEL DE MÉTRICAS ---
            st.markdown("---")
            st.subheader("🎯 Metas Projetadas para o Mini Índice")
            
            st.metric("🏢 Put Wall (Suporte)", fmt_win(put_wall_mini), delta=f"{dist_put_pct:+.2f}% EWZ")
            st.metric("📊 HVL (Nó de Volume)", fmt_win(hvl_mini), delta=f"{dist_hvl_pct:+.2f}% EWZ")
            st.metric("⚡ Gamma Flip (Inflexão)", fmt_win(gamma_flip_mini), delta=f"{dist_flip_pct:+.2f}% EWZ")
            st.metric("🚨 Gamma Risk (Risco)", fmt_win(gamma_risk_mini), delta=f"{dist_risk_pct:+.2f}% EWZ")
            st.metric("🏢 Call Wall (Resistência)", fmt_win(call_wall_mini), delta=f"{dist_call_pct:+.2f}% EWZ")

            # --- GRÁFICOS ---
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

            # --- LEITURA DE MERCADO E PLANO DE AÇÃO DETALHADO ---
            st.markdown("---")
            st.subheader("🧠 Leitura de Mercado e Plano Operacional")
            
            st.markdown(f"""
            ### 🏢 1. Barreiras de Contenção (Walls & HVL)
            * **Call Wall (EWZ: {call_wall} | Mini: {fmt_win(call_wall_mini)}):** 
                * *Leitura:* Zona de forte resistência devido ao hedge massivo dos dealers em calls.
                * *O que fazer:* Procure **vendas de topo / exaustão** ou realização de lucros nas proximidades.
            * **Put Wall (EWZ: {put_wall} | Mini: {fmt_win(put_wall_mini)}):** 
                * *Leitura:* Zona de suporte primário com alta concentração de puts vendidas.
                * *O que fazer:* Excelente região para procurar **compras de repique / suporte**.
            * **HVL - High Volume Level (EWZ: {hvl_strike} | Mini: {fmt_win(hvl_mini)}):** 
                * *Leitura:* Ponto de maior concentração total de contratos negociados.
                * *O que fazer:* Funciona como um **ímã de liquidez**. Fique atento ao comportamento do preço.
            """)

            st.markdown(f"""
            ### ⚡ 2. Pontos de Virada e Risco (Flip & Risk)
            * **Gamma Flip (EWZ: {gamma_flip} | Mini: {fmt_win(gamma_flip_mini)}):** 
                * *Leitura:* Ponto crítico de mudança de regime de volatilidade.
                * *O que fazer:* Acima deste nível, o mercado é amortecido. Abaixo dele, entra em *short gamma* (aceleração de quedas). **Monitore como gatilho.**
            * **Gamma Risk (EWZ: {gamma_risk} | Mini: {fmt_win(gamma_risk_mini)}):** 
                * *Leitura:* Zona de maior fluxo de volatilidade e risco direcional extremo.
                * *O que fazer:* Evite operações contra a tendência caso o preço rompa esta região.
            """)

            # --- TABELA DE NÍVEIS RESUMIDA ---
            st.markdown("---")
            st.subheader("🏛️ Resumo Técnico dos Níveis")
            niveis_data = {
                "Nível": ["Call Wall", "Put Wall", "HVL", "Gamma Flip", "Gamma Risk"],
                "Strike EWZ": [call_wall, put_wall, hvl_strike, gamma_flip, gamma_risk],
                "Distância %": [f"{dist_call_pct:+.2f}%", f"{dist_put_pct:+.2f}%", f"{dist_hvl_pct:+.2f}%", f"{dist_flip_pct:+.2f}%", f"{dist_risk_pct:+.2f}%"],
                "Projeção WIN": [fmt_win(call_wall_mini), fmt_win(put_wall_mini), fmt_win(hvl_mini), fmt_win(gamma_flip_mini), fmt_win(gamma_risk_mini)]
            }
            st.dataframe(pd.DataFrame(niveis_data), use_container_width=True)

        else:
            st.warning("Selecione um vencimento válido.")
else:
    st.info("👆 Envie o arquivo CSV da CBOE no topo para calcular as metas.")
