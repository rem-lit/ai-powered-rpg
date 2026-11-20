import copy

import pytest
import yaml

from mj.univers import UniversInvalide, charger_univers, lister_univers, valider_fiche


def test_logres_est_valide(logres):
    assert logres.id == "logres"
    assert logres.faces == 20
    assert logres.stats == {"vigueur": 2, "ruse": 1, "honneur": 3, "foi": 0}
    assert logres.ressources["pv"].debut == 20
    assert logres.ressources["pv"].max == 20
    assert "Merlin" in logres.source


def test_tous_les_univers_du_depot_sont_valides(racine):
    ids = lister_univers(racine / "universes")
    assert "logres" in ids
    for univers_id in ids:
        charger_univers(racine / "universes" / f"{univers_id}.yaml")


@pytest.fixture
def fiche(logres):
    return copy.deepcopy(logres.fiche)


def _erreur(fiche, **kwargs) -> str:
    with pytest.raises(UniversInvalide) as info:
        valider_fiche(fiche, **kwargs)
    return str(info.value)


def test_champ_obligatoire_absent(fiche):
    del fiche["intro"]
    assert "intro" in _erreur(fiche)


def test_toutes_les_erreurs_sont_listees(fiche):
    del fiche["ton"]
    fiche["de"] = "d1"
    message = _erreur(fiche)
    assert "ton" in message and "de" in message


def test_id_different_du_fichier(fiche):
    assert "logres2.yaml" in _erreur(fiche, id_attendu="logres2")


def test_de_mal_forme(fiche):
    fiche["de"] = "vingt"
    assert "d20" in _erreur(fiche)


def test_stat_non_entiere(fiche):
    fiche["stats"]["ruse"] = "beaucoup"
    assert "ruse" in _erreur(fiche)


def test_stat_booleenne_refusee(fiche):
    fiche["stats"]["foi"] = True
    assert "foi" in _erreur(fiche)


def test_ressource_hors_bornes(fiche):
    fiche["ressources"]["pv"] = {"debut": 25, "min": 0, "max": 20}
    assert "pv" in _erreur(fiche)


def test_ressource_incomplete(fiche):
    fiche["ressources"]["pv"] = {"debut": 20}
    assert "pv" in _erreur(fiche)


def test_nom_partage_entre_stat_et_ressource(fiche):
    fiche["ressources"]["ruse"] = {"debut": 1, "min": 0, "max": 5}
    assert "ruse" in _erreur(fiche)


@pytest.mark.parametrize("valeur", [4, 26, "dur"])
def test_seuil_hors_plage(fiche, valeur):
    fiche["seuils_difficulte"]["moyen"] = valeur
    assert "moyen" in _erreur(fiche)


def test_horloge_trop_remplie(fiche):
    fiche["horloges"] = [{"id": "h1", "nom": "x", "segments": 4, "rempli": 5}]
    assert "Horloge" in _erreur(fiche)


def test_liste_de_textes_invalide(fiche):
    fiche["secrets"] = ["ok", 3]
    assert "secrets" in _erreur(fiche)


def test_fiche_qui_n_est_pas_un_objet():
    assert "objet" in _erreur(["pas", "un", "objet"])


def test_fichier_introuvable(tmp_path):
    with pytest.raises(UniversInvalide, match="introuvable"):
        charger_univers(tmp_path / "absent.yaml")


def test_yaml_invalide(tmp_path):
    chemin = tmp_path / "casse.yaml"
    chemin.write_text("id: [non fermé", encoding="utf-8")
    with pytest.raises(UniversInvalide, match="YAML"):
        charger_univers(chemin)


def test_univers_minimal_d_un_autre_genre(tmp_path):
    fiche = {
        "id": "orbite",
        "nom": "Station Orbite",
        "ton": "Huis clos spatial, paranoïa.",
        "de": "d12",
        "stats": {"pilotage": 1, "piratage": 2, "sang-froid": 0},
        "ressources": {"oxygene": {"debut": 10, "min": 0, "max": 10}},
        "seuils_difficulte": {"moyen": 8},
        "intro": "L'alarme hurle.",
    }
    chemin = tmp_path / "orbite.yaml"
    chemin.write_text(yaml.safe_dump(fiche, allow_unicode=True), encoding="utf-8")
    univers = charger_univers(chemin)
    assert univers.faces == 12
    assert set(univers.stats) == {"pilotage", "piratage", "sang-froid"}
