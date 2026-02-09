# Projet Big Data

Projet Big Data — projet de master (M2) centré sur l'analyse de données et la mise en place de modèles (recommandation, factorisation, etc.). Ce dépôt contient des scripts d'entraînement, des notebooks d'exploration, et des composants pour tester et déployer des pipelines simples.

## Contenu principal
- `scripts/` : scripts utilitaires (ex. `train.py`, `evaluate.py`).
- `data/` : jeux de données (si présents).
- `models/` : modèles entraînés et artefacts.
- `notebooks/` / `.ipynb` : notebooks d'analyse et d'expérimentation.
- `src/` : code source réutilisable (préprocessing, métriques, etc.).

> Remarque : le nom exact des dossiers peut varier selon les branches. Cherchez `scripts/train.py` pour le script d'entraînement principal.

## Prérequis
- Python 3.8+ (conda recommandé)
- Installer les dépendances (si `requirements.txt` présent) :

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Ou avec conda :

```bash
conda create -n projet_big_data python=3.10 -y
conda activate projet_big_data
pip install -r requirements.txt
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

- Ouvrir les notebooks pour reproduire les analyses exploratoires :

```bash
jupyter lab
```

## Structure recommandée pour contribuer
- Créez une branche nommée `feature/xxx` ou `fix/xxx`.
- Faites des commits clairs et poussez la branche.
- Ouvrez une Pull Request vers `main`.

## Contact
Pour toute question ou pour obtenir de l'aide sur l'exécution, ouvrez une issue ou contactez l'auteur du dépôt.

---
Fichier généré automatiquement — modifiez ce README pour ajouter des instructions spécifiques au projet (ex. hyperparamètres, format de config, exemples d'usage détaillés).
# Projet_Big_Data
L’objectif du projet est de recommander des repositories Github à un utilisateur en se basant sur les repositories auxquels il a déjà mis une étoile.
