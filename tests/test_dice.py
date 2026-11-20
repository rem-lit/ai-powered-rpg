import random

import pytest

from mj import dice


def test_lancer_reste_dans_les_bornes():
    rng = random.Random(1)
    tirages = {dice.lancer(20, rng) for _ in range(2000)}
    assert tirages == set(range(1, 21))


def test_lancer_refuse_un_de_impossible():
    with pytest.raises(ValueError):
        dice.lancer(1)


def test_jet_reproductible_avec_graine():
    a = dice.jet("ruse", 1, 12, 20, random.Random(42))
    b = dice.jet("ruse", 1, 12, 20, random.Random(42))
    assert a == b
    assert a.total == a.de + 1
    assert a.reussite == (a.total >= 12)


class DeTruque(random.Random):
    def __init__(self, valeur):
        super().__init__()
        self.valeur = valeur

    def randint(self, a, b):
        return self.valeur


def test_egalite_vaut_reussite():
    assert dice.jet("vigueur", 2, 12, 20, DeTruque(10)).reussite


def test_echec_sous_la_difficulte():
    resultat = dice.jet("vigueur", 2, 12, 20, DeTruque(9))
    assert not resultat.reussite
    assert resultat.en_texte() == "Jet de vigueur contre 12 : dé 9 + 2 = 11, échec."


def test_modificateur_negatif_affiche():
    assert "dé 9 - 1 = 8" in dice.jet("foi", -1, 5, 20, DeTruque(9)).en_texte()


@pytest.mark.parametrize("difficulte", [4, 26])
def test_difficulte_hors_plage(difficulte):
    with pytest.raises(ValueError, match="entre 5 et 25"):
        dice.jet("ruse", 1, difficulte, 20)


@pytest.mark.parametrize("difficulte", [5, 25])
def test_difficulte_aux_bornes(difficulte):
    dice.jet("ruse", 1, difficulte, 20)
