"""Chargement et validation des fiches d'univers (YAML)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

DIFFICULTE_MIN = 5
DIFFICULTE_MAX = 25

_CHAMPS_TEXTE = ("id", "nom", "ton", "intro")
_LISTES_DE_TEXTES = ("lieux_cles", "factions", "regles_speciales", "secrets")


class UniversInvalide(ValueError):
    """Fiche d'univers invalide ; le message liste toutes les erreurs trouvées."""


@dataclass(frozen=True)
class Ressource:
    debut: int
    min: int
    max: int


@dataclass(frozen=True)
class Univers:
    id: str
    nom: str
    faces: int
    stats: dict[str, int]
    ressources: dict[str, Ressource]
    seuils_difficulte: dict[str, int]
    fiche: dict[str, Any]
    source: str
    """Texte YAML d'origine, injecté tel quel dans le prompt."""


def _est_entier(valeur: Any) -> bool:
    return isinstance(valeur, int) and not isinstance(valeur, bool)


def _texte_non_vide(valeur: Any) -> bool:
    return isinstance(valeur, str) and bool(valeur.strip())


def lister_univers(dossier: Path) -> list[str]:
    """Ids des univers disponibles (noms des fichiers .yaml du dossier)."""
    return sorted(p.stem for p in dossier.glob("*.yaml"))


def charger_univers(chemin: Path) -> Univers:
    """Lit une fiche d'univers et la valide. L'id doit correspondre au nom du fichier."""
    try:
        source = chemin.read_text(encoding="utf-8")
    except FileNotFoundError:
        raise UniversInvalide(f"Fiche d'univers introuvable : {chemin}") from None
    try:
        fiche = yaml.safe_load(source)
    except yaml.YAMLError as erreur:
        raise UniversInvalide(f"{chemin.name} n'est pas un YAML valide : {erreur}") from None
    return valider_fiche(fiche, source=source, id_attendu=chemin.stem)


def valider_fiche(fiche: Any, source: str = "", id_attendu: str | None = None) -> Univers:
    """Vérifie une fiche d'univers et renvoie l'objet Univers ; lève UniversInvalide sinon."""
    if not isinstance(fiche, dict):
        raise UniversInvalide("La fiche d'univers doit être un objet YAML (clé: valeur).")

    erreurs: list[str] = []

    for champ in _CHAMPS_TEXTE:
        if not _texte_non_vide(fiche.get(champ)):
            erreurs.append(f"« {champ} » est obligatoire et doit être un texte non vide.")
    if id_attendu is not None and _texte_non_vide(fiche.get("id")) and fiche["id"] != id_attendu:
        erreurs.append(f"« id » vaut {fiche['id']!r} mais le fichier s'appelle {id_attendu}.yaml.")

    faces = 0
    correspondance = re.fullmatch(r"d(\d+)", str(fiche.get("de", "")))
    if correspondance and int(correspondance.group(1)) >= 2:
        faces = int(correspondance.group(1))
    else:
        erreurs.append("« de » doit être de la forme d<faces>, par exemple d20.")

    stats = fiche.get("stats")
    if not isinstance(stats, dict) or not stats:
        erreurs.append("« stats » doit lister au moins une stat (nom: valeur de départ).")
        stats = {}
    for nom, valeur in stats.items():
        if not _est_entier(valeur):
            erreurs.append(f"La stat « {nom} » doit avoir une valeur entière (reçu {valeur!r}).")

    ressources: dict[str, Ressource] = {}
    brutes = fiche.get("ressources")
    if not isinstance(brutes, dict) or not brutes:
        erreurs.append("« ressources » doit lister au moins une ressource (nom: {debut, min, max}).")
        brutes = {}
    for nom, bornes in brutes.items():
        if not isinstance(bornes, dict) or not all(_est_entier(bornes.get(k)) for k in ("debut", "min", "max")):
            erreurs.append(f"La ressource « {nom} » doit avoir debut, min et max entiers.")
            continue
        if not bornes["min"] <= bornes["debut"] <= bornes["max"]:
            erreurs.append(
                f"La ressource « {nom} » doit vérifier min <= debut <= max "
                f"(reçu min={bornes['min']}, debut={bornes['debut']}, max={bornes['max']})."
            )
            continue
        ressources[nom] = Ressource(bornes["debut"], bornes["min"], bornes["max"])

    for nom in set(stats) & set(brutes):
        erreurs.append(f"« {nom} » est à la fois une stat et une ressource.")

    seuils = fiche.get("seuils_difficulte")
    if not isinstance(seuils, dict) or not seuils:
        erreurs.append("« seuils_difficulte » doit lister au moins un seuil (nom: valeur).")
        seuils = {}
    for nom, valeur in seuils.items():
        if not _est_entier(valeur) or not DIFFICULTE_MIN <= valeur <= DIFFICULTE_MAX:
            erreurs.append(
                f"Le seuil « {nom} » doit être un entier entre {DIFFICULTE_MIN} et {DIFFICULTE_MAX}."
            )

    for champ in _LISTES_DE_TEXTES:
        valeur = fiche.get(champ)
        if valeur is not None and (
            not isinstance(valeur, list) or not all(_texte_non_vide(v) for v in valeur)
        ):
            erreurs.append(f"« {champ} » doit être une liste de textes.")

    horloges = fiche.get("horloges")
    if horloges is not None:
        if not isinstance(horloges, list):
            erreurs.append("« horloges » doit être une liste.")
            horloges = []
        for horloge in horloges:
            if not (
                isinstance(horloge, dict)
                and _texte_non_vide(horloge.get("id"))
                and _texte_non_vide(horloge.get("nom"))
                and _est_entier(horloge.get("segments"))
                and _est_entier(horloge.get("rempli"))
                and 0 <= horloge["rempli"] <= horloge["segments"]
                and horloge["segments"] > 0
            ):
                erreurs.append(
                    f"Horloge invalide : {horloge!r} (id, nom, segments > 0, 0 <= rempli <= segments)."
                )

    if erreurs:
        nom_fiche = fiche.get("id") or id_attendu or "?"
        raise UniversInvalide(
            f"Fiche d'univers « {nom_fiche} » invalide :\n" + "\n".join(f"- {e}" for e in erreurs)
        )

    return Univers(
        id=fiche["id"],
        nom=fiche["nom"],
        faces=faces,
        stats=dict(stats),
        ressources=ressources,
        seuils_difficulte=dict(seuils),
        fiche=fiche,
        source=source,
    )
