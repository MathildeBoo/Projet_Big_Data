import pandas as pd
import random
import numpy as np
from pymongo import MongoClient
from surprise import Dataset, Reader, NMF, dump
import os

# --- CONFIGURATION ---
MONGO_URI = os.getenv("MONGO_URI")
MODEL_FILENAME = "github_nmf_model.pkl"

# Paramètres optimisés (issus de votre notebook)
BEST_PARAMS = {
    'n_factors': 132,
    'n_epochs': 76,
    'reg_pu': 0.03034349689970731,
    'reg_qi': 0.12323194796302143,
    'biased': False,
    'random_state': 42
}

def train_and_save_model():
    print(" Démarrage de l'entraînement hebdomadaire...")
    
    # 1. Chargement des données
    client = MongoClient(MONGO_URI)
    db = client["githubAPI"]
    # On limite pour l'exemple, mais en prod, on peut augmenter ou enlever la limite
    cursor = db["stars"].find({}, {'user_login': 1, 'repo_full_name': 1, '_id': 0}).limit(600000)
    
    data = []
    for doc in cursor:
        if doc.get('user_login') and doc.get('repo_full_name'):
            data.append({
                "user": doc.get('user_login'),
                "item": doc.get('repo_full_name'),
                "rating": 1.0
            })
    client.close()
    
    if not data:
        print(" Aucune donnée trouvée pour l'entraînement.")
        return

    print(f" {len(data)} interactions chargées.")

    # 2. Préparation (Exemples négatifs simplifiés pour le script)
    df_pos = pd.DataFrame(data)
    all_items = list(df_pos['item'].unique())
    users = df_pos['user'].unique()
    
    train_negatives = []
    # Optimisation : On génère moins de négatifs pour que le script tourne vite en cron
    for u in users:
        # On prend juste 2 items négatifs au hasard par user pour aller vite
        # (Dans la vraie vie, gardez votre logique du notebook)
        negs = random.sample(all_items, 2) 
        for item in negs:
            train_negatives.append({"user": u, "item": item, "rating": 0.0})
            
    df_train = pd.concat([df_pos, pd.DataFrame(train_negatives)])
    
    # 3. Entraînement Surprise
    reader = Reader(rating_scale=(0, 1))
    dataset = Dataset.load_from_df(df_train[['user', 'item', 'rating']], reader)
    trainset = dataset.build_full_trainset()
    
    algo = NMF(**BEST_PARAMS)
    algo.fit(trainset)
    
    # 4. Sauvegarde
    dump.dump(MODEL_FILENAME, algo=algo)
    print(f" Modèle sauvegardé sous : {MODEL_FILENAME}")

if __name__ == "__main__":
    train_and_save_model()