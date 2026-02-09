# Projet Big Data

Projet Big Data — projet de master (M2) centré sur l'analyse de données et la mise en place de modèles (recommandation, factorisation, etc.). 

## Contenu principal
- `scripts/` : scripts utilitaires (ex. `train.py`, `evaluate.py`).
- `front/` : tableau de recommandation, appel le back pour les recommandations
- `back/` : utilise le modèle pour les recos

## Prérequis
- Python 3.8+ (conda recommandé)
- Installer les dépendances:

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Ou avec conda :

```bash
conda create -n projet_big_data python=3.10 -y
conda activate projet_big_data
pip install -r requirements_scripts.txt
```

## Exécution rapide
- Lancer l'entraînement (exemple) :

```bash
python scripts/train.py
```

- Lancer l'évaluation (si présent) :

```bash
python scripts/evaluate.py
```
- Lancer l'api dans le dossier ProjetDB_Back:
  ```bash
   python3 -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
  ```
- Lancer l'application :
  ```bash
   streamlit run ProjetDB_Front/app.py
  ```
