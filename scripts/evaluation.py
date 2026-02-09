import os
import random
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from pymongo import MongoClient
from sklearn.metrics import (
    roc_curve, classification_report, confusion_matrix, 
    mean_squared_error, auc
)
from surprise import Reader, Dataset, dump
from collections import defaultdict

# ==========================================
# CONFIGURATION
# ==========================================
SEED = 42
random.seed(SEED)
np.random.seed(SEED)

MONGO_URI = "mongodb+srv://toto_db_user:Peche4412@bigdata.0wqiq5r.mongodb.net/?retryWrites=true&w=majority"
MODEL_PATH = "github_nmf_model.pkl"

# ==========================================
# CHARGEMENT ET PRÉPARATION
# ==========================================

def load_test_data(uri, limit=50000):
    """Récupère un échantillon de données pour l'évaluation."""
    print(f"📡 Récupération de {limit} records pour évaluation...")
    client = MongoClient(uri)
    db = client["githubAPI"]
    cursor = db["stars"].find({}, {'user_login': 1, 'repo_full_name': 1, '_id': 0}).limit(limit)
    
    data = [{"user": d['user_login'], "item": d['repo_full_name'], "rating": 1.0} for d in cursor]
    client.close()
    return data

def build_test_set(raw_data):
    """Crée le set de test avec X exemples négatifs par utilisateur."""
    df = pd.DataFrame(raw_data)
    all_items = set(df['item'].unique())
    test_users = df['user'].unique()
    
    test_set = []
    print("🎲 Génération des échantillons négatifs...")
    for u in test_users:
        # Positifs
        pos_items = df[df['user'] == u]['item'].tolist()
        for item in pos_items:
            test_set.append((u, item, 1.0))
        
        # Négatifs
        seen = set(pos_items)
        candidates = list(all_items - seen)
        if candidates:
            negs = random.sample(candidates, min(len(candidates), 5)) #<- X
            for item in negs:
                test_set.append((u, item, 0.0))
    return test_set

# ==========================================
# MÉTRIQUES ET VISUALISATION
# ==========================================

def plot_confusion_matrix(y_true, y_pred):
    """Génère et sauvegarde la matrice de confusion."""
    plt.figure(figsize=(6, 5))
    sns.heatmap(confusion_matrix(y_true, y_pred), annot=True, fmt='d', cmap='Blues')
    plt.title("Matrice de Confusion - NMF GitHub")
    plt.ylabel("Réalité (Star)")
    plt.xlabel("Prédiction")
    plt.savefig("confusion_matrix.png")
    print("📸 Matrice de confusion sauvegardée sous 'confusion_matrix.png'")

def run_evaluation():
    # Charger le modèle
    if not os.path.exists(MODEL_PATH):
        print(f"❌ Erreur : Modèle '{MODEL_PATH}' introuvable. Lancez d'abord train.py.")
        return

    print(f"📂 Chargement du modèle {MODEL_PATH}...")
    _, algo = dump.load(MODEL_PATH)

    # Préparer les données
    raw_data = load_test_data(MONGO_URI)
    test_set = build_test_set(raw_data)

    # Prédictions
    print("🔮 Calcul des prédictions...")
    predictions = algo.test(test_set)
    
    y_true = [int(p.r_ui) for p in predictions]
    y_scores = [p.est for p in predictions]

    # Calcul du seuil optimal (Indice de Youden)
    fpr, tpr, thresholds = roc_curve(y_true, y_scores)
    roc_auc = auc(fpr, tpr)
    best_thresh = thresholds[np.argmax(tpr - fpr)]
    
    # Calcul du RMSE
    # $$RMSE = \sqrt{\frac{1}{N} \sum_{i=1}^N (\hat{y}_i - y_i)^2}$$
    rmse = np.sqrt(mean_squared_error(y_true, y_scores))

    # Affichage des résultats
    print("\n" + "="*30)
    print("📊 RÉSULTATS DE L'ÉVALUATION")
    print("="*30)
    print(f"📈 AUC-ROC       : {roc_auc:.4f}")
    print(f"📉 RMSE          : {rmse:.4f}")
    print(f"🎯 Seuil Optimal : {best_thresh:.4f}")
    print("="*30)

    y_pred = [1 if s >= best_thresh else 0 for s in y_scores]
    print(classification_report(y_true, y_pred, target_names=['Non-Star', 'Star']))

    # Graphique
    plot_confusion_matrix(y_true, y_pred)

if __name__ == "__main__":
    # Correction pour l'erreur de bibliothèque C++ rencontrée précédemment
    # os.environ['LD_LIBRARY_PATH'] = f"{os.environ.get('CONDA_PREFIX')}/lib"
    run_evaluation()