# DOCUMENTATION TECHNIQUE COMPLÈTE DU PROJET

---

## GUIDE D'INSTALLATION ET D'EXPLOITATION (README_INSTALL)

Ce document détaille les procédures nécessaires pour l'initialisation, le 
développement et le déploiement de l'application, que ce soit en environnement 
local ou via Docker.

### INSTALLATION ET ENVIRONNEMENT VIRTUEL
---

Pour une exécution locale sans Docker, il est vivement recommandé d'utiliser un 
environnement virtuel pour isoler les dépendances.

1. **Création de l'environnement virtuel** :
    Ouvrez votre terminal à la racine de votre projet et exécutez la commande 
    suivante
    
    ```bash
    python -m venv venv
    ```

    **Note** : Cette commande crée un dossier nommé **venv** qui contiendra une 
    copie isolée de Python pour votre projet.

2. **Activation du venv** :
    L'étape d'activation est cruciale car elle indique à votre terminal d'utiliser 
    le Python local au projet plutôt que celui du système.
    
    - Sur Windows (PowerShell) :

    ```bash
    venv\Scripts\activate
    ```

    - Sur Linux / macOS :

    ```bash
    source venv/bin/activate
    ```

3. **Installation des dépendances** :
    Une fois l'environnement activé (vous devriez voir (venv) s'afficher au début 
    de votre ligne de commande), installez les bibliothèques nécessaires

    ```bash
    pip install -r requirements.txt
    ```

    **Pourquoi est-ce important** ?

    - Isolation : Cela évite les conflits entre les différentes versions de bibliothèques de vos projets.
    - Stabilité : Vous garantissez que l'application utilise exactement les versions de FastAPI, SQLAlchemy ou Alembic pour lesquelles elle a été développée.
    - Propreté : Si vous décidez de supprimer le projet, il suffit de supprimer le dossier venv pour ne laisser aucune trace sur votre système.

### DÉVELOPPEMENT AVEC DOCKER
---

1. **Lancement de l'infrastructure** :

    Cette commande construit les images à partir des Dockerfiles et lance l'ensemble 
    des services définis (API, base de données, etc.). Elle assure que tous les 
    composants communiquent correctement entre eux dans un environnement isolé.

    ```bash
    docker compose up --build
    ```

2. **Exécution des commandes dans le conteneur (ex: fastapi_app)** :

    Lorsque l'application tourne sous Docker, les tâches de maintenance comme les 
    migrations ou le seeding doivent être lancées directement dans le conteneur actif. 
    On utilise docker compose exec suivi du nom du service pour agir à l'intérieur 
    de l'instance en cours d'exécution.

    ```bash
    docker compose exec fastapi_app alembic upgrade head
    docker compose exec fastapi_app python -m app.seed
    ```

### GESTION DE LA BASE DE DONNÉES (ALEMBIC)
---

L'application utilise Alembic pour la gestion des migrations de base de données. 
Suivez ces étapes pour synchroniser votre schéma de données

1. **Génération de la Migration Initiale** :
    Analyse les modèles SQLAlchemy et génère le script de migration correspondant.
    
    ```bash
    alembic revision --autogenerate -m "init"
    ```

2. **Application des Migrations** :
    Met à jour la structure de la base de données vers la version la plus récente.

    ```bash
    alembic upgrade head
    ```

3. **Initialisation des Données (Seeding)** :
    Alimente la base de données avec les données par défaut (compte administrateur, configurations initiales).

    ```bash
    python -m app.seed
    ```


### UTILISATION AU QUOTIDIEN
---

Le serveur utilise Uvicorn avec l'option de rechargement automatique pour faciliter le développement.

- Lancement local : 

    ```bash
    uvicorn app.main:app --reload
    ```
    
- Tests unitaires : 

    ```bash
    pytest
    ```


## GUIDE DES WEBHOOKS STRIPE (README_STRIPE)

Procédure pour tester la réception des paiements en local.

### INSTALLATION DE STRIPE CLI
---

