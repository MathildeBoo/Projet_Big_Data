import streamlit as st
import pandas as pd
import os
import plotly.express as px
from pymongo import MongoClient

# --- CONFIGURATION ---
MONGO_URI = os.getenv("MONGO_URI")
DB_NAME = "githubAPI"
COLLECTION_ANALYTICS = "analytics_results"

st.set_page_config(page_title="GitHub Trends Dashboard", layout="wide")

# --- CHARGEMENT DES DONNÉES ---
@st.cache_data(ttl=3600)
def load_data():
    client = MongoClient(MONGO_URI)
    db = client[DB_NAME]
    
    # 1. Récupération des recommandations (Analytics)
    analytics_col = db[COLLECTION_ANALYTICS]
    data = analytics_col.find_one({"type": "cold_start_recommendations"})
    
    # 2. Récupération des KPIs (Raw Data)
    nb_users = db["users"].count_documents({})
    nb_repos = db["repos"].count_documents({})
    
    if not data:
        return None, None, 0, 0
        
    return data.get("by_language", {}), data.get("by_topic", {}), nb_users, nb_repos

dict_languages, dict_topics, total_users, total_repos = load_data()

# --- HEADER & KPI ---
st.title(" GitHub Repositories Analytics Board")

if not dict_languages:
    st.error(" Aucune donnée d'analyse trouvée. Lancez le consumer Kafka d'abord.")
    st.stop()

# KPIs
kpi1, kpi2, kpi3 = st.columns(3)
kpi1.metric("👥 Utilisateurs Analysés", f"{total_users:,}")
kpi2.metric("📦 Repositories Collectés", f"{total_repos:,}")
kpi3.metric("🧠 Sujets (Topics) Suivis", f"{len(dict_topics)}")

st.markdown("---")

# --- SECTION 1 : VUE D'ENSEMBLE ---
st.header("1. Tendances Globales")

def create_summary_df(data_dict, category_name):
    rows = []
    for cat, repos in data_dict.items():
        total_stars = sum(r['stars'] for r in repos)
        rows.append({category_name: cat, 'Popularité (Stars)': total_stars})
    return pd.DataFrame(rows).sort_values('Popularité (Stars)', ascending=False).head(10)

df_lang_summary = create_summary_df(dict_languages, "Langage")
df_topic_summary = create_summary_df(dict_topics, "Topic")

c1, c2 = st.columns(2)
with c1:
    fig_lang = px.bar(df_lang_summary, x='Langage', y='Popularité (Stars)', title="Top 10 Langages", color='Popularité (Stars)')
    st.plotly_chart(fig_lang, use_container_width=True)
with c2:
    fig_topic = px.bar(df_topic_summary, x='Popularité (Stars)', y='Topic', orientation='h', title="Top 10 Topics", color='Popularité (Stars)')
    st.plotly_chart(fig_topic, use_container_width=True)

# --- SECTION 2 : RECOMMANDATIONS (FILTRAGE STRICT) ---
st.markdown("---")
st.header("2. Explorateur & Recommandations")
st.write("Sélectionnez vos critères (Langage ET/OU Topic) pour filtrer les résultats.")

# Sélecteurs
all_langs = sorted(list(dict_languages.keys()))
all_topics = sorted(list(dict_topics.keys()))

col_sel1, col_sel2 = st.columns(2)
selected_lang = col_sel1.selectbox("Langage", ["Tout"] + all_langs)
selected_topic = col_sel2.selectbox("Topic", ["Tout"] + all_topics)

# --- LOGIQUE DE FILTRAGE STRICT ---
unique_repos = {}

# Cas 1 : Langage seul
if selected_lang != "Tout" and selected_topic == "Tout":
    for repo in dict_languages.get(selected_lang, []):
        unique_repos[repo['repo_name']] = repo

# Cas 2 : Topic seul
elif selected_lang == "Tout" and selected_topic != "Tout":
    for repo in dict_topics.get(selected_topic, []):
        unique_repos[repo['repo_name']] = repo

# Cas 3 : Langage ET Topic (Intersection)
elif selected_lang != "Tout" and selected_topic != "Tout":
    # On récupère les repos du Topic
    potential_repos = dict_topics.get(selected_topic, [])
    
    for repo in potential_repos:
        # On vérifie si le langage du repo correspond à la sélection
        repo_lang = repo.get('language')
        if repo_lang == selected_lang:
            unique_repos[repo['repo_name']] = repo

# Cas 4 : Rien
else:
    unique_repos = {}

# Conversion en liste et tri
results = list(unique_repos.values())
results = sorted(results, key=lambda x: x['stars'], reverse=True)

# --- AFFICHAGE ---
if results:
    st.success(f" {len(results)} repositories recommandés.")

    # Graphique dynamique de la sélection
    df_results = pd.DataFrame(results).head(10)
    if not df_results.empty:
        st.subheader(f" Top Résultats : {selected_lang} / {selected_topic}")
        fig_sel = px.bar(
            df_results, x='repo_name', y='stars', 
            color='stars', labels={'repo_name': 'Dépôt', 'stars': 'Étoiles'},
            hover_data=['language', 'description']
        )
        st.plotly_chart(fig_sel, use_container_width=True)

    # Liste détaillée
    st.subheader("Détails")
    for repo in results:
        with st.expander(f" {repo['stars']} - {repo['repo_name']} ({repo.get('language')})"):
            st.write(f"**Description:** {repo.get('description', 'Aucune description')}")
            st.markdown(f" [Voir sur GitHub]({repo['url']})")

elif selected_lang == "Tout" and selected_topic == "Tout":
    st.info(" Utilisez les filtres pour commencer.")
else:
    st.warning(f"Aucun repository trouvé pour le topic '{selected_topic}' écrit en '{selected_lang}'.")