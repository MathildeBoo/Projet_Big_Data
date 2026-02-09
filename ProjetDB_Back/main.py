from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import pandas as pd
import requests
from surprise import dump
from pymongo import MongoClient
from contextlib import asynccontextmanager
import math
import os
import random
from dotenv import load_dotenv

# 1. Configuration
load_dotenv(override=True)
# --- CONFIGURATION ---
MODEL_PATH = "github_nmf_model.pkl"
MONGO_URI = os.getenv("MONGO_URI")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")

# Variables globales
loaded_algo = None
df_reference = None
cache_metadata = {"languages": [], "topics": []}

@asynccontextmanager
async def lifespan(app: FastAPI):
    global loaded_algo, df_reference, cache_metadata
    print(" Démarrage de l'API...")
    
    # 1. Chargement ML
    try:
        if os.path.exists(MODEL_PATH):
            _, loaded_algo = dump.load(MODEL_PATH)
            print(" Modèle NMF chargé.")
        else:
            print(" Modèle .pkl introuvable !")
    except Exception as e:
        print(f" Erreur ML : {e}")

    # 2. Chargement Données
    try:
        client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
        db = client["githubAPI"]
        
        # Référence pour Jaccard
        cursor = db["stars"].find({}, {'user_login': 1, 'repo_full_name': 1, '_id': 0}).limit(50000)
        df_reference = pd.DataFrame(list(cursor))
        if not df_reference.empty:
            df_reference.columns = ['user', 'item']
            print(f" Référence chargée ({len(df_reference)} lignes).")
        
        # Tags pour Streamlit
        langs = db["repos"].distinct("language")
        tops = db["repos"].distinct("topics")
        cache_metadata["languages"] = sorted([l for l in langs if l])
        cache_metadata["topics"] = sorted([t for t in tops if t])
        
        client.close()
    except Exception as e:
        print(f" Erreur Mongo : {e}")
    
    yield

app = FastAPI(title="GitHub RecSys API", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

class Recommendation(BaseModel):
    repo_name: str
    score: float
    url: str = ""
    description: str = ""
    language: str = ""

class UserPreferences(BaseModel):
    languages: List[str]
    topics: List[str]

@app.get("/trends")
def get_trends():
    return cache_metadata

@app.post("/recommend/manual", response_model=List[Recommendation])
def recommend_manual(prefs: UserPreferences):
    try:
        client = MongoClient(MONGO_URI)
        db = client["githubAPI"]
        query = {"$or": [{"language": {"$in": prefs.languages}}, {"topics": {"$in": prefs.topics}}]}
        repos = list(db["repos"].find(query).sort("stars", -1).limit(10))
        client.close()
        return [Recommendation(
            repo_name=r.get('full_name'),
            score=round(min(99, math.log(r.get('stars', 1)+1)*10), 1),
            url=f"https://github.com/{r.get('full_name')}",
            description=r.get('description', 'Basé sur vos filtres'),
            language=r.get('language', 'N/A')
        ) for r in repos]
    except: return []

@app.get("/recommend/{github_user}", response_model=List[Recommendation])
async def recommend_user(github_user: str, token: str = None):
    """RECO IA PURE : Garantit au moins 5 à 10 résultats ML"""
    try:
        headers = {"Accept": "application/vnd.github.v3+json"}
        if GITHUB_TOKEN: headers["Authorization"] = f"token {GITHUB_TOKEN}"
        url = f"https://api.github.com/users/{github_user}/starred?per_page=50"
        resp = requests.get(url, headers=headers, timeout=5)
        
        user_stars = set()
        if resp.status_code == 200:
            user_stars = {r['full_name'] for r in resp.json() if 'full_name' in r}

        recommendations = []

        if loaded_algo and df_reference is not None:
            db_users = df_reference.groupby('user')['item'].apply(set)
            best_match, max_sim = None, -1
            
            # Recherche de similarité
            for db_user, items in db_users.items():
                inter = user_stars.intersection(items)
                sim = len(inter) / len(user_stars.union(items)) if user_stars else 0
                if sim > max_sim:
                    max_sim, best_match = sim, db_user
            
            # Si pas de match, on prend un échantillon d'utilisateurs pour générer du contenu
            targets = []
            if not best_match or max_sim == 0:
                targets = random.sample(list(db_users.keys()), 3) # On prend 3 users au hasard
                reason = "Exploration ML"
            else:
                targets = [best_match]
                reason = f"Similarité IA ({int(max_sim*100)}%)"

            known_items = list(loaded_algo.trainset._raw2inner_id_items.keys())
            
            # Générer des prédictions pour les targets
            for target_user in targets:
                # On teste 50 items pour être sûr d'en trouver 10 bons
                random_items = random.sample(known_items, min(len(known_items), 50))
                for repo in random_items:
                    if repo not in user_stars and repo not in [r.repo_name for r in recommendations]:
                        pred = loaded_algo.predict(uid=target_user, iid=repo)
                        recommendations.append(Recommendation(
                            repo_name=repo,
                            score=round(min(99, pred.est * 20), 1),
                            description=reason,
                            url=f"https://github.com/{repo}",
                            language="IA Suggestion"
                        ))

        recommendations.sort(key=lambda x: x.score, reverse=True)
        return recommendations[:10]

    except Exception:
        return []

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)