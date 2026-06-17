import asyncio
import secrets
import hashlib
from datetime import datetime, timezone
from sqlalchemy import select

from app.models.admin import Admin
from app.core.config import settings
from app.database.session import SessionLocal, engine
from app.services.utility_service import PasswordService

async def seed_db():
    async with SessionLocal() as db:
        password_service = PasswordService()
        
        try:
            print("Lancement de la procédure d'initialisation...")

            admin_email = settings.ADMIN_EMAIL
            
            # Vérification
            query = select(Admin).filter(Admin.email == admin_email)
            result = await db.execute(query)
            admin = result.scalars().first()
            
            if not admin:
                # Préparation du mot de passe
                hashed_password = password_service.hash_password(settings.ADMIN_PASSWORD)
                
                # Génération du client_secret
                raw_secret = f"{datetime.now(timezone.utc).timestamp()}-{secrets.token_hex(16)}"
                client_secret = hashlib.sha256(raw_secret.encode()).hexdigest()
            
                # Création de l'objet Admin
                new_admin = Admin(
                    email=admin_email,
                    hashed_password=hashed_password,
                    client_secret=client_secret,
                    failed_login_attempts=0,
                )
                
                db.add(new_admin)
                
                # Commit asynchrone
                await db.commit()
                print(f"Succès : Le compte administrateur '{admin_email}' a été créé.")
                
            else:
                print(f"Info : L'administrateur '{admin_email}' existe déjà.")

        except Exception as e:
            print(f"Erreur pendant le seeding : {e}")
            await db.rollback()
            
        finally:
            # Fermeture de la session
            await db.close()
            # Fermeture du moteur pour libérer les pools de connexion
            await engine.dispose()


if __name__ == "__main__":
    asyncio.run(seed_db())