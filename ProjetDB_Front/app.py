import streamlit as st
import requests
import os
from dotenv import load_dotenv

#  Configuration
load_dotenv(override=True)
API_URL = st.secrets["API_URL"]

st.set_page_config(page_title="GitHub Matcher", page_icon="🚀", layout="wide")

# CSS personnalisé pour les cartes et le style global
st.markdown("""
<style>
    .repo-card { 
        background-color: #1E1E1E; 
        padding: 15px; 
        border-radius: 10px; 
        border: 1px solid #333; 
        margin-bottom: 10px; 
    }
    .repo-title a { 
        color: #FF4B4B !important; 
        font-weight: bold; 
        text-decoration: none; 
        font-size: 1.1em; 
    }
    .badge-ia { 
        background-color: #4CAF50; 
        color: white; 
        padding: 2px 6px; 
        border-radius: 4px; 
        font-size: 0.7em; 
        float: right; 
    }
    .badge-manual { 
        background-color: #2196F3; 
        color: white; 
        padding: 2px 6px; 
        border-radius: 4px; 
        font-size: 0.7em; 
        float: right; 
    }
    div.stButton > button { border-radius: 20px; }
</style>
""", unsafe_allow_html=True)

#  Gestion de l'état (Session State)
if "step" not in st.session_state: st.session_state.step = "login"
if "user_id" not in st.session_state: st.session_state.user_id = ""
if "selected_langs" not in st.session_state: st.session_state.selected_langs = set()
if "selected_topics" not in st.session_state: st.session_state.selected_topics = set()

#  Fonction API (avec cache)
@st.cache_data(ttl=600, show_spinner=False)
def fetch_tags():
    try:
        response = requests.get(f"{API_URL}/trends", timeout=5)
        if response.status_code == 200:
            return response.json()
    except:
        pass
    return {"languages": [], "topics": []}

# ==========================================
# ÉTAPE 1 : CONNEXION
# ==========================================
if st.session_state.step == "login":
    st.title(" GitHub Matcher")
    st.markdown("### Connectez-vous pour découvrir vos recommandations")
    
    user_id = st.text_input("Identifiant GitHub (ex: karpathy, octocat)")
    
    if st.button("Se connecter", type="primary", use_container_width=True):
        if user_id.strip():
            st.session_state.user_id = user_id.strip()
            st.session_state.step = "preferences"
            st.rerun()

# ==========================================
# ÉTAPE 2 : PRÉFÉRENCES
# ==========================================
elif st.session_state.step == "preferences":
    st.title(" Vos Intérêts")
    
    data = fetch_tags()
    
    if not data['languages'] and not data['topics']:
        st.warning(" Impossible de charger les données. Vérifiez que l'API tourne.")
    
    # --- LANGAGES ---
    st.subheader(" Langages")
    selected_l = st.multiselect(
        "Sélectionnez vos langages favoris",
        data['languages'], # On prend tous les langages disponibles
        default=list(st.session_state.selected_langs),
        placeholder="Tapez pour rechercher (ex: Python, Rust...)"
    )
    st.session_state.selected_langs = set(selected_l)

    # --- TOPICS ---
    st.subheader(" Thématiques")
    selected_t = st.multiselect(
        "Rechercher des sujets (ex: machine-learning, api...)", 
        data['topics'], 
        default=list(st.session_state.selected_topics),
        placeholder="Tapez pour rechercher un topic..."
    )
    st.session_state.selected_topics = set(selected_t)

    st.divider()
    
    col1, col2 = st.columns(2)
    with col1:
        st.metric("Langages choisis", len(st.session_state.selected_langs))
    with col2:
        st.metric("Topics choisis", len(st.session_state.selected_topics))

    if st.button("Voir mes recommandations ", type="primary", use_container_width=True):
        if st.session_state.selected_langs or st.session_state.selected_topics:
            st.session_state.step = "dashboard"
            st.rerun()
        else:
            st.warning("Sélectionnez au moins un langage ou un topic pour continuer.")

# ==========================================
# ÉTAPE 3 : DASHBOARD
# ==========================================
elif st.session_state.step == "dashboard":
    col_h1, col_h2 = st.columns([4,1])
    col_h1.title(f" Bonjour {st.session_state.user_id}")
    if col_h2.button("Déconnexion"):
        st.session_state.step = "login"
        st.rerun()

    tab1, tab2 = st.tabs([" Pour vous (IA)", " Selon vos choix"])

    
    with tab1:
        st.markdown("### Basé sur vos stars & similarité")
        try:
            with st.spinner("L'IA analyse votre profil..."):
                res = requests.get(f"{API_URL}/recommend/{st.session_state.user_id}", timeout=10)
                recos = res.json() if res.status_code == 200 else []
            
            if not recos:
                st.info(" **Aucune recommandation IA trouvée.**")
                st.caption("Notre modèle n'a pas trouvé d'utilisateur suffisamment similaire ('jumeau') dans la base de données pour générer des prédictions fiables.")
            else:
                for r in recos:
                    st.markdown(f"""
                    <div class="repo-card">
                        <span class="badge-ia">IA Pure</span>
                        <div class="repo-title"><a href="{r.get('url')}" target="_blank">{r.get('repo_name')}</a></div>
                        <div style="color: #bbb; font-size: 0.9em; margin: 5px 0;">{r.get('description')}</div>
                        <div style="margin-top: 10px;">
                            <b>Score:</b> {r.get('score')}% | <b>Langage:</b> {r.get('language')}
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
        except Exception as e:
            st.error("Erreur de connexion API.")

    # ONGLET 2 : MANUEL (Filtrage classique)
    with tab2:
        st.markdown("### Basé sur vos filtres")
        payload = {
            "languages": list(st.session_state.selected_langs), 
            "topics": list(st.session_state.selected_topics)
        }
        try:
            with st.spinner("Recherche des meilleurs projets..."):
                res = requests.post(f"{API_URL}/recommend/manual", json=payload, timeout=5)
                manual_recos = res.json() if res.status_code == 200 else []
            
            if manual_recos:
                for r in manual_recos:
                     st.markdown(f"""
                    <div class="repo-card">
                        <span class="badge-manual">Filtre</span>
                        <div class="repo-title"><a href="{r.get('url')}" target="_blank">{r.get('repo_name')}</a></div>
                        <div style="color: #bbb; font-size: 0.9em; margin: 5px 0;">{r.get('description')}</div>
                        <div style="margin-top: 10px;">
                            <b>Score:</b> {r.get('score')}% | <b>Langage:</b> {r.get('language')}
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
            else:
                st.info("Aucun résultat pour ces critères.")
        except:
            st.error("Erreur lors de la recherche.")

    st.divider()
    if st.button("Modifier mes préférences"):
        st.session_state.step = "preferences"
        st.rerun()
