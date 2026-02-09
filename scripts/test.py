import requests
import os
import re
import time
from pymongo import MongoClient
from datetime import datetime
from dotenv import load_dotenv
load_dotenv() 
# --- Configuration ---
MONGO_URI = os.getenv("MONGO_URI")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
# --- Connexion MongoDB ---
try:
    client = MongoClient(MONGO_URI)
    client.admin.command('ping')
    print(" Connexion MongoDB établie.")
except Exception as e:
    print(f" Erreur de connexion MongoDB : {e}")
    exit()

# --- Collections ---
db = client["githubAPI"]
users_collection = db["users"]
repos_collection = db["repos"]
stars_collection = db["stars"]

# --- Index ---
print(" Vérification des index...")
users_collection.create_index("github_id", unique=True)
repos_collection.create_index("github_id", unique=True)
stars_collection.create_index(
    [("user_github_id", 1), ("repo_github_id", 1)],
    unique=True
)
print(" Index actifs.")

# --- Headers GitHub API ---
headers = {
    "Accept": "application/vnd.github.v3.star+json",
    "Authorization": f"token {GITHUB_TOKEN}",
    "X-GitHub-Api-Version": "2022-11-28"
}

topic_headers = {
    "Accept": "application/vnd.github.mercy-preview+json",
    "Authorization": f"token {GITHUB_TOKEN}",
    "X-GitHub-Api-Version": "2022-11-28"
}


def wait_for_rate_limit(response):
    if response.status_code == 403:
        remaining = int(response.headers.get('X-RateLimit-Remaining', 0))
        if remaining == 0:
            reset_time = int(response.headers.get('X-RateLimit-Reset', time.time() + 60))
            wait_duration = max(reset_time - time.time() + 5, 0)
            print(f" Rate limit atteint. Pause de {wait_duration:.0f} sec.")
            time.sleep(wait_duration)
            return True
    return False


def get_all_starred_repos_with_dates(username):
    """
    Récupère TOUS les repos starred d’un utilisateur
    mais garde uniquement :
         ceux ajoutés après 2021
         et limite à 50 stars max
    """
    all_repos = []
    url = f"https://api.github.com/users/{username}/starred?per_page=100"

    while url and len(all_repos) < 50:
        response = requests.get(url, headers=headers)
        if wait_for_rate_limit(response):
            continue

        if response.status_code != 200:
            break

        data = response.json()

        for item in data:
            if len(all_repos) >= 50:
                break

            starred_at_str = item.get("starred_at")
            if not starred_at_str:
                continue

            starred_date = datetime.fromisoformat(starred_at_str.replace("Z", "+00:00"))

            #  Filtre : garder seulement les stars après 2021
            if starred_date.year <= 2021:
                continue

            repo = item["repo"]
            all_repos.append({
                "repo_id": repo["id"],
                "full_name": repo["full_name"],
                "html_url": repo["html_url"],
                "stars": repo["stargazers_count"],
                "language": repo.get("language"),
                "starred_at": starred_at_str
            })

        url = response.links.get("next", {}).get("url")

    return all_repos


def get_repo_topics(full_name):
    url = f"https://api.github.com/repos/{full_name}/topics"
    response = requests.get(url, headers=topic_headers)
    if response.status_code == 200:
        return response.json().get("names", [])
    return []


def get_users_with_starred_repos(min_starred=10, max_users=1000):

    users_url = "https://api.github.com/users?since=0&per_page=50"
    users_processed = 0

    print(" Démarrage du script...")

    while users_processed < max_users and users_url:

        response = requests.get(users_url, headers=headers)
        if wait_for_rate_limit(response):
            continue

        users = response.json()
        if not users:
            break

        for user in users:
            if users_processed >= max_users:
                break

            username = user["login"]
            user_github_id = user["id"]

            # Déjà traité ?
            if users_collection.find_one({"github_id": user_github_id}):
                continue

            # On récupère les stars filtrées (post-2021 + max 50)
            starred_repos = get_all_starred_repos_with_dates(username)

            if len(starred_repos) >= min_starred:
                print(f"\n👤 {username} ({len(starred_repos)} stars post-2021). Traitement...")

                # Sauvegarde user
                users_collection.update_one(
                    {"github_id": user_github_id},
                    {"$set": {"login": username, "github_id": user_github_id, "status": "full"}},
                    upsert=True
                )

                # Pour chaque star
                for repo in starred_repos:

                    repo_id = repo["repo_id"]
                    full_name = repo["full_name"]
                    starred_at = repo["starred_at"]

                    # Sauvegarde repo
                    if not repos_collection.find_one({"github_id": repo_id}):
                        topics = get_repo_topics(full_name)
                        repos_collection.update_one(
                            {"github_id": repo_id},
                            {"$set": {
                                "github_id": repo_id,
                                "full_name": full_name,
                                "url": repo["html_url"],
                                "stars": repo["stars"],
                                "language": repo["language"],
                                "topics": topics
                            }},
                            upsert=True
                        )

                    # Sauvegarde lien star AVEC DATE
                    stars_collection.update_one(
                        {"user_github_id": user_github_id, "repo_github_id": repo_id},
                        {"$set": {
                            "user_login": username,
                            "repo_full_name": full_name,
                            "starred_at": starred_at
                        }},
                        upsert=True
                    )

                users_processed += 1
                print(f" Terminé ({users_processed}/{max_users})")

            else:
                print(f" {username} ignoré ({len(starred_repos)} stars post-2021).")
                users_collection.update_one(
                    {"github_id": user_github_id},
                    {"$set": {"login": username, "github_id": user_github_id, "status": "skipped"}},
                    upsert=True
                )

        users_url = response.links.get('next', {}).get('url')

    print(f"\n🎉 Collecte terminée. {users_processed} nouveaux utilisateurs ajoutés.")


# --- Lancement ---
get_users_with_starred_repos(min_starred=10, max_users=1000)
