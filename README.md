# Jeu de rôle narratif : Claude MJ

Jeu de rôle solo en local où Claude est le maître du jeu. La conception complète est dans `CLAUDE.md`.

État actuel : **étape 1, noyau en ligne de commande**. Une boucle dans le terminal charge une fiche d'univers, appelle l'API Claude avec le prompt de base et affiche le récit. L'objectif est de juger le ton et la qualité narrative.

## Installation

Python 3.11 ou plus récent.

```bash
python -m venv .venv
```

```bash
.venv/bin/pip install -e '.[dev]'
```

```bash
cp .env.example .env
```

Dans `.env`, renseigner `ANTHROPIC_API_KEY` et `MJ_MODEL`. `MJ_EFFORT` est facultatif. Les variables déjà exportées dans le terminal ont priorité sur `.env`.

## Jouer

```bash
.venv/bin/python -m mj logres --nom Yvain
```

Options : `--difficulte facile|normal|brutal|kenshi` (normal par défaut). Sans `--nom`, le nom est demandé au lancement.

Dans la partie :

- écrire son action librement, ou taper `1`, `2` ou `3` pour un des choix proposés ;
- `/jet <stat> <difficulté>` lance le dé quand le MJ demande un jet (par exemple `/jet ruse 12` ou `/jet ruse moyen`) ;
- `/renvoyer` renvoie le dernier message si l'appel à l'API a échoué ;
- `/aide`, `/quitter`.

Chaque partie est transcrite dans `saves/cli/` (dossier non commité) pour pouvoir la relire.

## Limites de l'étape 1

- Aucun outil n'est branché. Les consignes de `prompts/etape1_sans_outils.md` demandent à Claude de proposer les 3 choix en texte, de signaler entre parenthèses les changements d'état et de s'arrêter pour demander un jet.
- Les dés sont lancés par le code, mais seulement quand le joueur tape `/jet`. Règle provisoire : réussite si total ≥ difficulté. Pas encore de critiques, de position et d'effet appliqués, ni de décalage de difficulté.
- L'état (stats, ressources) est figé aux valeurs de départ de la fiche. La difficulté n'agit que sur le ton.
- L'historique complet est renvoyé à chaque tour (avec cache de prompt). Pas encore de résumé ni de sauvegarde de partie.

## Tests

```bash
.venv/bin/pytest
```

Les tests n'appellent jamais l'API.
