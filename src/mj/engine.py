"""Moteur de l'étape 1 : assemble le contexte, appelle Claude, garde l'historique.

Aucun outil à ce stade ; l'état est fixe (valeurs de départ de la fiche d'univers).
Le moteur ne dépend pas du terminal, pour rester testable avec un faux client.
"""

from __future__ import annotations

import random
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from mj import dice
from mj.config import Config
from mj.univers import Univers

DIFFICULTES = ("facile", "normal", "brutal", "kenshi")
MAX_TOKENS = 16000

FICHIERS_SYSTEME = ("base.md", "etape1_sans_outils.md")
FICHIER_OUVERTURE = "ouverture.md"


class ReponseRefusee(Exception):
    """Claude a refusé de répondre (stop_reason « refusal »)."""


class ReponseVide(Exception):
    """La réponse ne contient aucun texte à afficher."""


class JetInvalide(ValueError):
    """Commande de jet invalide ; le message est destiné au joueur."""


@dataclass(frozen=True)
class Tour:
    texte: str
    tronque: bool
    jetons_entree: int
    jetons_cache: int
    jetons_sortie: int


def compter_mots_recit(texte: str) -> int:
    """Compte les mots du récit, sans la liste de choix ni la demande de jet."""
    lignes = []
    for ligne in texte.splitlines():
        if re.match(r"\s*(1[.)]|JET DEMANDÉ)", ligne):
            break
        lignes.append(ligne)
    return len(re.findall(r"\w+(?:['’-]\w+)*", "\n".join(lignes)))


def etat_initial(univers: Univers, nom: str | None, difficulte: str) -> dict[str, Any]:
    """État du jeu de l'étape 1 : personnage aux valeurs de départ de la fiche."""
    return {
        "univers": univers.id,
        "difficulte": difficulte,
        "personnage": {
            "nom": nom or "(pas encore nommé)",
            "stats": dict(univers.stats),
            "ressources": {nom_r: r.debut for nom_r, r in univers.ressources.items()},
        },
    }


def construire_systeme(dossier_prompts: Path, univers: Univers, etat: dict[str, Any]) -> str:
    """Prompt système : prompt de base, consignes d'étape, fiche d'univers, état du jeu."""
    parties = [(dossier_prompts / nom).read_text(encoding="utf-8").strip() for nom in FICHIERS_SYSTEME]
    parties.append(f"FICHE D'UNIVERS\n```yaml\n{univers.source.strip()}\n```")
    etat_yaml = yaml.safe_dump(etat, allow_unicode=True, sort_keys=False).strip()
    parties.append(f"ÉTAT DU JEU\n```yaml\n{etat_yaml}\n```")
    return "\n\n".join(parties)


class MaitreDuJeu:
    def __init__(
        self,
        client: Any,
        config: Config,
        univers: Univers,
        dossier_prompts: Path,
        nom_personnage: str | None = None,
        difficulte: str = "normal",
        rng: random.Random | None = None,
    ) -> None:
        if difficulte not in DIFFICULTES:
            raise ValueError(f"Difficulté inconnue : {difficulte!r} (attendu : {', '.join(DIFFICULTES)}).")
        self.client = client
        self.config = config
        self.univers = univers
        self.dossier_prompts = dossier_prompts
        self.difficulte = difficulte
        self.rng = rng
        self.etat = etat_initial(univers, nom_personnage, difficulte)
        self.systeme = construire_systeme(dossier_prompts, univers, self.etat)
        self.messages: list[dict[str, Any]] = []

    def ouvrir(self) -> Tour:
        """Premier tour : demande à Claude d'ouvrir la première scène."""
        ouverture = (self.dossier_prompts / FICHIER_OUVERTURE).read_text(encoding="utf-8").strip()
        return self.jouer(ouverture)

    def jouer(self, texte_joueur: str) -> Tour:
        """Envoie l'action du joueur et renvoie le tour du MJ.

        En cas d'erreur, l'historique est laissé tel qu'avant l'appel.
        """
        self.messages.append({"role": "user", "content": texte_joueur})
        try:
            reponse = self.client.messages.create(**self._parametres())
        except BaseException:
            self.messages.pop()
            raise

        if reponse.stop_reason == "refusal":
            self.messages.pop()
            details = getattr(reponse, "stop_details", None)
            categorie = getattr(details, "category", None)
            raise ReponseRefusee(f"catégorie : {categorie}" if categorie else "sans précision")

        texte = "\n\n".join(b.text for b in reponse.content if b.type == "text").strip()
        if not texte:
            self.messages.pop()
            raise ReponseVide(f"stop_reason : {reponse.stop_reason}")

        # Le contenu complet (blocs de réflexion compris) repart tel quel au tour suivant.
        self.messages.append({"role": "assistant", "content": reponse.content})

        usage = reponse.usage
        return Tour(
            texte=texte,
            tronque=reponse.stop_reason == "max_tokens",
            jetons_entree=(usage.input_tokens or 0)
            + (getattr(usage, "cache_read_input_tokens", 0) or 0)
            + (getattr(usage, "cache_creation_input_tokens", 0) or 0),
            jetons_cache=getattr(usage, "cache_read_input_tokens", 0) or 0,
            jetons_sortie=usage.output_tokens or 0,
        )

    def jet(self, stat: str, difficulte: str) -> dice.ResultatJet:
        """Jet demandé par le joueur : stat de la fiche, difficulté en nombre ou nom de seuil."""
        if stat not in self.univers.stats:
            raise JetInvalide(
                f"Stat inconnue : « {stat} ». Stats de cet univers : {', '.join(self.univers.stats)}."
            )
        if difficulte in self.univers.seuils_difficulte:
            valeur = self.univers.seuils_difficulte[difficulte]
        else:
            try:
                valeur = int(difficulte)
            except ValueError:
                seuils = ", ".join(self.univers.seuils_difficulte)
                raise JetInvalide(
                    f"Difficulté invalide : « {difficulte} ». Donne un nombre ou un seuil ({seuils})."
                ) from None
        try:
            return dice.jet(stat, self.univers.stats[stat], valeur, self.univers.faces, self.rng)
        except ValueError as erreur:
            raise JetInvalide(str(erreur)) from None

    def _parametres(self) -> dict[str, Any]:
        parametres: dict[str, Any] = {
            "model": self.config.modele,
            "max_tokens": MAX_TOKENS,
            "system": self.systeme,
            "messages": self.messages,
            # Met en cache le préfixe (système + historique) d'un tour à l'autre.
            "cache_control": {"type": "ephemeral"},
        }
        if self.config.effort:
            parametres["output_config"] = {"effort": self.config.effort}
        return parametres
