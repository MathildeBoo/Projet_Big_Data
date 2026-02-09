import os
import shutil
import random
import numpy as np
import pandas as pd
import requests
import mlflow
import mlflow.sklearn
from collections import defaultdict
from pymongo import MongoClient
from sklearn.metrics import mean_squared_error
from surprise import Dataset, Reader, NMF, dump

# ==========================================
# CONFIGURATION & HYPERPARAMÈTRES
# ==========================================
SEED = 42
random.seed(SEED)
np.random.seed(SEED)

MONGO_URI = "mongodb+srv://toto_db_user:Peche4412@bigdata.0wqiq5r.mongodb.net/?retryWrites=true&w=majority"
DATA_LIMIT = 300000

# Paramètres optimisés via Optuna
BEST_PARAMS = {
    'n_factors': 132,
    'n_epochs': 76,
    'reg_pu': 0.03034349689970731,
    'reg_qi': 0.12323194796302143,
    'biased': False,
    'random_state': SEED
}

# Configuration MLflow (Chemins absolus pour éviter les erreurs de base de données)
BASE_DIR = os.path.abspath(os.getcwd())
MLFLOW_DB_PATH = os.path.join(BASE_DIR, "mlflow_recsys_final.db")
TRACKING_URI = f"sqlite:///{MLFLOW_DB_PATH}"

# ==========================================
# FONCTIONS UTILES
# ==========================================

def clean_mlflow_artifacts():
    """Nettoie les anciens dossiers MLflow pour repartir de zéro."""
    if os.path.exists("mlruns"):
        shutil.rmtree("mlruns")
    if os.path.exists(MLFLOW_DB_PATH):
        os.remove(MLFLOW_DB_PATH)
    print("🧹 Environnement MLflow nettoyé.")

def load_data_from_mongo(uri, limit):
    """Récupère les données d'interactions depuis MongoDB."""
    print(f"📡 Connexion à MongoDB pour récupérer {limit} records...")
    try:
        client = MongoClient(uri, serverSelectionTimeoutMS=5000)
        db = client["githubAPI"]
        collection = db["stars"]
        cursor = collection.find({}, {'user_login': 1, 'repo_full_name': 1, '_id': 0}).limit(limit)
        
        data = []
        for doc in cursor:
            if doc.get('user_login') and doc.get('repo_full_name'):
                data.append({
                    "user": doc.get('user_login'),
                    "item": doc.get('repo_full_name'),
                    "rating": 1.0
                })
        client.close()
        print(f"✅ {len(data)} enregistrements chargés.")
        return data
    except Exception as e:
        print(f"❌ Erreur MongoDB : {e}")
        return []

def precision_recall_at_k(predictions, k=10, threshold=0.16):
    """Calcule la précision et le rappel à K pour évaluer la pertinence réelle."""
    user_est_true = defaultdict(list)
    for uid, _, true_r, est, _ in predictions:
        user_est_true[uid].append((est, true_r))

    precisions, recalls = dict(), dict()
    for uid, user_ratings in user_est_true.items():
        user_ratings.sort(key=lambda x: x[0], reverse=True)
        n_rel = sum((true_r >= 1.0) for (_, true_r) in user_ratings)
        n_rec_k = sum((est >= threshold) for (est, _) in user_ratings[:k])
        n_rel_and_rec_k = sum(((true_r >= 1.0) and (est >= threshold))
                            for (est, true_r) in user_ratings[:k])

        precisions[uid] = n_rel_and_rec_k / n_rec_k if n_rec_k != 0 else 0
        recalls[uid] = n_rel_and_rec_k / n_rel if n_rel != 0 else 0

    return np.mean(list(precisions.values())), np.mean(list(recalls.values()))

# ==========================================
# ENTRAÎNEMENT
# ==========================================

def run_training_pipeline():
    # Nettoyage
    clean_mlflow_artifacts()
    
    # Chargement
    raw_data = load_data_from_mongo(MONGO_URI, DATA_LIMIT)
    if not raw_data: return
    
    # Split Train/Test
    random.shuffle(raw_data)
    split_idx = int(len(raw_data) * 0.8)
    train_pos = raw_data[:split_idx]
    test_pos = raw_data[split_idx:]
    
    df_train_pos = pd.DataFrame(train_pos)
    all_items = set(df_train_pos['item'].unique())
    
    # Échantillonnage négatif (Train)
    print("🎲 Génération des exemples négatifs pour l'entraînement...")
    train_negatives = []
    users_in_train = df_train_pos['user'].unique()
    for u in users_in_train:
        seen = set(df_train_pos[df_train_pos['user'] == u]['item'])
        candidates = list(all_items - seen)
        num_to_take = len(seen) * 5
        if candidates:
            negs = random.sample(candidates, min(len(candidates), num_to_take))
            for item in negs:
                train_negatives.append({"user": u, "item": item, "rating": 0.0})
    
    df_train_final = pd.concat([df_train_pos, pd.DataFrame(train_negatives)])
    
    # Préparation Surprise
    reader = Reader(rating_scale=(0, 1))
    train_data_surprise = Dataset.load_from_df(df_train_final[['user', 'item', 'rating']], reader)
    trainset = train_data_surprise.build_full_trainset()
    
    # Échantillonnage négatif (Test) pour l'évaluation MLflow
    print("🧪 Préparation du jeu de test...")
    all_data_df = pd.DataFrame(raw_data)
    test_users = set([x['user'] for x in test_pos])
    test_negatives = []
    for u in test_users:
        seen = set(all_data_df[all_data_df['user'] == u]['item'])
        candidates = list(all_items - seen)
        if candidates:
            negs = random.sample(candidates, min(len(candidates), 5)) #<- X
            for item in negs:
                test_negatives.append({'user': u, 'item': item, 'rating': 0.0})
    
    test_set_surprise = [(x['user'], x['item'], x['rating']) for x in test_pos] + \
                        [(x['user'], x['item'], x['rating']) for x in test_negatives]

    # MLflow Tracking & Training
    mlflow.set_tracking_uri(TRACKING_URI)
    mlflow.set_experiment("GitHub_Recommender_Final")
    
    with mlflow.start_run(run_name="NMF_Final_Optimized"):
        print("🚀 Entraînement du modèle NMF...")
        algo = NMF(**BEST_PARAMS)
        algo.fit(trainset)
        
        # Prédictions et métriques
        predictions = algo.test(test_set_surprise)
        rmse_val = np.sqrt(mean_squared_error([p.r_ui for p in predictions], [p.est for p in predictions]))
        prec, rec = precision_recall_at_k(predictions, k=10)
        
        # Logging
        mlflow.log_params(BEST_PARAMS)
        mlflow.log_metric("rmse", rmse_val)
        mlflow.log_metric("precision_at_10", prec)
        mlflow.log_metric("recall_at_10", rec)
        
        # Sauvegarde
        model_filename = "github_nmf_model.pkl"
        dump.dump(model_filename, algo=algo)
        mlflow.log_artifact(model_filename)
        
        print("-" * 30)
        print(f"✅ Succès !")
        print(f"📊 RMSE: {rmse_val:.4f}")
        print(f"🎯 Precision@10: {prec:.4f}")
        print("-" * 30)

    print(f"\n👉 Pour voir le dashboard MLflow, lancez :")
    print(f"mlflow ui --backend-store-uri {TRACKING_URI} --port 5001")

if __name__ == "__main__":
    run_training_pipeline()