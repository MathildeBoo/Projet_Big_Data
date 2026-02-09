import schedule
import time
import subprocess
import os

# --- CONFIGURATION DES CHEMINS ---
SCRIPT_COLLECTE = "scripts/test.py"
SCRIPT_PRODUCER = "scripts/producer.py"
SCRIPT_CONSUMER = "scripts/consumer_analyser.py"
SCRIPT_ML = "ml_training_task.py" 
def job_daily_update():
    """Tâche quotidienne : Collecte -> Kafka -> Stats"""
    print("\n [DAILY] Lancement de la mise à jour quotidienne...")
    try:
        # 1. Collecte de nouveaux Users/Repos
        print("   1. Collecte Data...")
        subprocess.run(["python", SCRIPT_COLLECTE], check=True)
        
        # 2. Envoi dans Kafka
        print("   2. Streaming Kafka...")
        subprocess.run(["python", SCRIPT_PRODUCER], check=True)
        
        # 3. Analyse Kafka -> MongoDB (Mise à jour Dashboard)
        print("   3. Analyse & Tendances...")
        subprocess.run(["python", SCRIPT_CONSUMER], check=True)
        
        print(" [DAILY] Mise à jour terminée !")
    except Exception as e:
        print(f" [DAILY] Erreur : {e}")

def job_weekly_training():
    """Tâche Hebdomadaire : Ré-entraînement du modèle IA"""
    print("\n[WEEKLY] Lancement de l'entraînement ML...")
    try:
        subprocess.run(["python", SCRIPT_ML], check=True)
        print(" [WEEKLY] Nouveau modèle 'github_nmf_model.pkl' généré.")
        
       
    except Exception as e:
        print(f" [WEEKLY] Erreur : {e}")

# --- PLANIFICATION ---

schedule.every().saturday.at("02:00").do(job_daily_update)

schedule.every(60).days.at("02:00").do(job_weekly_training)

print(" Scheduler démarré. En attente des tâches...")
# Lancement immédiat pour tester (à commenter en prod)
# job_daily_update()

while True:
    schedule.run_pending()
    time.sleep(60) 