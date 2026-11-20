"""Dés : tous les jets sont lancés ici, jamais par Claude.

Version de l'étape 1 : réussite si total >= difficulté. Les degrés (critiques),
la position, l'effet et le décalage de difficulté arrivent avec l'outil `jet`
(étape 2).
"""

from __future__ import annotations

import random
from dataclasses import dataclass

from mj.univers import DIFFICULTE_MAX, DIFFICULTE_MIN

_rng_par_defaut = random.SystemRandom()


@dataclass(frozen=True)
class ResultatJet:
    stat: str
    modificateur: int
    difficulte: int
    de: int
    total: int
    reussite: bool

    def en_texte(self) -> str:
        signe = "+" if self.modificateur >= 0 else "-"
        issue = "réussite" if self.reussite else "échec"
        return (
            f"Jet de {self.stat} contre {self.difficulte} : dé {self.de} {signe} "
            f"{abs(self.modificateur)} = {self.total}, {issue}."
        )


def lancer(faces: int, rng: random.Random | None = None) -> int:
    """Lance un dé à `faces` faces (résultat de 1 à faces)."""
    if faces < 2:
        raise ValueError(f"Un dé doit avoir au moins 2 faces (reçu {faces}).")
    return (rng or _rng_par_defaut).randint(1, faces)


def jet(
    stat: str,
    modificateur: int,
    difficulte: int,
    faces: int,
    rng: random.Random | None = None,
) -> ResultatJet:
    """Lance le dé, ajoute le modificateur de la stat et compare à la difficulté."""
    if not DIFFICULTE_MIN <= difficulte <= DIFFICULTE_MAX:
        raise ValueError(
            f"La difficulté doit être entre {DIFFICULTE_MIN} et {DIFFICULTE_MAX} (reçu {difficulte})."
        )
    de = lancer(faces, rng)
    total = de + modificateur
    return ResultatJet(stat, modificateur, difficulte, de, total, total >= difficulte)
