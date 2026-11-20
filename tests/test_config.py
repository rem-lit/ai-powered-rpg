import pytest

from mj.config import ConfigErreur, charger_dotenv, lire_config


def test_dotenv(tmp_path):
    (tmp_path / ".env").write_text(
        "# commentaire\n"
        "MJ_MODEL=modele-a\n"
        "export MJ_EFFORT='high'\n"
        'AUTRE="avec = signe"\n'
        "ligne sans egal\n",
        encoding="utf-8",
    )
    environ = {}
    charger_dotenv(tmp_path / ".env", environ)
    assert environ == {"MJ_MODEL": "modele-a", "MJ_EFFORT": "high", "AUTRE": "avec = signe"}


def test_dotenv_n_ecrase_pas_l_environnement(tmp_path):
    (tmp_path / ".env").write_text("MJ_MODEL=fichier\n", encoding="utf-8")
    environ = {"MJ_MODEL": "terminal"}
    charger_dotenv(tmp_path / ".env", environ)
    assert environ["MJ_MODEL"] == "terminal"


def test_dotenv_absent(tmp_path):
    environ = {}
    charger_dotenv(tmp_path / ".env", environ)
    assert environ == {}


def test_config_complete():
    config = lire_config({"ANTHROPIC_API_KEY": "k", "MJ_MODEL": "m", "MJ_EFFORT": "low"})
    assert (config.modele, config.effort) == ("m", "low")


def test_effort_vide_par_defaut():
    assert lire_config({"ANTHROPIC_API_KEY": "k", "MJ_MODEL": "m", "MJ_EFFORT": ""}).effort is None


@pytest.mark.parametrize(
    "environ, attendu",
    [
        ({"MJ_MODEL": "m"}, "ANTHROPIC_API_KEY"),
        ({"ANTHROPIC_API_KEY": "k"}, "MJ_MODEL"),
        ({"ANTHROPIC_API_KEY": "k", "MJ_MODEL": "m", "MJ_EFFORT": "énorme"}, "MJ_EFFORT"),
    ],
)
def test_config_invalide(environ, attendu):
    with pytest.raises(ConfigErreur, match=attendu):
        lire_config(environ)
