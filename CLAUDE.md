# CLAUDE.md — Jeu de rôle narratif (Claude MJ)

Projet perso de Rémi : un site local où Claude joue le maître du jeu (MJ) d'un jeu de rôle narratif solo, dans l'univers choisi au lancement. Ce fichier condense le document de conception (doc privé de la conversation d'origine). En cas de doute, ce fichier fait foi ; les décisions marquées « à trancher » sont ouvertes.

## Principe directeur

Le code tient les chiffres et la mémoire ; Claude tient la plume.

- Usage : solo, en local, sans comptes, sans publication. Pas de sécurité ni de design poussés.
- Modèle : API Claude avec appel d'outils (tool use). Le modèle est configurable (variable `MJ_MODEL`), ne pas figer un identifiant dans le code.
- Clé API : variable d'environnement `ANTHROPIC_API_KEY`. Ne jamais la committer (`.env` et `saves/` dans `.gitignore`).
- Univers : au choix, un fichier YAML par univers.
- Tour de jeu : récit de 100 à 180 mots, puis 3 choix proposés ; réponse libre toujours possible.
- Les dés sont lancés par le code, jamais par Claude.
- Claude lit l'état à chaque tour et ne le modifie que par des outils.
- Stack : Python, FastAPI, page web simple. Rémi maîtrise Python et FastAPI.

## Architecture

```
Page web  <->  Serveur FastAPI  <->  API Claude
                    |
              Fichiers locaux (état JSON, fiches d'univers)
```

Boucle d'un tour :

1. Le joueur clique sur un des 3 choix ou écrit librement.
2. Le serveur assemble : prompt de base, fiche d'univers, état du jeu, résumé, fiches des PNJ présents, derniers échanges (4 à 6 tours), éventuel événement aléatoire.
3. Claude répond par du texte ou des appels d'outils.
4. Le serveur exécute chaque outil, met l'état à jour, renvoie le résultat à Claude, et recommence jusqu'à l'appel de `proposer_choix`.
5. Le serveur sauvegarde l'état et renvoie le récit avec les 3 choix à la page.
6. Tous les 10 tours, un appel séparé à Claude condense l'histoire en résumé.

Structure de projet proposée (à ajuster) :

```
src/mj/        engine.py, tools.py, state.py, memory.py, dice.py, api.py
prompts/       base.md
universes/     logres.yaml, ...
saves/         une partie = un dossier, un fichier JSON par tour (rotation)
web/           index.html, JS minimal
tests/
```

## Fiche d'univers (YAML)

Chaque univers définit ses propres stats, ressources et ambiance. Le code l'utilise pour valider les outils ; le texte narratif est injecté dans le prompt.

```yaml
id: logres
nom: Logres arthurien
ton: "Épique et mystérieux, une touche de merveilleux. Honneur, serments, magie ancienne."
de: d20
stats:            # nom: valeur de départ (modificateur ajouté au jet)
  vigueur: 2
  ruse: 1
  honneur: 3
  foi: 0
ressources:       # nom: valeurs de départ, min, max
  pv: {debut: 20, min: 0, max: 20}
  gloire: {debut: 0, min: 0, max: 100}
seuils_difficulte: {facile: 8, moyen: 12, dur: 16, heroique: 20}
lieux_cles: [Brocéliande, Camelot, Avalon, Tintagel]
factions: [Chevaliers de la Table ronde, Saxons, Fées, Église]
regles_speciales:
  - "La magie a toujours un prix."
  - "Un serment brisé coûte de l'honneur."
intro: "Jeune écuyer, tu portes une lettre de Merlin…"
```

Champs ajoutés par les principes de narration : `fronts` (2 à 3 menaces liées qui avancent), `secrets` (une dizaine, une phrase chacun, indépendants du lieu), `lieux` (nom évocateur + 3 traits), `horloges` de départ, `table_evenements` (mots d'inspiration propres à l'univers), `faits_reels` (si l'univers inclut des éléments réels : faits courts + URL des sources).

Un univers de SF aurait d'autres stats (`pilotage`, `piratage`, `sang-froid`) et d'autres ressources (`oxygène`, `carburant`). Rien d'autre ne change dans le code.

Règles de validation côté code :

1. Un outil qui cite une stat ou une ressource absente de la fiche est refusé avec une erreur lisible (`is_error`) que Claude reçoit et corrige.
2. Les ressources restent bornées entre `min` et `max`.
3. Un jet n'accepte que des difficultés entre 5 et 25.
4. Les enums de stats et de ressources des schémas d'outils sont générés à partir de la fiche d'univers au moment d'appeler l'API.

## Création d'un univers

Si l'univers n'existe pas encore, la partie commence par une phase de création menée par Claude, avant toute scène.

1. Le joueur décrit son envie en une ou deux phrases (genre, époque, ton, inspirations) et indique si l'univers s'appuie sur des éléments réels (lieux, époque, événements, organisations, personnes).
2. Si oui : recherche préalable (ci-dessous).
3. Claude rédige la fiche complète (ton, règles du monde, lieux clés, factions, tensions, stats, ressources, seuils, règles spéciales, fronts, une dizaine de secrets, lieux à trois traits, horloges de départ, table d'événements, introduction) via l'outil `creer_univers`, validé contre le schéma.
4. Le joueur relit et demande des changements ; Claude révise jusqu'à validation. La fiche est enregistrée dans `universes/`.

Un univers déjà enregistré saute cette phase.

Recherche préalable (éléments réels) :

- Déclenchement : dès que l'univers cite un lieu, une époque, un événement, une organisation ou une personne qui existent ou ont existé.
- Moyen : outil de recherche web de l'API Claude, activé uniquement pendant cette phase. **Prérequis : il doit être disponible et activé sur la clé utilisée.**
- Démarche : plusieurs recherches par thème (géographie et lieux, histoire et chronologie, société et usages, vocabulaire, figures marquantes), puis tri des faits utiles au jeu.
- Résultat : section `faits_reels` dans la fiche, faits courts avec sources (URL), séparée de la fiction inventée.
- Règle de jeu : les faits réels font foi. Quand le dossier ne couvre pas un point, Claude invente de façon plausible et le marque comme fiction dans le journal.
- Phase plus lente et plus chère qu'un tour normal, faite une seule fois par univers.

## Création du personnage

Au début de chaque partie, après le choix de l'univers, de la difficulté et du mode de mort (définitive ou avec reprise) : court dialogue avec Claude, puis fiche validée par le joueur, puis première scène.

1. Concept : nom, origine, métier ou passé, deux ou trois traits. Le joueur peut demander à Claude de proposer trois personnages.
2. Stats : répartition de points ou tirage selon l'univers, bornes de la fiche d'univers.
3. Équipement de départ : déterminé par le passé et la difficulté.
4. Liens : Claude crée un ou deux PNJ liés au passé (contact, rival, dette) avec `nouveau_pnj`.
5. Validation par le joueur, puis le code enregistre l'état initial.

`creer_personnage(nom, histoire, traits, stats, inventaire)` est vérifié par le code (total de points conforme à la difficulté, stats existantes, équipement cohérent).

| Niveau | Personnage de départ |
| --- | --- |
| Facile | Points généreux, équipement correct, un atout de départ |
| Normal | Points standards, équipement simple |
| Brutal | Peu de points, équipement léger |
| Kenshi | Points minimaux, équipement misérable, aucun atout, aucun destin |

## État du jeu

Un fichier JSON par partie, sauvegardé à chaque tour, avec rotation sur les 10 derniers tours. En mode de mort avec reprise, le joueur peut revenir 1, 3 ou 5 tours en arrière.

```json
{
  "partie_id": "2026-11-19-logres-01",
  "univers": "logres",
  "difficulte": "normal", "mort": "definitive",
  "tour": 12,
  "personnage": {
    "nom": "Rémi",
    "stats": {"vigueur": 2, "ruse": 1, "honneur": 3, "foi": 0},
    "ressources": {"pv": 17, "gloire": 4},
    "inventaire": ["épée simple", "lettre scellée de Merlin"]
  },
  "lieu": "Auberge du Cerf",
  "horloges": [{"id": "h1", "nom": "La garnison arrive", "segments": 6, "rempli": 2}],
  "secrets": [{"id": "s1", "texte": "...", "revele": false}],
  "chaos": 3,
  "quetes": [
    {"id": "q1", "titre": "Livrer la lettre de Merlin", "statut": "en_cours", "notes": ""}
  ],
  "journal": [
    {"id": "f12", "tour": 12, "lieu": "Auberge du Cerf", "fait": "...", "temoins": ["aubergiste"]}
  ],
  "pnj": {
    "aubergiste": {"attitude": -2, "sait": ["f12"], "croit": [], "ressent": "méfiance"}
  },
  "resume": "Texte condensé de l'histoire jusqu'au tour 10.",
  "derniers_echanges": []
}
```

- `journal` et `pnj` forment la mémoire. Seul le journal est la vérité du monde.
- `resume` est régénéré tous les 10 tours par un appel séparé. Le journal brut reste sur disque mais n'est plus renvoyé en entier.
- `derniers_echanges` garde les 4 à 6 derniers tours en texte complet.
- Chaque partie = un fichier, ce qui permet de reprendre ou d'en lancer plusieurs.

## Outils de Claude (14)

Chaque outil est une fonction Python qui valide l'appel, modifie l'état et renvoie un résultat court. Un appel invalide renvoie une erreur lisible ; Claude corrige dans la boucle. `proposer_choix` est obligatoire en fin de tour (sinon le code relance Claude une fois).

| Outil | Paramètres | Effet côté code |
| --- | --- | --- |
| `jet` | stat, difficulte, position, effet, raison | Lance le dé, ajoute la stat, applique le décalage de difficulté du niveau, renvoie dé, total et degré (échec critique, échec, réussite, réussite critique) |
| `modifier_ressource` | nom, delta, raison | Applique le delta en respectant min et max, renvoie la nouvelle valeur |
| `inventaire` | action (ajouter, retirer), objet | Met à jour la liste ; refuse de retirer un objet absent |
| `deplacer` | lieu | Change le lieu courant |
| `quete` | id, statut, titre, note | Ouvre, avance ou clôt une quête |
| `journal_fait` | fait, lieu, temoins | Ajoute au journal factuel ; copie l'id du fait dans le `sait` de chaque témoin |
| `memoire_pnj` | nom, type (sait, croit, ressent, attitude), contenu | Écrit dans la fiche subjective du PNJ |
| `propager` | fait_id, de, vers, deformation | Un PNJ raconte un fait à un autre, éventuellement déformé (alimente `croit`) |
| `nouveau_pnj` | nom, role, personnalite, but | Crée une fiche PNJ avec un but stable |
| `proposer_choix` | choix (liste de 3) | Termine le tour ; alimente les boutons du site |
| `creer_univers` | fiche (objet complet) | Valide la fiche contre le schéma et l'enregistre après accord du joueur |
| `creer_personnage` | nom, histoire, traits, stats, inventaire | Vérifie les points selon la difficulté et fixe l'état initial |
| `horloge` | id, action (creer, avancer, reculer, clore), delta, raison | Gère les horloges de menace et d'effort ; borne le remplissage, signale quand une horloge se remplit |
| `reveler_secret` | id, comment | Marque un secret comme révélé et l'ajoute au journal factuel |

Exemple de définition (`jet`), au format de l'API Claude :

```json
{
  "name": "jet",
  "description": "Résout une action incertaine du joueur. Appeler AVANT de raconter le résultat.",
  "input_schema": {
    "type": "object",
    "properties": {
      "stat": {"type": "string", "description": "Une stat de l'univers courant"},
      "difficulte": {"type": "integer", "minimum": 5, "maximum": 25},
      "position": {"enum": ["maitrisee", "risquee", "desesperee"]},
      "effet": {"enum": ["limite", "standard", "important"]},
      "raison": {"type": "string", "description": "Ce que le joueur tente"}
    },
    "required": ["stat", "difficulte", "position", "effet", "raison"]
  }
}
```

Dans le tour de boucle, un bloc `tool_use` doit toujours recevoir son `tool_result` ; les résultats d'outils restent courts, le détail vit dans l'état.

## Mémoire : monde objectif et PNJ subjectifs

Deux historiques coexistent : le journal factuel (ce qui s'est réellement passé) et la fiche de chaque PNJ (ce qu'il sait, croit et ressent). L'écart produit malentendus et rumeurs.

Entrée de journal (écrite par Claude via `journal_fait`, `temoins` fixe qui est au courant) :

```json
{"id": "f12", "tour": 12, "lieu": "Auberge du Cerf", "fait": "Le joueur a pris la lettre du forgeron", "temoins": ["aubergiste", "forgeron"]}
```

Fiche subjective d'un PNJ :

```json
{
  "nom": "aubergiste",
  "role": "tenancier de l'Auberge du Cerf",
  "but": "protéger son auberge et ses clients",
  "attitude": -2,
  "sait": ["f12"],
  "croit": ["le joueur est un espion du roi"],
  "ressent": "méfiance, surveille ses clients"
}
```

- `sait` : ids de faits que le PNJ a vus ou appris (ajout automatique pour les témoins).
- `croit` : opinions et rumeurs, vraies ou fausses. Elles persistent jusqu'à ce qu'un fait les corrige.
- `ressent` et `attitude` : état émotionnel et note de -5 à +5 envers le joueur.
- `but` : motivation stable, ne change que par un fait marquant.
- `propager` copie un fait d'un PNJ vers un autre, avec une déformation optionnelle ; le récepteur reçoit une version altérée dans `croit`, pas l'id du fait vrai dans `sait`.

Ce qui part vers Claude à chaque tour : le résumé global (factuel), les 4 à 6 derniers échanges, et uniquement les fiches des PNJ présents dans la scène ou nommés par le joueur (leurs faits de `sait` dépliés en phrases). Condensation tous les 10 tours : résumé du journal en 150 mots max qui remplace `resume` ; les fiches PNJ ne sont jamais résumées.

## Difficulté

Quatre niveaux, choisis au lancement. Le décalage est appliqué par le **code** dans `jet` (Claude propose une difficulté de 5 à 25, le code l'ajuste).

| Niveau | Effet sur les jets | Ton des conséquences |
| --- | --- | --- |
| Facile | -3 sur les difficultés demandées | Blessures légères, aides fréquentes |
| Normal | Inchangées | Conséquences réelles, rien de définitif sans avertissement |
| Brutal | +3 sur les difficultés demandées | Ressources rares, erreurs payantes, mort possible |
| Kenshi | +6 ; stats de départ réduites (valeurs à ajuster) | Monde indifférent et injuste, blessures durables, mort possible sans avertissement |

Règles d'équité (niveaux Facile, Normal, Brutal) :

1. Toute menace mortelle est annoncée par un indice avant de frapper.
2. Un échec change la situation (perte, alerte, complication) ; il ne bloque jamais l'histoire.
3. Le joueur peut toujours tenter une approche originale, qui peut remplacer un jet si elle est ingénieuse.
4. La mort n'est possible que si les PV tombent à 0 après au moins un avertissement ; elle est racontée, puis, selon le mode de mort choisi au début, la partie se termine ou propose de recharger la dernière sauvegarde.

Niveau Kenshi : le joueur n'a rien d'un héros (pas de destin, pas de statut, pas de mentor providentiel). Le monde est brutal, indifférent et souvent injuste, et il continue sans lui.

- Départ : stats parmi les plus basses de l'univers, équipement misérable, aucune relation utile.
- Menaces : certaines hors de portée et pas toujours annoncées ; fuir, contourner ou abandonner est souvent la bonne décision.
- Séquelles : les blessures durent (membre perdu, boiterie, cicatrices) et pèsent sur les jets suivants.
- Mort : possible à tout moment, sans avertissement garanti. Le mode (définitive, ou avec reprise de la dernière sauvegarde) est choisi au début de la partie.
- Progression : lente, par la pratique ; survie, argent et ressources comptent autant que le combat.
- PNJ : indifférents, intéressés ou hostiles par défaut ; personne n'aide le joueur sans contrepartie.
- Brutal ne veut pas dire arbitraire : les dés restent honnêtes et le monde reste cohérent. L'injustice vient de l'indifférence du monde, pas d'un MJ qui triche.

Ajustement dynamique (v2, optionnel) : le code compte les échecs et réussites récents et ajoute une ligne à l'état envoyé à Claude (« 3 échecs consécutifs : ouvre une opportunité », « 5 réussites consécutives : monte les enjeux »). Les dés ne sont jamais truqués.

## Principes de narration et d'aventure

| Principe | Idée | Application |
| --- | --- | --- |
| Jouer pour découvrir (Dungeon World) | Pas d'intrigue écrite d'avance | Claude improvise à partir de l'état, des fronts et des horloges |
| Penser dangereux et hors champ (Dungeon World) | Le monde change sans le joueur, plutôt en pire | 2 à 3 fronts par univers qui avancent même quand le joueur fait autre chose |
| Horloges (Blades in the Dark) | Jauges à segments pour un danger qui approche ou un effort en cours | Outil `horloge` ; état des horloges envoyé à chaque tour |
| Position et effet (Blades in the Dark) | Danger et ampleur du résultat sont deux réglages indépendants | `jet` reçoit position (maîtrisée, risquée, désespérée) et effet (limité, standard, important) |
| Mouvements doux puis durs (Dungeon World) | Un signe de menace avant le coup, ou le coup tout de suite | Facile/Normal/Brutal : signe avant coup. Kenshi : le coup peut tomber d'emblée |
| Échec qui fait avancer (The Alexandrian, Pathfinder) | Un échec crée un obstacle ou une conséquence et ouvre une autre voie | Jamais de « rien ne se passe » ; à Kenshi la conséquence peut être lourde |
| Début en pleine action, secrets, lieux (Sly Flourish) | Ouvrir au milieu de l'action ; une dizaine de secrets d'une phrase ; lieux à nom évocateur et trois traits | Première scène en pleine action ; `secrets` et `lieux` dans la fiche |
| Règle des trois indices, scènes en nœuds (The Alexandrian) | Chaque conclusion repose sur trois indices ; le joueur choisit l'ordre | Toujours au moins 3 pistes ouvertes ; les 3 choix en sont tirés ; `reveler_secret` |
| Limites plus intéressantes que pouvoirs (Sanderson) | Pouvoirs compréhensibles, limités, coûteux ; développer l'existant avant d'ajouter | Chaque pouvoir a un coût et une limite ; pas de pouvoir inventé pour sortir d'une impasse |
| Hasard organisé (Mythic GME) | Événements aléatoires, tables de mots, facteur de chaos de 1 à 9 | Le code tire parfois un événement (focus + mots de `table_evenements`) et l'injecte dans le prompt |

Changements dans le jeu : le chaos monte quand le joueur enchaîne les succès et baisse quand il enchaîne les échecs ; chaque tour, un petit tirage selon le chaos peut ajouter un événement aléatoire au prompt.

Pièges connus des MJ pilotés par un modèle, et réponses :

- Dérive des règles et de l'état : fonctions pour les jets et pour l'état (c'est l'architecture ci-dessus).
- Blocage en attente d'un jet : l'outil `jet` règle le problème.
- Trop de nouveautés d'un coup : un seul nouvel élément important par tour.
- Complaisance : ce qui n'est pas dans l'état n'existe pas ; le joueur décrit ses actions, pas leurs résultats.
- Répétitions de ton et de vocabulaire : risque à surveiller aux premiers essais ; l'événement aléatoire et la consigne de variété y remédient en partie, à vérifier en jeu.
- MJ adversaire : même au niveau Kenshi, le MJ est arbitre du monde, pas adversaire du joueur.

Sources (pages ouvertes) : [Dungeon World, chapitre du MJ](https://roll20.net/compendium/dw/Rules:The%20GM) · [Blades in the Dark, position et effet](https://roll20.net/compendium/BITD/Rules:Setting%20Position%20and%20Effect) · [Sly Flourish, Lazy GM's Resource Document](https://slyflourish.com/lazy_gm_resource_document.html) · [The Alexandrian, conception par nœuds](https://thealexandrian.net/creations/misc/node-design/node-design2.html) · [étude arXiv, MJ IA avec appels de fonctions](https://arxiv.org/html/2409.06949v1).
Lues par extraits seulement : [Dungeon World, Fronts](https://roll20.net/compendium/dw/Rules:Fronts) · [horloges de Blades in the Dark](https://www.indiegamereadingclub.com/indie-game-reading-club/clocks-forged-in-the-darks-underappreciated-killer-app) · [The Alexandrian, Failure for the Beginning GM](https://thealexandrian.net/wordpress/46186/roleplaying-games/failure-for-the-beginning-gm) · [Pathfinder GM Core, Failing Forward](https://2e.aonprd.com/Rules.aspx?ID=817) · [Mythic GME](https://wordmillgames.com/mythic-gme.html) · [lois de Sanderson](https://faq.brandonsanderson.com/knowledge-base/what-are-sandersons-laws-of-magic/) · [CEUR-WS, conformité narrative des LLM](https://ceur-ws.org/Vol-4097/paper7.pdf).

## Prompt système de base

Commun à tous les univers (`prompts/base.md`). Le code y ajoute à chaque tour : fiche d'univers, état du jeu, résumé, fiches des PNJ présents, derniers échanges, éventuel événement aléatoire.

```text
Tu es le Maître du Jeu d'un jeu de rôle narratif solo. Le joueur incarne un seul personnage ; tu incarnes le monde et tous les autres personnages. Tu écris en français.

RÔLE
- Décris les scènes, joue les PNJ, fais vivre les conséquences.
- Ne décide jamais des actions, paroles ou pensées du joueur.
- Reste dans l'univers fourni. Les remarques hors-jeu vont entre parenthèses.

COHÉRENCE
- L'ÉTAT DU JEU, le RÉSUMÉ et les FICHES PNJ fournis font foi. Ne les contredis jamais.
- Un PNJ n'agit et ne parle qu'à partir de sa fiche. Il ne connaît jamais ce qu'il n'a pas vu ou appris. Ses croyances peuvent être fausses.
- Tout changement d'état passe par un outil. Ne le décris jamais seulement dans le texte.
- Quand une action du joueur a une issue incertaine, appelle l'outil `jet` AVANT de raconter le résultat, puis narre en respectant le résultat obtenu.

DIFFICULTÉ
- Niveaux facile, normal, brutal : le monde est dangereux mais juste. Annonce les menaces par des indices avant qu'elles frappent.
- Niveaux facile, normal, brutal : un échec a des conséquences (blessure, perte, alerte, temps perdu), jamais une impasse ni une mort immédiate sans avertissement.
- Récompense l'ingéniosité et les bons choix plus que la force brute.
- Respecte le niveau de difficulté fourni dans l'état du jeu. Au niveau « kenshi », le joueur n'a rien d'un héros : le monde est brutal, indifférent et injuste, avec des menaces hors de portée, des blessures durables et une mort possible sans avertissement. Reste cohérent, ne triche jamais sur les jets : brutal ne veut pas dire arbitraire.

NARRATION ET AVENTURE
- Joue pour découvrir ce qui arrive : improvise à partir de la situation, des fronts et des horloges, sans suivre une intrigue écrite d'avance.
- Le monde bouge hors champ : fais avancer les horloges et les fronts même quand le joueur fait autre chose.
- Chaque scène contient un enjeu, un obstacle ou un choix. Évite les scènes sans tension.
- Garde au moins trois pistes ouvertes (lieux, personnes, secrets) pour que le joueur choisisse sa direction. Révèle les secrets par indices, jamais d'un bloc, et appelle `reveler_secret`.
- Pour chaque jet, fixe la position (maîtrisée, risquée, désespérée) selon le danger et l'effet (limité, standard, important) selon ce que l'action peut accomplir.
- Un échec change la situation ou coûte quelque chose ; il n'y a jamais de « rien ne se passe ».
- La magie et la technologie suivent les règles et limites de la fiche d'univers. Ne résous jamais un problème par un pouvoir non établi.
- Un seul nouvel élément important par tour. Fais avancer ce qui est ouvert avant d'en ouvrir un autre.
- Si un ÉVÉNEMENT ALÉATOIRE est fourni, intègre-le de façon plausible au lieu de l'ignorer.
- Ce qui n'est pas dans l'état n'existe pas. Le joueur décrit ses actions, pas leurs résultats ni des faits du monde.
- Varie le vocabulaire, le rythme et l'ouverture des scènes ; ne répète pas les tournures des tours précédents.
- Donne un nom et un désir à chaque personnage rencontré.
- Tu es l'arbitre du monde, pas l'adversaire du joueur : même brutal, le monde reste cohérent.

FORMAT DE CHAQUE TOUR
1. Appelle les outils nécessaires (jets, changements d'état, mémoire).
2. Écris le récit : 100 à 180 mots, sensoriel, sans répéter le tour précédent.
3. Termine toujours en appelant `proposer_choix` avec 3 choix courts et variés (prudent, audacieux, original). Le joueur peut aussi répondre librement.
```

Points à surveiller au premier essai : Claude qui raconte un jet sans l'appeler, des PNJ trop bien informés, des choix qui se ressemblent.

## Plan de réalisation

On construit par couches : chaque étape donne un jeu jouable.

1. **Noyau en ligne de commande** : boucle Python qui charge une fiche d'univers, appelle l'API Claude avec le prompt de base et affiche le récit. Objectif : valider le ton et la qualité narrative.
2. **Outils et état** : `jet`, `modifier_ressource`, `inventaire`, `proposer_choix`, avec sauvegarde JSON. Objectif : vérifier que Claude appelle bien les outils.
3. **Mémoire** : journal factuel, fiches PNJ, `journal_fait`, `memoire_pnj`, `propager`, résumé tous les 10 tours.
4. **Site FastAPI** : endpoint de tour, page web avec zone de récit, boutons de choix, saisie libre et panneau d'état.
5. **Univers et réglages** : phases de création d'univers (avec recherche web) et de personnage, un deuxième univers, sélecteur de difficulté dont le niveau Kenshi, reprise de partie.
6. **Finitions** : ajustement dynamique, export d'une partie en texte, éventuel mode vocal ou illustrations.

## Décisions prises

- Choix proposés à chaque tour (3) avec réponse libre possible.
- Récit de 100 à 180 mots par tour.
- Jets résolus par le code via l'outil `jet` (aller-retour avec Claude à chaque jet).
- Stats et ressources variables, définies par chaque univers.
- Deux mémoires : journal factuel et fiches subjectives des PNJ.
- Claude via l'API ; univers au choix ; site perso en local.
- Création d'univers rédigée par Claude, avec recherche web préalable si des éléments réels sont inclus (recherche web : prérequis).
- Création du personnage au début de chaque partie.
- Niveau Kenshi : monde brutal et injuste, personnage quelconque, mort possible sans avertissement.
- Mode de mort (définitive ou avec reprise) choisi au début de la partie.
- Sauvegarde à chaque tour, rotation sur les 10 derniers tours.

## Questions ouvertes (à trancher en cours de route)

- [ ] Streaming du récit mot à mot dans le site, ou affichage une fois le tour terminé ?
- [ ] Quel modèle Claude par défaut (qualité narrative contre coût par tour) ?
- [ ] Gestion des combats : simple suite de jets, ou règles dédiées ?
- [ ] Fréquence des événements aléatoires et réglage du facteur de chaos (à tester en jeu).
- [ ] Valeurs exactes des décalages de difficulté et des stats de départ Kenshi.

## Consignes de travail pour Claude Code

- Suivre l'ordre du plan. Commencer par l'étape 1 et faire jouer une partie réelle avant d'ajouter des couches.
- Garder le moteur (dés, validation, état) testable sans appeler l'API : tests unitaires pour les jets, les bornes des ressources, la validation contre la fiche d'univers et la rotation des sauvegardes.
- Ne jamais laisser Claude lancer les dés ni modifier l'état hors outils.
- Prompt, fiches d'univers et schémas d'outils vivent dans des fichiers (pas dans le code) pour pouvoir les itérer.
- Avant d'ajouter une dépendance ou de trancher une question ouverte, demander à Rémi.
- Ne pas committer `.env`, clés, ni le dossier `saves/`.
