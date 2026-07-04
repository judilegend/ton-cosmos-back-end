# Guide de Déploiement Docker — Ton Cosmos (Backend)

Ce document décrit comment builder, configurer et lancer l'application en production avec Docker, suite aux mises à jour des modules Abonnement (Cercle Cosmos) et Upsell (Sprint 3).

## 1. Variables d'Environnement Requises (`.env`)

Assurez-vous que votre fichier `.env` de production contient bien les éléments suivants pour les nouvelles fonctionnalités (en plus de vos clés Stripe, Claude, etc.) :

```env
# URL de l'API
API_URL=https://api.ton-cosmos.com

# URL du Frontend (CORS) - TRÈS IMPORTANT EN PROD
# Pas d'astérisque '*' autorisé en prod. Uniquement les domaines exacts séparés par des virgules.
CORS_ORIGINS=["https://ton-cosmos.com","https://admin.ton-cosmos.com"]

# Base de données PostgreSQL (gérée dans le docker-compose ou AWS RDS)
DATABASE_URL=postgresql+asyncpg://user:password@db:5432/toncosmos_db
```

## 2. Construire l'Image Docker

L'image est désormais optimisée via le nouveau `Dockerfile` (multi-layers, pas d'utilisateur root, security check, suppression de `--reload`).
Placez-vous dans le dossier `ton-cosmos-back-end` et exécutez :

```bash
docker build -t ton-cosmos-backend:latest .
```

## 3. Lancer les Migrations (Alembic)

**Règle d'or :** L'application ne modifie plus son propre schéma de base de données au démarrage (`ALTER TABLE` supprimés). 
Il est **obligatoire** de jouer les migrations Alembic avant (ou pendant) le démarrage du conteneur.

### Option A : Via la commande de démarrage (CMD dans Dockerfile/docker-compose)
Le Dockerfile est déjà configuré pour lancer `alembic upgrade head` juste avant de démarrer Uvicorn.
Le `CMD` s'en occupe automatiquement à chaque lancement :
```dockerfile
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
```
Si vous utilisez `docker-compose`, démarrez simplement le conteneur :
```bash
docker-compose up -d backend
```

### Option B : Migration manuelle dans le conteneur
Si vous devez appliquer la migration manuellement sur une base de données existante sans relancer le conteneur complet :
```bash
docker exec -it <nom_du_conteneur_backend> alembic upgrade head
```

## 4. Ce qui tourne en arrière-plan (Background Tasks)

Une fois le serveur `uvicorn` lancé, le backend fait tourner automatiquement :
- **FastAPI / Uvicorn** : Traitement des requêtes HTTP sur le port 8000.
- **Le Scheduler Mensuel (`SubscriptionScheduler`)** : Attaché au cycle de vie de FastAPI (lifespan), ce script ne consomme rien mais se réveille automatiquement le 1er de chaque mois pour générer les rapports des abonnés actifs du "Cercle Cosmos".

## 5. Vérifier la santé du conteneur (Healthcheck)

Le backend dispose maintenant d'un endpoint healthcheck natif utilisé par Docker pour vérifier qu'il n'est pas planté.
```bash
docker ps
# La colonne STATUS devrait afficher "Up X minutes (healthy)"
```

Si le conteneur est marqué `unhealthy`, consultez les logs :
```bash
docker logs <nom_du_conteneur_backend> --tail 100
```