- **macOS** : brew install stripe/stripe-cli/stripe
- **Windows** : Télécharger le binaire sur GitHub ([stripe.exe](https://github.com/stripe/stripe-cli/releases/tag/v1.40.9)) et l'ajouter au PATH.

### CONFIGURATION DU TUNNEL
---

Une fois l'outil installé, vous devez lier votre machine à votre compte Stripe 
pour générer une clé secrète de signature temporaire.

1. **Connexion à votre compte** : 

    ```bash
    stripe login
    ```

    Cette commande ouvrira une fenêtre dans votre navigateur pour confirmer l'accès.

2. **Lancement du tunnel (Forwarding)** :
    Lancez la redirection des événements vers votre point de terminaison local 
    (ex: /api/v1/stripe/stripe/webhook)

    ```bash
    stripe listen --forward-to localhost:8000/api/v1/stripe/stripe/webhook
    ```

3. **Secret de signature** :
   Récupérez la valeur 'whsec_...' affichée et placez-la dans .env :
   STRIPE_WEBHOOK_SECRET=whsec_xxx

### TESTS
---

Pendant que votre commande stripe listen tourne dans un terminal et que votre serveur 
FastAPI est actif dans un autre, vous pouvez simuler des événements réels.

- **Simuler un paiement** : Ouvrez un troisième terminal et déclenchez un événement test :

    ```bash
    stripe trigger checkout.session.completed --override checkout_session:metadata.order_id="1"
    ```

3. DOCUMENTATION TECHNIQUE : AUTH_MIDDLEWARE

## AUTH MIDDLEWARE

### INTRODUCTION

Ce module implémente un middleware de sécurité pour les applications basées 
sur le framework FastAPI. Son rôle est d'assurer l'interception, l'analyse 
et la validation des droits d'accès pour chaque requête HTTP entrante vers 
les ressources protégées de l'API.

### PRINCIPES DE FONCTIONNEMENT

Le middleware opère selon une logique de filtrage séquentielle :

1.  **Exemption des Requêtes de Pré-vérification** :
    Les requêtes avec la méthode `OPTIONS` (CORS) sont autorisées sans traitement supplémentaire.

2.  **Gestion des Chemins Publics** : 
    Les routes explicitement définies comme publiques ainsi que la documentation 
    technique (Swagger UI, ReDoc) sont ignorées par le processus d'authentification.

3.  **Analyse du Header d'Autorisation** : 
    Le middleware exige la présence d'un header `Authorization` utilisant le schéma `Bearer`.

4.  **Identification via Jeton de Rafraîchissement** : 
    L'identité de l'utilisateur est extraite d'un jeton de rafraîchissement présent 
    dans les cookies de la requête.

5.  **Validation Dynamique** : 
    Le middleware interroge la base de données pour confirmer l'existence de l'utilisateur 
    et récupère une clé secrète spécifique (`client_secret`) pour valider le jeton d'accès final.

### Architecture Technique

L'implémentation repose sur les composants suivants :

* **BaseHTTPMiddleware** : 
    Classe parente fournie par Starlette pour l'extension des fonctionnalités de traitement de requêtes.

* **JWT Service** : 
    Service responsable du décodage et de la validation cryptographique des jetons.

* **AdminRepository** : 
    Couche d'accès aux données pour la vérification de l'intégrité des comptes utilisateurs.

### Configuration

Lors de l'instanciation, le middleware requiert :

- `app` : L'instance de l'application FastAPI.
- `jwt_service` : Une instance valide du service de gestion des jetons.
- `public_paths` : Une liste optionnelle de chaînes de caractères définissant les points de terminaison accessibles sans authentification.

### Webographie

Pour approfondir les concepts de sécurité et les technologies utilisés dans ce fichier, veuillez consulter les ressources suivantes :

* [Documentation officielle de FastAPI - Middleware](https://fastapi.tiangolo.com/tutorial/middleware/)
* [Spécifications du standard JSON Web Token (RFC 7519)](https://datatracker.ietf.org/doc/html/rfc7519)
* [Guide Starlette sur les Middlewares](https://www.starlette.io/middleware/)
* [OWASP - Cheat Sheet sur l'Authentification](https://cheatsheetseries.owasp.org/cheatsheets/Authentication_Cheat_Sheet.html)


## RÉCAPITULATIF DES COMMANDES ESSENTIELLES

- Docker : docker compose up --build
- Serveur local : uvicorn app.main:app --reload
- Seeder : python -m app.seed
- Migrations : alembic upgrade head
- Tests : pytest

---

## Fin du document - Dernière mise à jour : 04 Mai 2026 19:50




…\ton-cosmos-back-end > .\venv\Scripts\pip.exe install pytest pytest-asyncio httpx
