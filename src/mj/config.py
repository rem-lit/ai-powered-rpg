"""Configuration : variables d'environnement, avec un fichier .env local facultatif."""

from __future__ import annotations

import os
from collections.abc import MutableMapping
from dataclasses import dataclass
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
"""Racine du dépôt (contient prompts/, universes/, saves/)."""

EFFORTS = ("low", "medium", "high", "xhigh", "max")


class ConfigErreur(Exception):
    """Configuration absente ou invalide ; le message est destiné au joueur."""


@dataclass(frozen=True)
class Config:
    modele: str
    effort: str | None = None


def charger_dotenv(chemin: Path, environ: MutableMapping[str, str] = os.environ) -> None:
    """Charge un fichier .env simple (CLE=valeur) sans écraser les variables déjà définies."""
    if not chemin.is_file():
        return
    for ligne in chemin.read_text(encoding="utf-8").splitlines():
        ligne = ligne.strip()
        if not ligne or ligne.startswith("#") or "=" not in ligne:
            continue
        cle, _, valeur = ligne.partition("=")
        cle = cle.strip().removeprefix("export ").strip()
        valeur = valeur.strip()
        if len(valeur) >= 2 and valeur[0] == valeur[-1] and valeur[0] in "\"'":
            valeur = valeur[1:-1]
        if cle:
            environ.setdefault(cle, valeur)


def lire_config(environ: MutableMapping[str, str] = os.environ) -> Config:
    """Lit et vérifie la configuration du MJ."""
    if not environ.get("ANTHROPIC_API_KEY", "").strip():
        raise ConfigErreur(
            "ANTHROPIC_API_KEY n'est pas définie. Mets ta clé dans le fichier .env "
            "(voir .env.example) ou exporte-la dans ton terminal."
        )
    modele = environ.get("MJ_MODEL", "").strip()
    if not modele:
        raise ConfigErreur(
            "MJ_MODEL n'est pas défini. Choisis un modèle Claude dans le fichier .env "
            "(voir .env.example)."
        )
    effort = environ.get("MJ_EFFORT", "").strip() or None
    if effort is not None and effort not in EFFORTS:
        raise ConfigErreur(
            f"MJ_EFFORT={effort!r} est invalide. Valeurs possibles : {', '.join(EFFORTS)}, "
            "ou laisser vide pour la valeur par défaut du modèle."
        )
    return Config(modele=modele, effort=effort)
