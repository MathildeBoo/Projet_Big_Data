import json
from kafka import KafkaProducer
from pymongo import MongoClient
from bson import json_util # Pour gérer les ObjectId de Mongo

# 1. Connexion à MongoDB (Modifie l'URI avec le tien)
client = MongoClient(os.getenv("MONGO_URI"))
db = client["githubAPI"] # Ton nom de BDD
collection_repos = db["repos"]

# 2. Configuration du Producer Kafka
producer = KafkaProducer(
    bootstrap_servers=['localhost:9092'], # Adresse de ton Kafka
    value_serializer=lambda x: json.dumps(x, default=json_util.default).encode('utf-8')
)

TOPIC_NAME = 'github_repos_stream'

def send_repos_to_kafka():
    print("Début de l'envoi des données vers Kafka...")
    # On récupère tous les repos
    cursor = collection_repos.find({})
    
    count = 0
    for repo in cursor:
        # On envoie le repo complet dans Kafka
        producer.send(TOPIC_NAME, value=repo)
        count += 1
        
    producer.flush()
    print(f"Terminé ! {count} repositories envoyés dans le topic '{TOPIC_NAME}'.")

if __name__ == "__main__":
    send_repos_to_kafka() 