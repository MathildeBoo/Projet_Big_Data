import json
import datetime
import pandas as pd
from kafka import KafkaConsumer
from pymongo import MongoClient

# --- CONFIGURATION ---
MONGO_URI = os.getenv("MONGO_URI")
DB_NAME = "githubAPI"
COLLECTION_ANALYTICS = "analytics_results"
KAFKA_TOPIC = 'github_repos_stream'
KAFKA_BOOTSTRAP_SERVER = ['localhost:9092']

# 🚫 LISTE DES TOPICS À BANNIR
BLACKLIST_TOPICS = [
    "awesome", "awesome-list", "list", "resources", "free", 
    "learning", "tutorial", "collection", "books", "cheat-sheet", 
    "interview", "roadmap", "curated", "documentation", "guide",
    "course", "materials", "programming"
]

def process_and_save():
    print("🔌 Connexion à MongoDB...")
    try:
        client = MongoClient(MONGO_URI)
        db = client[DB_NAME]
        analytics_col = db[COLLECTION_ANALYTICS]
        print("✅ Connexion MongoDB réussie.")
    except Exception as e:
        print(f"❌ Erreur de connexion MongoDB: {e}")
        return

    # Configuration du Consumer
    print("⏳ Connexion à Kafka (cela peut prendre quelques secondes)...")
    consumer = KafkaConsumer(
        KAFKA_TOPIC,
        bootstrap_servers=KAFKA_BOOTSTRAP_SERVER,
        auto_offset_reset='earliest',
        enable_auto_commit=True,
        # IMPORTANT : Je change le group_id pour forcer Kafka à tout renvoyer depuis le début
        group_id='analytics_group_debug_v5', 
        value_deserializer=lambda x: json.loads(x.decode('utf-8')),
        # IMPORTANT : Timeout augmenté à 20 secondes pour éviter les coupures si ton PC ralentit
        consumer_timeout_ms=20000 
    )

    data_list = []
    print("📥 En attente de messages Kafka (Timeout: 20s)...")

    count = 0
    for message in consumer:
        repo = message.value
        
        repo_url = repo.get('url') if repo.get('url') else repo.get('html_url')

        simplified_data = {
            'repo_name': repo.get('full_name'),
            'url': repo_url,
            'description': repo.get('description'),
            'language': repo.get('language'), # GitHub renvoie souvent "TypeScript" (CamelCase)
            'topics': repo.get('topics') if repo.get('topics') else [],
            'stars': repo.get('stars', 0)
        }
        data_list.append(simplified_data)
        
        count += 1
        if count % 10000 == 0:
            print(f"   -> {count} repos traités...")

    if not data_list:
        print("❌ Aucune donnée reçue. Kafka est vide ou le Producer n'a pas tourné.")
        return

    # --- ANALYSE ET FILTRAGE ---
    df = pd.DataFrame(data_list)
    print(f"📊 Analyse de {len(df)} repos au total.")
    
    # --- DEBUG : VÉRIFICATION SPÉCIFIQUE TYPESCRIPT ---
    # Cela va t'afficher dans le terminal combien de TS il a trouvé VRAIMENT
    ts_count = df[df['language'] == 'TypeScript'].shape[0]
    print(f"🔎 DEBUG: J'ai trouvé {ts_count} repositories identifiés comme 'TypeScript' dans les données brutes.")
    # --------------------------------------------------

    def get_top_10_by_group(dataframe, group_col):
        sorted_df = dataframe.sort_values('stars', ascending=False)
        # MODIFICATION : On garde le Top 10
        top_10 = sorted_df.groupby(group_col).head(10)
        
        lookup_dict = {}
        for name, group in top_10.groupby(group_col):
            if name and str(name).lower() != 'nan':
                records = group[['repo_name', 'url', 'description', 'stars', 'language']].to_dict('records')
                lookup_dict[str(name)] = records
        return lookup_dict

    # 1. Traitement des LANGAGES (Top 50)
    top_langs_list = df.groupby('language')['stars'].sum().sort_values(ascending=False).head(50).index.tolist()
    df_langs_filtered = df[df['language'].isin(top_langs_list)]
    
    lookup_languages = get_top_10_by_group(df_langs_filtered, 'language')
    print(f"   -> {len(lookup_languages)} langages traités.")

    # 2. Traitement des TOPICS (Top 500 + Blacklist)
    df_topics = df.explode('topics')
    df_topics = df_topics[~df_topics['topics'].isin(BLACKLIST_TOPICS)]
    
    print("   -> Calcul des Top Topics (filtrage 'awesome' & co)...")
    top_topics_list = df_topics.groupby('topics')['stars'].sum().sort_values(ascending=False).head(500).index.tolist()
    
    df_topics_filtered = df_topics[df_topics['topics'].isin(top_topics_list)]
    lookup_topics = get_top_10_by_group(df_topics_filtered, 'topics')
    print(f"   -> {len(lookup_topics)} topics pertinents conservés.")

    # --- SAUVEGARDE MONGODB ---
    stats_document = {
        "type": "cold_start_recommendations",
        "updated_at": datetime.datetime.now(),
        "total_analyzed": len(df),
        "by_language": lookup_languages,
        "by_topic": lookup_topics
    }

    try:
        analytics_col.update_one(
            {"type": "cold_start_recommendations"},
            {"$set": stats_document},
            upsert=True
        )
        print("✅ Données mises à jour et sauvegardées avec succès !")
    except Exception as e:
        print(f"❌ Erreur lors de la sauvegarde : {e}")

if __name__ == "__main__":
    process_and_save()