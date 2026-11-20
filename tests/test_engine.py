import copy
import random
from types import SimpleNamespace

import pytest

from mj.config import Config
from mj.engine import (
    JetInvalide,
    MaitreDuJeu,
    ReponseRefusee,
    ReponseVide,
    compter_mots_recit,
)


def reponse(texte="Le vent se lève.", stop_reason="end_turn", **usage):
    contenu = [SimpleNamespace(type="thinking", thinking=""), SimpleNamespace(type="text", text=texte)]
    usage = {"input_tokens": 10, "output_tokens": 5, "cache_read_input_tokens": 0,
             "cache_creation_input_tokens": 0} | usage
    return SimpleNamespace(content=contenu, stop_reason=stop_reason, usage=SimpleNamespace(**usage),
                           stop_details=None)


class FauxClient:
    """Imite client.messages.create : renvoie les réponses prévues, note les appels."""

    def __init__(self, *reponses):
        self.reponses = list(reponses)
        self.appels = []
        self.messages = self

    def create(self, **kwargs):
        self.appels.append(copy.deepcopy(kwargs))
        suivante = self.reponses.pop(0)
        if isinstance(suivante, BaseException):
            raise suivante
        return suivante


@pytest.fixture
def config():
    return Config(modele="modele-test")


def creer_mj(client, config, logres, racine, **kwargs):
    return MaitreDuJeu(client, config, logres, racine / "prompts", **kwargs)


def test_systeme_contient_prompt_fiche_et_etat(config, logres, racine):
    mj = creer_mj(FauxClient(), config, logres, racine, nom_personnage="Yvain", difficulte="kenshi")
    assert mj.systeme.startswith("Tu es le Maître du Jeu")
    assert "CONSIGNES TEMPORAIRES" in mj.systeme
    assert "FICHE D'UNIVERS" in mj.systeme and "lettre scellée de Merlin" in mj.systeme
    assert "nom: Yvain" in mj.systeme
    assert "difficulte: kenshi" in mj.systeme
    assert "pv: 20" in mj.systeme


def test_ouverture_puis_tour(config, logres, racine):
    client = FauxClient(reponse("Scène 1"), reponse("Scène 2", input_tokens=3, cache_read_input_tokens=100))
    mj = creer_mj(client, config, logres, racine)

    assert mj.ouvrir().texte == "Scène 1"
    tour = mj.jouer("J'ouvre la porte.")
    assert tour.texte == "Scène 2"
    assert (tour.jetons_entree, tour.jetons_cache) == (103, 100)

    premier, second = client.appels
    assert premier["model"] == "modele-test"
    assert premier["cache_control"] == {"type": "ephemeral"}
    assert "output_config" not in premier
    assert "Début de la partie" in premier["messages"][0]["content"]
    assert [m["role"] for m in second["messages"]] == ["user", "assistant", "user"]
    # Le contenu complet (réflexion comprise) est renvoyé tel quel.
    assert [b.type for b in second["messages"][1]["content"]] == ["thinking", "text"]
    assert second["messages"][2]["content"] == "J'ouvre la porte."


def test_effort_transmis(logres, racine):
    client = FauxClient(reponse())
    creer_mj(client, Config("m", effort="high"), logres, racine).ouvrir()
    assert client.appels[0]["output_config"] == {"effort": "high"}


def test_erreur_api_laisse_l_historique_intact(config, logres, racine):
    client = FauxClient(reponse(), RuntimeError("réseau"), reponse("Reprise"))
    mj = creer_mj(client, config, logres, racine)
    mj.ouvrir()
    with pytest.raises(RuntimeError):
        mj.jouer("Action perdue")
    assert len(mj.messages) == 2
    assert mj.jouer("Action perdue").texte == "Reprise"
    assert [m["role"] for m in mj.messages] == ["user", "assistant", "user", "assistant"]


def test_refus_retire_le_message(config, logres, racine):
    mj = creer_mj(FauxClient(reponse(), reponse("", stop_reason="refusal")), config, logres, racine)
    mj.ouvrir()
    with pytest.raises(ReponseRefusee):
        mj.jouer("...")
    assert len(mj.messages) == 2


def test_reponse_sans_texte(config, logres, racine):
    mj = creer_mj(FauxClient(reponse("   ")), config, logres, racine)
    with pytest.raises(ReponseVide):
        mj.ouvrir()
    assert mj.messages == []


def test_reponse_tronquee_signalee(config, logres, racine):
    mj = creer_mj(FauxClient(reponse("Coupé au mil", stop_reason="max_tokens")), config, logres, racine)
    assert mj.ouvrir().tronque


def test_difficulte_inconnue(config, logres, racine):
    with pytest.raises(ValueError):
        creer_mj(FauxClient(), config, logres, racine, difficulte="impossible")


def test_jet_par_seuil_et_par_nombre(config, logres, racine):
    mj = creer_mj(FauxClient(), config, logres, racine, rng=random.Random(3))
    par_seuil = mj.jet("ruse", "moyen")
    assert par_seuil.difficulte == 12 and par_seuil.modificateur == 1
    assert mj.jet("honneur", "15").difficulte == 15


@pytest.mark.parametrize(
    "stat, difficulte, attendu",
    [("charisme", "12", "Stat inconnue"), ("ruse", "dingue", "Difficulté invalide"), ("ruse", "30", "entre 5 et 25")],
)
def test_jet_invalide(config, logres, racine, stat, difficulte, attendu):
    mj = creer_mj(FauxClient(), config, logres, racine)
    with pytest.raises(JetInvalide, match=attendu):
        mj.jet(stat, difficulte)


def test_compter_mots_ignore_choix_et_jet():
    texte = "La pluie tombe sur l'auberge.\n\n1. Fuir\n2. Combattre\n3. Parler"
    assert compter_mots_recit(texte) == 5
    assert compter_mots_recit("Il hésite.\nJET DEMANDÉ : ruse contre 12") == 2
