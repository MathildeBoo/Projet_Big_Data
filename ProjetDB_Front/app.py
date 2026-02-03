import streamlit as st
import requests
import pandas as pd

# CONFIGURATION PAGE
st.set_page_config(page_title="GitHub Matcher", page_icon="🚀", layout="wide")

# CSS PERSONNALISÉ (Cartes, Couleurs)
st.markdown("""
<style>
    .repo-card {
        background-color: #262730;
        padding: 15px;
        border-radius: 10px;
        border: 1px solid #41424C;
        margin-bottom: 15px;
        transition: transform 0.2s;
    }
    .repo-card:hover {
        transform: scale(1.02);
        border-color: #FF4B4B;
        box-shadow: 0 4px 15px rgba(0,0,0,0.3);
    }
    .repo-title a {
        color: #FFFFFF !important;
        text-decoration: none;
        font-size: 1.1em;
        font-weight: bold;
    }
    .repo-desc {
        color: #BBBBBB;
        font-size: 0.9em;
        margin: 5px 0;
        white-space: nowrap; 
        overflow: hidden;
        text-overflow: ellipsis; 
    }
    .tag {
        background: #333;
        padding: 2px 8px;
        border-radius: 4px;
        font-size: 0.8em;
        color: #eee;
    }
    .score-high { color: #4CAF50; font-weight: bold; }
    .score-med { color: #FFC107; font-weight: bold; }
    .score-low { color: #FF5722; font-weight: bold; }
</style>
""", unsafe_allow_html=True)

# --- SIDEBAR ---
st.sidebar.title(" Réglages")
API_URL = st.sidebar.text_input("URL Backend", "http://localhost:8000")
github_token = st.sidebar.text_input("GitHub Token", type="password")

# --- ETAT (Session State) ---
if "recos_perso" not in st.session_state: st.session_state["recos_perso"] = []
if "recos_mainstream" not in st.session_state: st.session_state["recos_mainstream"] = []
if "has_searched" not in st.session_state: st.session_state["has_searched"] = False

# =========================================================
# HEADER & INPUT
# =========================================================
st.title(" GitHub Repository Matcher")
st.markdown("##### *Trouvez votre prochain projet Open Source.*")

col_input, col_btn = st.columns([3, 1])
with col_input:
    username = st.text_input("Pseudo GitHub (Optionnel)", placeholder="ex: MathildeBoo")
with col_btn:
    st.write("") # Spacer
    st.write("") 
    analyze_btn = st.button(" Analyser", type="primary", use_container_width=True)

# =========================================================
# SECTION FILTRES (Toujours visible)
# =========================================================
st.divider()
st.subheader(" Vos Intérêts")
st.caption("Cochez pour voir les tops du moment (Mainstream).")

# Récupération des options depuis l'API
try:
    trends = requests.get(f"{API_URL}/trends").json()
    langs_opt = trends.get("languages", [])
    topics_opt = trends.get("topics", [])
except:
    langs_opt, topics_opt = [], []

col_f1, col_f2 = st.columns(2)
with col_f1:
    sel_langs = st.multiselect("Langages", langs_opt)
with col_f2:
    sel_topics = st.multiselect("Thèmes / Topics", topics_opt)

# =========================================================
# LOGIQUE DE RECHERCHE
# =========================================================

# 1. Analyse Utilisateur (IA)
if analyze_btn and username:
    with st.spinner("Analyse du profil..."):
        try:
            params = {"token": github_token} if github_token else {}
            resp = requests.get(f"{API_URL}/recommend/{username}", params=params)
            if resp.status_code == 200:
                st.session_state["recos_perso"] = resp.json()
                st.session_state["has_searched"] = True
            else:
                st.error("Erreur API")
        except Exception as e:
            st.error(f"Erreur connexion: {e}")

# 2. Analyse Mainstream (Auto si filtres changent)
if sel_langs or sel_topics:
    try:
        payload = {"languages": sel_langs, "topics": sel_topics}
        resp = requests.post(f"{API_URL}/recommend/manual", json=payload)
        if resp.status_code == 200:
            st.session_state["recos_mainstream"] = resp.json()
    except: pass

# =========================================================
# AFFICHAGE DOUBLE COLONNE
# =========================================================

if st.session_state["has_searched"] or st.session_state["recos_mainstream"]:
    st.divider()
    col_left, col_right = st.columns(2)

    # --- GAUCHE : IA / PERSONNEL ---
    with col_left:
        st.header(" Pour Vous")
        if st.session_state["recos_perso"]:
            st.caption("Recommandations par Machine Learning")
            for repo in st.session_state["recos_perso"]:
                s = repo['score']
                s_class = "score-high" if s > 75 else "score-med" if s > 50 else "score-low"
                
                st.markdown(f"""
                <div class="repo-card">
                    <div class="repo-title"><a href="{repo.get('url', '#')}" target="_blank">{repo['repo_name']}</a></div>
                    <div class="repo-desc">{repo.get('description', '')[:90]}...</div>
                    <div style="display:flex; justify-content:space-between; align-items:center; margin-top:8px;">
                        <span class="tag">{repo.get('language', 'N/A')}</span>
                        <span class="{s_class}">{s}% Match</span>
                    </div>
                </div>
                """, unsafe_allow_html=True)
                st.progress(int(s))
        
        elif st.session_state["has_searched"]:
            st.info("Pas assez de données pour l'IA. Regardez les tops à droite 👉")
        else:
            st.info("Entrez un pseudo pour voir les recos IA.")

    # --- DROITE : MAINSTREAM ---
    with col_right:
        st.header(" Mainstream")
        if st.session_state["recos_mainstream"]:
            st.caption(f"Top Repos populaires")
            for repo in st.session_state["recos_mainstream"]:
                s = repo['score']
                
                st.markdown(f"""
                <div class="repo-card" style="border-left: 4px solid #3498db;">
                    <div class="repo-title"><a href="{repo.get('url', '#')}" target="_blank">{repo['repo_name']}</a></div>
                    <div class="repo-desc">{repo.get('description', '')[:90]}...</div>
                    <div style="display:flex; justify-content:space-between; align-items:center; margin-top:8px;">
                        <span style="font-size:0.8em;"> Popularité</span>
                        <span style="font-weight:bold;">{s}/100</span>
                    </div>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.info(" Sélectionnez des filtres pour voir les tendances.")