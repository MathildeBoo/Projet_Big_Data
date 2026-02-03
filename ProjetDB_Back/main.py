from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import pandas as pd
import requests
from surprise import dump
from pymongo import MongoClient
from contextlib import asynccontextmanager
import traceback
import math

# --- CONFIGURATION ---
MODEL_PATH = "github_nmf_model.pkl"
MONGO_URI = os.getenv("MONGO_URI")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")

# Variables globales
loaded_algo = None
df_reference = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Charge le modèle ML et la connexion Mongo au démarrage"""
    global loaded_algo, df_reference
    print(" Démarrage de l'API...")
    
    # 1. Chargement ML
    try:
        import os
        if os.path.exists(MODEL_PATH):
            _, loaded_algo = dump.load(MODEL_PATH)
            print(" Modèle NMF chargé.")
        else:
            print(" Modèle introuvable. Mode 'Content-Based' uniquement.")
    except Exception as e:
        print(f" Erreur chargement ML : {e}")

    # 2. Chargement Données de Référence (Pour Jaccard)
    try:
        client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
        db = client["githubAPI"]
        cursor = db["stars"].find({}, {'user_login': 1, 'repo_full_name': 1, '_id': 0}).limit(50000)
        df_reference = pd.DataFrame(list(cursor))
        if not df_reference.empty:
            df_reference.columns = ['user', 'item']
            print(f" Données de référence chargées ({len(df_reference)} lignes).")
        client.close()
    except Exception as e:
        print(f" Erreur Mongo Init : {e}")
    
    yield

app = FastAPI(title="GitHub RecSys API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- MODÈLES ---
class Recommendation(BaseModel):
    repo_name: str
    score: float       # Sur 100
    url: str = ""
    description: str = ""
    language: str = ""

class UserPreferences(BaseModel):
    languages: List[str]
    topics: List[str]

# --- FONCTIONS ---

def get_analytics_data():
    """Récupère les Tops Kafka"""
    try:
        client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=3000)
        data = client["githubAPI"]["analytics_results"].find_one({"type": "cold_start_recommendations"})
        client.close()
        return data
    except: return None

def enrich_repo_if_missing(repo_full_name: str):
    """Ajoute un repo inconnu dans la BDD"""
    try:
        client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=3000)
        db = client["githubAPI"]
        
        if db["repos"].find_one({"full_name": repo_full_name}):
            client.close()
            return

        headers = {"Accept": "application/vnd.github.v3+json"}
        if GITHUB_TOKEN: headers["Authorization"] = f"token {GITHUB_TOKEN}"
        
        resp = requests.get(f"https://api.github.com/repos/{repo_full_name}", headers=headers, timeout=5)
        if resp.status_code == 200:
            d = resp.json()
            new_repo = {
                "github_id": d.get("id"),
                "full_name": d.get("full_name"),
                "url": d.get("html_url"),
                "stars": d.get("stargazers_count", 0),
                "language": d.get("language"),
                "topics": d.get("topics", []),
                "description": d.get("description")
            }
            db["repos"].update_one({"full_name": repo_full_name}, {"$set": new_repo}, upsert=True)
            print(f"📥 Enrichi: {repo_full_name}")
        client.close()
    except Exception as e:
        print(f" Erreur enrichissement {repo_full_name}: {e}")

# --- ENDPOINTS ---

@app.get("/trends")
def get_global_trends():
    """Pour les dropdowns du frontend"""
    data = get_analytics_data()
    if not data:
        return {"languages": ["Python", "JavaScript", "Java"], "topics": ["web", "data", "ai"]}
    return {
        "languages": sorted(list(data.get("by_language", {}).keys())),
        "topics": sorted(list(data.get("by_topic", {}).keys()))
    }

@app.post("/recommend/manual", response_model=List[Recommendation])
def recommend_manual(prefs: UserPreferences):
    """Recommandation 'Mainstream' basée sur Kafka"""
    data = get_analytics_data()
    if not data: raise HTTPException(status_code=503, detail="Données non prêtes")

    results = {}
    
    # Fusion des résultats Langages + Topics
    for lang in prefs.languages:
        for r in data.get("by_language", {}).get(lang, []):
            results[r.get('repo_name')] = r
    
    for topic in prefs.topics:
        for r in data.get("by_topic", {}).get(topic, []):
            results[r.get('repo_name')] = r

    final_list = []
    for r in results.values():
        # Score de popularité normalisé (Log scale)
        # On considère 50k stars comme le "Max" (100%)
        stars = float(r.get('stars', 0))
        score_pop = min(100, (math.log(stars + 1) / math.log(50000 + 1)) * 100) if stars > 0 else 0
        
        final_list.append(Recommendation(
            repo_name=r.get('repo_name', 'Unknown'),
            score=round(score_pop, 1),
            url=r.get('url') or '',
            description=r.get('description') or 'Pas de description',
            language=r.get('language') or 'Inconnu'
        ))
    
    final_list.sort(key=lambda x: x.score, reverse=True)
    return final_list[:10]

@app.get("/recommend/{github_user}", response_model=List[Recommendation])
async def recommend_user(github_user: str, token: str = None):
    """Recommandation IA (NMF) pour un utilisateur"""
    try:
        # 1. Récupération Stars GitHub
        headers = {"Accept": "application/vnd.github.v3+json"}
        if token: headers["Authorization"] = f"token {token}"
        
        url = f"https://api.github.com/users/{github_user}/starred?per_page=50"
        try:
            resp = requests.get(url, headers=headers, timeout=10)
        except: return [] # Timeout ou erreur réseau
            
        if resp.status_code != 200 or not resp.json():
            return [] # User inconnu ou pas de stars

        user_stars_data = resp.json()
        if not isinstance(user_stars_data, list): return []
        
        user_stars_names = {r['full_name'] for r in user_stars_data if 'full_name' in r}

        # 2. Enrichissement (3 premiers)
        for r in user_stars_data[:3]:
            if 'full_name' in r: enrich_repo_if_missing(r['full_name'])

        recommendations = []

        # 3. Machine Learning (Jaccard + NMF)
        if loaded_algo and df_reference is not None and not df_reference.empty:
            try:
                db_users_data = df_reference.groupby('user')['item'].apply(set)
                best_match, max_sim = None, -1
                
                # Jaccard
                for db_user, items in db_users_data.items():
                    common = user_stars_names.intersection(items)
                    if common:
                        sim = len(common) / len(user_stars_names.union(items))
                        if sim > max_sim:
                            max_sim, best_match = sim, db_user
                
                # Prédiction
                if best_match:
                    print(f"👯 Jumeau: {best_match} ({max_sim:.2f})")
                    known_items = set(loaded_algo.trainset._raw2inner_id_items.keys())
                    to_predict = list(known_items - user_stars_names)
                    
                    for repo in to_predict[:30]:
                        try:
                            pred = loaded_algo.predict(uid=best_match, iid=repo)
                            # Conversion Score NMF -> % Match
                            # Suppose que le modèle sort ~0 à 1 (ou 5). Ajuster le facteur si besoin.
                            raw = pred.est
                            score_pct = min(99, raw * 100) if raw <= 1 else min(99, raw * 20)
                            
                            recommendations.append(Recommendation(
                                repo_name=repo,
                                score=round(score_pct, 1),
                                description=f"Similaire à vos goûts (via {best_match})",
                                language="IA Suggestion"
                            ))
                        except: pass
            except Exception as e:
                print(f" Erreur ML: {e}")

        # 4. Fallback Content-Based (Si ML échoue)
        if not recommendations:
            user_topics = set()
            user_langs = set()
            for r in user_stars_data:
                if r.get("language"): user_langs.add(r["language"])
                for t in r.get("topics", []): user_topics.add(t)
            
            if user_topics or user_langs:
                return recommend_manual(UserPreferences(
                    languages=list(user_langs)[:3],
                    topics=list(user_topics)[:5]
                ))

        recommendations.sort(key=lambda x: x.score, reverse=True)
        return recommendations[:10]

    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)