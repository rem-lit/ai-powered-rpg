"""Interface en ligne de commande de l'étape 1 : jouer une partie dans le terminal."""

from __future__ import annotations

import argparse
import shutil
import sys
import textwrap
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

import anthropic

from mj.config import RACINE, Config, ConfigErreur, charger_dotenv, lire_config
from mj.engine import (
    DIFFICULTES,
    JetInvalide,
    MaitreDuJeu,
    ReponseRefusee,
    ReponseVide,
    Tour,
    compter_mots_recit,
)
from mj.univers import UniversInvalide, charger_univers, lister_univers

DOSSIER_UNIVERS = RACINE / "universes"
DOSSIER_PROMPTS = RACINE / "prompts"
DOSSIER_TRANSCRIPTIONS = RACINE / "saves" / "cli"

AIDE = """\
Écris ton action librement, ou tape 1, 2 ou 3 pour un des choix proposés.
Commandes :
  /jet <stat> <difficulté>  lance le dé (difficulté en nombre ou nom de seuil)
  /renvoyer                 renvoie le dernier message si l'appel a échoué
  /aide                     affiche cette aide
  /quitter                  termine la partie"""


def afficher(texte: str) -> None:
    largeur = min(shutil.get_terminal_size((88, 24)).columns, 88)
    for ligne in texte.splitlines():
        print(textwrap.fill(ligne, width=largeur) if ligne.strip() else "")


def afficher_tour(tour: Tour) -> None:
    print()
    afficher(tour.texte)
    if tour.tronque:
        print("\n(Réponse coupée : limite de longueur atteinte.)")
    print(
        f"\n  · {compter_mots_recit(tour.texte)} mots · jetons : entrée {tour.jetons_entree}"
        f" (dont {tour.jetons_cache} en cache), sortie {tour.jetons_sortie}"
    )


class Transcription:
    """Garde une trace lisible de la partie dans saves/cli/ (hors dépôt)."""

    def __init__(self, dossier: Path, univers_id: str, entete: str) -> None:
        dossier.mkdir(parents=True, exist_ok=True)
        horodatage = datetime.now().strftime("%Y-%m-%d-%H%M%S")
        self.chemin = dossier / f"{horodatage}-{univers_id}.md"
        self.chemin.write_text(entete + "\n", encoding="utf-8")

    def ajouter(self, titre: str, texte: str) -> None:
        with self.chemin.open("a", encoding="utf-8") as fichier:
            fichier.write(f"\n## {titre}\n\n{texte}\n")


def appeler(config: Config, action: Callable[[], Tour]) -> Tour | None:
    """Appelle Claude et traduit les erreurs en messages lisibles."""
    print("\n(Le MJ réfléchit…)", flush=True)
    try:
        return action()
    except anthropic.AuthenticationError:
        print("Clé API refusée : vérifie ANTHROPIC_API_KEY.")
    except anthropic.PermissionDeniedError as erreur:
        print(f"Accès refusé par l'API : {erreur.message}")
    except anthropic.NotFoundError:
        print(f"Modèle introuvable : vérifie MJ_MODEL (actuellement {config.modele!r}).")
    except anthropic.RateLimitError:
        print("Limite de débit atteinte : attends un peu, puis tape /renvoyer.")
    except anthropic.BadRequestError as erreur:
        print(f"Requête refusée par l'API : {erreur.message}")
    except anthropic.APIStatusError as erreur:
        print(f"Erreur de l'API ({erreur.status_code}) : {erreur.message}. Tape /renvoyer pour réessayer.")
    except anthropic.APIConnectionError:
        print("Impossible de joindre l'API (réseau). Tape /renvoyer pour réessayer.")
    except ReponseRefusee as erreur:
        print(f"(Claude a refusé de répondre à ce message, {erreur}. Reformule ton action.)")
    except ReponseVide as erreur:
        print(f"(Réponse vide, {erreur}. Tape /renvoyer pour réessayer.)")
    return None


