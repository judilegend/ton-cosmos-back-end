import re
import json
import logging
import anthropic
from app.core.config import settings
from typing import Dict, Any

logger = logging.getLogger(__name__)
##jkfkbnkvnbk
class AIService:
    def __init__(self):
        self.client = anthropic.AsyncAnthropic(
            api_key=settings.ANTHROPIC_API_KEY
        )
        self.model_name = "claude-sonnet-4-6"   # ou claude-opus-4-6

        
    async def GenerateSVGMap(self, chart: dict): 
        prompt = f"""
        Génère le code source SVG d'une carte du ciel astrologique minimaliste mais optimisée pour une couverture de livre.

        DONNÉES ASTRALES À REPRÉSENTER : {chart}

        RÈGLES DE DESIGN (ZÉRO TEXTE) :
        1. SYMBOLES ET COORDONNÉES INCLUS : Intègre les symboles (glyphes) des planètes, les signes du zodiaque et les lignes des maisons/degrés.
        2. ZÉRO LÉGENDE : Aucun texte explicatif, aucun nom en toutes lettres, aucun tableau. Uniquement du graphisme.
        3. ESTHÉTIQUE : Épuré, lignes fines (stroke-width="1").

        RÈGLES D'OPTIMISATION STRICTES (POUR ÉCONOMISER LES TOKENS) :
        - CODE COMPACT : Factorise au maximum. Utilise une balise `<style>` globale au début au lieu de répéter `stroke="..."` et `fill="..."` sur chaque ligne.
        - GLYPHES RÉUTILISABLES : Déclare les symboles complexes une seule fois dans des balises `<defs>` et réutilise-les avec `<use href="#id" x="..." y="..." />`.
        - PAS DE COMMENTAIRES, pas d'indentation excessive, pas de sauts de ligne inutiles. Reste ultra-concis.

        RÈGLES TECHNIQUES CRITIQUES :
        - Réponds UNIQUEMENT avec le code source SVG brut, sans blabla ni explications avant/après.
        - INTERDICTION ABSOLUE d'utiliser les blocs Markdown (PAS de ```svg ou ```). Commence directement par <svg> et finis par </svg>.
        - Dimensions : viewBox="0 0 500 500" width="100%" height="100%".
        
        IMPORTANT : Ton quota est de 5000 tokens, mais tu dois rester concis et structuré pour ne jamais tronquer la fermeture du SVG. Finis impérativement par '</svg>'.
        """
        
        raw_content = ""
        
        try:
            response = await self.client.messages.create(
                model=self.model_name,
                max_tokens=8000,
                temperature=0,
                system="Tu es Indira. Ton unique but est de générer du code SVG valide. Ne salue pas. Ne commente pas.",
                messages=[{"role": "user", "content": prompt}]
            )
            
            raw_content = response.content[0].text.strip()

            svg_match = re.search(r'(<svg.*?</svg>)', raw_content, re.DOTALL | re.IGNORECASE)
            
            if svg_match:
                svg_code = svg_match.group(1)
            else:
                svg_code = raw_content.replace("```svg", "").replace("```", "").strip()

            if "<svg" not in svg_code.lower():
                logger.error(f"Contenu non-SVG reçu : {raw_content[:200]}")
                return '<svg width="500" height="500" xmlns="[http://www.w3.org/2000/svg](http://www.w3.org/2000/svg)"></svg>'

            return svg_code
        
        except json.JSONDecodeError as e:
            logger.error(f"Erreur JSON : {raw_content[:200]}")
            raise Exception("Format JSON invalide reçu de l'IA.")
        except Exception as e:
            logger.error(f"Erreur Claude : {e}")
            raise e


    async def generate_astrology_report(self, chart: dict, full_name: str, section_key: str, max_retries: int = 3) -> Dict[str, Any]:
        section_prompts = {
            "introduction": "Voyage au cœur de ton ciel : Une introduction immersive à l'astrologie comme outil de connaissance de soi et le message d'Indira pour ton évolution.",
            "piliers": "Les Fondations de l'Être : Analyse psychologique croisée et approfondie de ton 'Big Three' (Soleil, Lune, Ascendant). Comment ton essence, tes besoins émotionnels et ton masque social s'unissent.",
            "mental": "L'Alchimie de la Pensée : Étude détaillée de ton Mercure. Ta manière de traiter l'information, ton style de communication, tes apprentissages et ton fonctionnement intellectuel.",
            "dominantes": "Ta Signature Énergétique : Analyse de tes forces dominantes, de la répartition des éléments (Feu, Terre, Air, Eau) et des modes (Cardinal, Fixe, Mutable) qui régissent ton tempérament.",
            "maisons_vie_1": "La Roue du Destin (Partie I) : Exploration profonde des 6 premiers secteurs de vie. Ton identité (I), tes ressources (II), ton mental (III), tes racines (IV), ta créativité (V) et ton quotidien (VI).",
            "maisons_vie_2": "La Roue du Destin (Partie II) : Exploration des 6 secteurs relationnels et spirituels. Tes partenariats (VII), tes transformations (VIII), ta quête de sens (IX), ton destin social (X), tes projets (XI) et tes mystères (XII).",
            "amour": "Le Langage du Cœur : Analyse de Vénus, de Mars et de la Maison VII. Tes besoins affectifs, ta façon de séduire, d'aimer et ta dynamique de désir au sein du couple.",
            "mission": "L'Appel du Monde : Analyse de ta vocation et de ta réussite via le Milieu du Ciel (Maison X), Saturne (tes responsabilités) et la Maison VI (ton service au quotidien).",
            "destin": "La Boussole de l'Âme : Étude karmique et évolutive des Nœuds Lunaires (Nord et Sud) et de ta Part de Fortune pour comprendre ton chemin de croissance.",
            "ombres": "L'Espace de Guérison : Exploration des points sensibles. Ta blessure sacrée avec Chiron, tes désirs inconscients avec la Lune Noire et les héritages du passé.",
            "aspects_majeurs": "Le Dialogue des Astres : Analyse complexe des interactions géométriques majeures (Carrés, Trines, Oppositions). Tes défis intérieurs et tes dons innés.",
            "predictions": "Les Cycles à Venir : Analyse prospective détaillée des transits planétaires majeurs pour les 12 prochains mois et les opportunités de transformation à saisir.",
            "predictions_detailed": "L'Année Cosmique : Vos prévisions détaillées mois par mois pour les 12 prochains mois. Pour chaque mois, tu dois ABSOLUMENT fournir des paragraphes pour l'Amour, la Carrière, l'Énergie, et les Finances, en te basant sur les transits et la Révolution Solaire.",
            "karma": "La Boussole Karmique : Analyse évolutive et karmique profonde de ton Nœud Nord, de ta blessure sacrée avec ton Chiron natal (indique son signe/degré et sa maison, et la clé de guérison) et du timing de ton Retour de Saturne (première et deuxième occurrences).",
            "conseils": "Rituels et Harmonie : Actions concrètes, pratiques d'alignement et conseils holistiques pour incarner pleinement les énergies de ton thème.",
            "synthese": "L'Unité Retrouvée : Synthèse magistrale de ton ciel, message final de sagesse d'Indira et perspectives pour ton futur glorieux."
        }
        
        prompt = f"""
        ### RÔLE : Indira, astrologue experte. Tu tutoies {full_name}.
        ### DONNÉES DU THÈME : {chart}
        ### TÂCHE : Génère EXCLUSIVEMENT la section '{section_key}' : {section_prompts.get(section_key)}
        ### STYLE : Chaleureux, profond, sans jargon technique complexe.

        ### CONTRAINTES DE RÉDACTION (STRICTES) :
        1. Pour chaque bloc, cite le placement (ex: "Ta Lune en Verseau...").
        2. Développe chaque paragraphe de manière très riche (environts 50 à 120 mots par paragraphe maximum).
        3. INTERDICTION FORMELLE d'utiliser des retours à la ligne réels (touches Entrée) à l'intérieur des valeurs de texte. Utilise exclusivement '\\n' pour simuler un saut de ligne si nécessaire.
        4. N'utilise pas de caractères spéciaux non standards ou de guillemets doubles (") à l'intérieur de tes textes (utilise des guillemets simples ' à la place).

        IMPORTANT : Ton quota est de 5000 tokens, mais tu dois rester concis et structuré pour ne jamais tronquer la fermeture du JSON. Finis impérativement par '}}'.
        """
        
        report_tool = {
            "name": "submit_astrology_section",
            "description": "Soumet la section rédigée du rapport astrologique sous un format structuré.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "id": {"type": "string", "description": f"Doit être exactement '{section_key}'"},
                    "title": {"type": "string", "description": "Titre créatif court"},
                    "blocks": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "subtitle": {"type": "string", "description": "Sous-titre du bloc"},
                                "paragraphs": {
                                    "type": "array",
                                    "items": {"type": "string", "description": "Paragraphe de texte riche."}
                                },
                                "note": {"type": "string", "description": "Note de sagesse courte (optionnelle)"},
                                "conseil": {"type": "string", "description": "Conseil pratique (optionnel)"}
                            },
                            "required": ["subtitle", "paragraphs"]
                        }
                    },
                    "summary": {"type": "string", "description": "Conclusion synthétique de la section"}
                },
                "required": ["id", "title", "blocks", "summary"]
            }
        }
        
        for attempt in range(max_retries + 1):
            try:
                response = await self.client.messages.create(
                    model=self.model_name,
                    max_tokens=8000,
                    temperature=0.7,
                    system="Tu es Indira. Tu rédiges des rapports de thèmes astraux profonds et tu appelles l'outil mis à ta disposition pour renvoyer ton travail.",
                    tools=[report_tool],
                    tool_choice={"type": "tool", "name": "submit_astrology_section"},
                    messages=[{"role": "user", "content": prompt}]
                )

                tool_use = next((block for block in response.content if block.type == "tool_use"), None)
                
                if not tool_use:
                    raise ValueError("Le modèle a contourné l'outil de structuration.")

                result_json = tool_use.input
                
                if not result_json.get("blocks"):
                    raise ValueError("La structure renvoyée ne contient aucun bloc de contenu.")

                for block in result_json["blocks"]:
                    if "note" not in block:
                        block["note"] = None
                    if "conseil" not in block:
                        block["conseil"] = None

                return result_json

            except Exception as e:
                logger.warning(f"[Tentative {attempt + 1}/{max_retries + 1}] Erreur section {section_key} : {e}")
                if attempt == max_retries:
                    logger.error(f"Échec critique après {max_retries + 1} essais pour {section_key}.")
                    raise Exception(f"Erreur de génération de la section {section_key} : {e}")
        