def choisir_univers(demande: str | None) -> str | None:
    disponibles = lister_univers(DOSSIER_UNIVERS)
    if demande:
        if demande in disponibles:
            return demande
        print(f"Univers inconnu : {demande!r}. Disponibles : {', '.join(disponibles) or 'aucun'}.")
        return None
    if not disponibles:
        print(f"Aucune fiche d'univers dans {DOSSIER_UNIVERS}.")
        return None
    if len(disponibles) == 1:
        return disponibles[0]
    print("Univers disponibles : " + ", ".join(disponibles))
    choix = input("Univers : ").strip()
    return choix if choix in disponibles else None


def analyser_arguments(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="mj", description="Jeu de rôle narratif solo avec Claude comme maître du jeu (étape 1)."
    )
    parser.add_argument("univers", nargs="?", help="id de l'univers (fichier universes/<id>.yaml)")
    parser.add_argument("--nom", help="nom du personnage")
    parser.add_argument("--difficulte", choices=DIFFICULTES, default="normal", help="niveau de difficulté")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = analyser_arguments(argv)
    charger_dotenv(RACINE / ".env")
    try:
        config = lire_config()
    except ConfigErreur as erreur:
        print(erreur, file=sys.stderr)
        return 2

    try:
        univers_id = choisir_univers(args.univers)
        if univers_id is None:
            return 2
        univers = charger_univers(DOSSIER_UNIVERS / f"{univers_id}.yaml")
    except UniversInvalide as erreur:
        print(erreur, file=sys.stderr)
        return 2
    except (EOFError, KeyboardInterrupt):
        return 0

    print(f"\n=== {univers.nom} · difficulté {args.difficulte} · modèle {config.modele} ===")
    try:
        nom = args.nom if args.nom is not None else input("Nom de ton personnage (Entrée pour passer) : ")
    except (EOFError, KeyboardInterrupt):
        return 0
    nom = nom.strip() or None

    mj = MaitreDuJeu(
        anthropic.Anthropic(),
        config,
        univers,
        DOSSIER_PROMPTS,
        nom_personnage=nom,
        difficulte=args.difficulte,
    )
    transcription = Transcription(
        DOSSIER_TRANSCRIPTIONS,
        univers.id,
        f"# {univers.nom}\n\nPersonnage : {nom or '(sans nom)'} · difficulté : {args.difficulte}"
        f" · modèle : {config.modele}",
    )
    print(AIDE)

    tour = appeler(config, mj.ouvrir)
    if tour is None:
        print("La partie n'a pas pu commencer.")
        return 1
    transcription.ajouter("MJ", tour.texte)
    afficher_tour(tour)

    en_attente: str | None = None
    while True:
        try:
            saisie = input("\n> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not saisie:
            continue

        commande, *arguments = saisie.split()
        if commande in ("/quitter", "/q"):
            break
        if commande == "/aide":
            print(AIDE)
            continue
        if commande == "/renvoyer":
            if en_attente is None:
                print("Rien à renvoyer.")
                continue
            message = en_attente
        elif commande == "/jet":
            if len(arguments) != 2:
                print("Usage : /jet <stat> <difficulté>, par exemple /jet ruse 12 ou /jet ruse moyen")
                continue
            try:
                resultat = mj.jet(*arguments)
            except JetInvalide as erreur:
                print(erreur)
                continue
            message = f"[{resultat.en_texte()}]"
            print(message)
        elif commande.startswith("/"):
            print(f"Commande inconnue : {commande}. Tape /aide.")
            continue
        else:
            message = saisie

        tour = appeler(config, lambda: mj.jouer(message))
        if tour is None:
            en_attente = message
            continue
        en_attente = None
        transcription.ajouter("Joueur", message)
        transcription.ajouter("MJ", tour.texte)
        afficher_tour(tour)

    print(f"Fin de la partie. Transcription : {transcription.chemin}")
    return 0
