# Samsung Health Cloud CLI — lecture seule

Client local privé pour consulter et analyser les données Samsung Health de Charles. Le produit opérationnel est autonome : il utilise le catalogue persistant et le miroir SQLite, sans APK, décompilation ni dépôt de recherche.

> L’API Samsung Cloud utilisée n’est pas publique et peut évoluer sans préavis.

## Architecture technique

Le binaire `samsung-health` assemble six couches :

1. `auth.py` échange transitoirement l’état maître Samsung Find contre un jeton Samsung Health ;
2. `scsp.py` enregistre l’identité locale SCSP si nécessaire et obtient l’autorisation Cloud ;
3. `data.py` réalise exclusivement les lectures distantes des documents ;
4. `sync.py` synchronise chaque manifest indépendamment dans le miroir ;
5. `cache.py` stocke les données et enveloppes complètes dans SQLite ;
6. `analytics.py`, `analysis_engine.py` et `semantics.py` produisent les vues consolidées, statistiques, validations et provenances.

`cli.py` orchestre ces couches. Les commandes `schema`, `inventory`, `types`, `cache-status` et toute commande portant `--no-sync` lisent uniquement les fichiers locaux. Les autres commandes initialisent la session si nécessaire, synchronisent leur périmètre, puis lisent le miroir.

Le catalogue des manifests et le miroir sont des dépendances opérationnelles persistantes. L’APK, les sources JADX et les rapports de recherche ne sont jamais requis à l’exécution : ils servent uniquement à établir certaines entrées du registre sémantique livré dans le code.

## Interface analytique

`analyze` est la commande quotidienne principale. Elle actualise silencieusement les types nécessaires, effectue les jointures et retourne des données accompagnées de leur provenance et de la formule de chaque dérivation.

```bash
samsung-health analyze sleep --latest
samsung-health analyze activity --period week --compare previous
samsung-health analyze exercise --all-history
samsung-health analyze weight --latest
samsung-health analyze stress --period month
samsung-health analyze blood_pressure --since 2026-01-01 --until 2026-06-30
```

Compatibilité des sélecteurs :

| Analyse | Sélecteurs acceptés |
|---|---|
| `sleep` | `--latest` ou aucun sélecteur ; les intervalles et comparaisons sont refusés |
| `activity` | `--period`, `--since/--until`, `--all-history`, `--compare previous` ; jamais `--latest` |
| `exercise` | mêmes intervalles et comparaison qu’`activity` ; jamais `--latest` |
| autre type | `--latest` **ou** un intervalle ; `--compare` est refusé |

Sans sélecteur d’intervalle, la période par défaut est la semaine civile courante en `Europe/Paris`. `--latest`, `--period`, `--since/--until` et `--all-history` sont mutuellement exclusifs lorsque leur combinaison serait ambiguë. Une borne `since` postérieure à `until` produit une erreur. `--no-sync` commute seulement la source vers le miroir local ; il ne change pas le calcul.

Analyseurs spécialisés :

- sommeil : le document source le plus récent est choisi par `end_time`, puis les stades sont filtrés par `sleep_id` lorsqu’il existe et limités à sa fenêtre. Les durées utilisent les intervalles valides ; la couverture utilise leur union, tandis que les chevauchements et valeurs invalides sont comptés. Les blocs `AWAKE`/REM sont des suites contiguës de codes officiels. Fréquence cardiaque, SpO₂ et ronflement ne sont joints que par chevauchement temporel (`time_window_only`). L’efficacité rapportée reste directe ; la baseline prend au plus sept **source records** antérieurs et ses moyennes sont arithmétiques ;
- activité : seuls les enregistrements Samsung `source_type == -2` (total toutes sources dédupliqué) servent aux totaux. Pour chaque jour, la ligne au plus grand `update_time` est retenue ; aucune valeur n’est inventée en son absence. Une comparaison soustrait la période immédiatement précédente de même largeur ;
- exercice : les événements sont comptés, les durées/distances/calories sont sommées avec conversions explicites, et la fréquence cardiaque moyenne est pondérée par la durée. Les extrema proviennent des champs source numériques.

Les vues historiques ont des fenêtres propres : les pas et la fréquence cardiaque utilisent le jour civil `Europe/Paris`; le sommeil d’une date interroge de midi la veille à 18 h le jour demandé, fusionne les intervalles et moyenne uniquement les champs `efficiency` numériques ; le poids choisit la mesure au plus grand `start_time`, puis `create_time` en fallback.

Tous les types, y compris les analyseurs spécialisés, exposent chaque champ observé sous `field_analysis`. Un champ documenté porte sa sémantique, son unité, sa source et éventuellement une validation de plage/enum. Un champ sans preuve conserve son nom brut et reçoit uniquement des statistiques neutres : présence, type, nombre, somme, moyennes, écarts types, minimum, maximum et dernière valeur pour les nombres ; comptages pour les autres formes. Aucune agrégation n’est choisie à partir du seul nom du champ.

Hiérarchie de preuve : documentation officielle Samsung, puis projets open source comme corroboration, puis APK distribué par Galaxy Store et décompilé. L’identité Samsung du certificat embarqué a été inspectée, sans vérification indépendante complète de confiance. Les sorties distinguent `official_documentation`, `official_schema_convention` (nom commun documenté, héritage du manifest privé non publié), `open_source`, `apk_decompiled` et `raw_observed`.

Une absence de violation ne concerne que les valeurs couvertes par une règle encodée. Le rapport publie séparément les champs avec règle applicable, les champs documentés sans règle encodée, les valeurs vérifiées et les valeurs non vérifiées ; il ne prétend jamais valider tout le compte.

## Miroir universel

Le miroir conserve les documents complets des 182 types du catalogue sans réduire leur schéma.

```bash
samsung-health types oxygen
samsung-health inventory
samsung-health inventory exercise
samsung-health schema
samsung-health schema sleep
samsung-health data oxygen_saturation --since 2026-08-01
samsung-health data exercise --envelope --limit 20
samsung-health cache-status
```

- `data` actualise le type ciblé avant lecture.
- `--no-sync` impose une lecture locale immédiate.
- `--envelope` inclut `data`, `files`, `downloadUrls`, `needToDecrypt` et les clés inconnues.
- La pagination locale utilise `--limit` et `--offset`.
- `schema` prouve la couverture globale des couples manifest/champ ; `schema TYPE` retourne les statistiques, la provenance et les validations de toutes les valeurs locales du type.

La méthodologie, les sources et les limites de preuve sont détaillées dans [`docs/semantic-methodology.md`](docs/semantic-methodology.md).

## Référence complète des commandes

### Session et diagnostic

```bash
samsung-health init
samsung-health status
samsung-health doctor
```

- `init` crée ou renouvelle les autorisations Health et SCSP nécessaires.
- `status` n’affiche que la présence et les échéances des éléments d’état, jamais leur valeur.
- `doctor` vérifie les fichiers requis, le catalogue, le miroir et l’espace disque sans lire ni afficher de secret.
- Les chemins peuvent être remplacés globalement avec `--master-state`, `--state`, `--catalog` et `--cache`.

### Catalogue et lecture distante bas niveau

```bash
samsung-health manifests list [--filter texte]
samsung-health manifests show MANIFEST_ID
samsung-health read MANIFEST_ID [--limit N|--all] [--page-size N] [--format json|jsonl|pretty] [--e2ee-state disabled|enabled|none]
samsung-health documents MANIFEST_ID --schema-revision N [--limit N] [--page-token TOKEN]
```

`read` parcourt directement les pages Cloud, applique localement `--since/--until` et émet des documents complets. `--e2ee-state` transmet explicitement le filtre Cloud `disabled`, `enabled` ou `none`; il ne déchiffre aucune donnée. `documents` est une interface de compatibilité pour lire une seule page avec une révision de schéma explicite. Ces commandes n’écrivent jamais dans Samsung Health.

### Exports privés reprenables

```bash
samsung-health export MANIFEST_ID [--output fichier.jsonl] [--page-size N] [--since ISO] [--until ISO] [--e2ee-state disabled|enabled|none]
samsung-health export-all [--output-dir DOSSIER] [--page-size N] [--since ISO] [--until ISO] [--e2ee-state disabled|enabled|none] [--stop-on-error]
```

Chaque export est verrouillé par `flock`, écrit par pages privées `0600`, et accompagné d’un checkpoint `state.json`. Le checkpoint lie manifest, révision, version, filtres, taille de page et état E2EE. Chaque page possède une empreinte SHA-256 ; une relance reprend au `nextPageToken`, vérifie les pages déjà écrites puis assemble atomiquement le JSONL final. `export-all` isole les erreurs par manifest et maintient un `index.json`, sauf avec `--stop-on-error`.

### Interfaces locales universelles

- `types [filtre]` recherche le catalogue et affiche l’état local de chaque manifest.
- `inventory [TYPE]` rapporte les volumes, bornes, champs observés, E2EE, fichiers et URL annexes.
- `schema` calcule la couverture structurelle globale sans charger toutes les valeurs.
- `schema TYPE` analyse tout l’historique local du type ; son coût mémoire est linéaire avec le nombre de documents et de champs.
- `data TYPE` synchronise le type puis lit le miroir ; `--no-sync` évite toute initialisation réseau.
- `cache-status` résume les révisions, fraîcheurs, indisponibilités HTTP 404 et erreurs normalisées.

Le contrat `data` est stable dans les deux modes :

```json
{"manifest_id":"…","offset":0,"count":100,"next_offset":100,"records":[]}
```

`next_offset` vaut `null` lorsque la page est terminale. `--limit` accepte 1 à 10 000, `--offset` doit être positif ou nul, et l’ordre local est décroissant par début pour les enveloppes paginées.

## Migration 0.6.0

La 0.6.0 retire volontairement plusieurs clés dont le nom affirmait davantage que les données :

| Ancienne sortie | Nouvelle sortie / comportement |
|---|---|
| `sleep.sessions` | `sleep.source_records` ou `merged_sleep_intervals` selon la vue |
| `awakenings` | `awake_periods_detected`, explicitement non équivalent aux réveils conscients |
| `efficiency_percent` recalculé | `reported_efficiency_percent` direct + `derived_stage_coverage_percent` séparé |
| `baseline_previous_nights` | `baseline_previous_source_records` |
| `heart_rate.average_bpm` dans la vue journalière | `arithmetic_mean_bpm` |
| `metrics` / `distributions` de l’analyse générique | `fields.<champ>.statistics` et provenance champ par champ |
| maximum téléphone/montre utilisé comme pas quotidiens | aucune valeur si le total Samsung `source_type == -2` manque |
| interprétation de `low_duration`, minimum SpO₂ ou durée de ronflement sans unité prouvée | champ brut conservé dans `field_analysis` |

Les analyseurs spécialisés ajoutent `calculations`, `field_analysis` et `coverage`. Les intégrations qui consomment le JSON doivent donc migrer explicitement plutôt que conserver des alias trompeurs.

Formes minimales :

```json
{"analysis":"sleep","reported_efficiency_percent":null,"awake_periods_detected":0,"calculations":{},"field_analysis":{},"coverage":{"coverage_percent":100.0}}
{"analysis":"activity","steps":0,"days_without_authoritative_all_sources":1,"calculations":{},"field_analysis":{}}
{"date":"YYYY-MM-DD","samples":0,"arithmetic_mean_bpm":null,"minimum_bpm":null,"maximum_bpm":null}
```

Les vues historiques simplifiées restent disponibles :

```bash
samsung-health summary [YYYY-MM-DD]
samsung-health steps [YYYY-MM-DD]
samsung-health sleep [YYYY-MM-DD]
samsung-health heart-rate [YYYY-MM-DD]
samsung-health weight
```

## Synchronisation et miroir SQLite

```bash
samsung-health sync --all-types --days 14 --force
samsung-health sync --all-types --all-history --force
```

### Algorithme de synchronisation

- Sans `--all-types`, `sync` cible les manifests usuels ; `--all-types` parcourt les 182 entrées du catalogue.
- La fenêtre récente vaut 14 jours par défaut. `--all-history` supprime la borne de début.
- Un manifest est sauté si sa révision, son absence d’erreur et sa fraîcheur satisfont le délai demandé, sauf `--force`.
- Les documents sont lus par pages Cloud de 1 000 puis upsertés par lots de 1 000.
- Chaque manifest est isolé : son échec n’interrompt pas les suivants.
- Un HTTP 404 devient `unavailable: HTTP 404`, distinct d’une défaillance technique.
- Les erreurs persistées sont normalisées et ne contiennent ni URL, réponse, en-tête ni jeton.
- Une réconciliation intégrale mémorise tous les identifiants vus puis supprime localement les anciens documents absents du serveur. Une synchronisation partielle ne supprime rien.
- L’API privée peut ignorer ses bornes temporelles ; le client filtre également les résultats localement.

Le rafraîchissement universel quotidien et la réconciliation hebdomadaire sont assurés par l’automatisation de l’hôte, en dehors du paquet Python. Le CLI ne crée lui-même aucun timer.

### Schéma et transactions du miroir

SQLite fonctionne en mode WAL avec `synchronous=NORMAL`. Deux tables sont maintenues :

- `documents` : clé primaire `(manifest_id, document_id)`, temps normalisés pour les index, `data_json` complet, `envelope_json` complet, indicateurs E2EE/fichiers/URL ;
- `sync_state` : révision du schéma, dernière synchronisation, nombre de documents et erreur normalisée par manifest.

L’identifiant local reprend successivement `datauuid`, `uuid` ou `id`; en leur absence, il devient le SHA-256 canonique du JSON `data`. L’upsert remplace atomiquement l’enregistrement du même couple manifest/identifiant sans réduire son schéma. Les lectures temporelles sélectionnent les documents dont l’intervalle chevauche la requête (`end_time >= since` et `start_time <= until`).

Le dossier du miroir est forcé à `0700`; la base et ses sidecars WAL/SHM sont forcés à `0600`.

## Installation, packaging et tests

Prérequis : Python 3.12 ou supérieur. La seule dépendance d’exécution déclarée est `httpx>=0.28,<0.29`; `pytest` appartient au groupe de développement.

```bash
cd /home/hermes/projects/samsung-health-research/client
/home/hermes/.hermes/bin/uv sync
/home/hermes/.hermes/bin/uv run pytest -q
/home/hermes/.hermes/bin/uv build
/home/hermes/.hermes/bin/uv tool install --editable --force .
samsung-health --version
samsung-health doctor
samsung-health schema
```

Hatchling construit un wheel contenant uniquement `src/samsung_health_cloud` et un sdist à liste blanche contenant `src`, `tests`, `docs`, `README.md`, `pyproject.toml` et `uv.lock`. Les deux points d’entrée `samsung-health` et `samsung-health-cloud` appellent le même `cli.main`.

La vérification de livraison attend successivement : suite complète verte, build réussi, inspection des archives pour exclure état/cache/inventaire de compte, installation, `doctor`, couverture `schema` avec `ignored_fields == 0`, puis smoke tests des commandes historiques et analytiques. Une installation éditable pointe directement vers l’arbre source courant ; un déploiement reproductible peut installer le wheel construit.

Le projet source contient uniquement :

- `src/samsung_health_cloud/` ;
- `tests/` ;
- `docs/` ;
- `pyproject.toml` ;
- `uv.lock` ;
- ce README.

Les environnements virtuels, distributions, caches de tests et artefacts de recherche ne sont pas versionnés ni conservés dans le projet.

## Données privées

- catalogue : `~/.config/samsung-health-cloud/manifests.json` ;
- état Health : `~/.config/samsung-health-cloud/state.json` ;
- état Samsung partagé : `~/.config/samsung-find/state.json` ;
- miroir : `~/.local/share/samsung-health/health.sqlite3`.

Les dossiers privés sont en `0700` et les fichiers d’état/données en `0600`. SQLite ne contient aucun jeton d’authentification.

## Cycle d’authentification et état

L’état maître Samsung Find est lu transitoirement pour récupérer les éléments nécessaires à l’échange Health ; son jeton maître n’est jamais copié dans le miroir. Sous un verrou interprocessus :

1. un CDID aléatoire est créé s’il manque ;
2. le jeton Health est réémis s’il manque, expire dans moins de 60 secondes ou n’a pas d’identifiant utilisateur ;
3. l’identité SCSP est enregistrée une seule fois si `registration_id` manque ;
4. l’autorisation Cloud est réémise si elle expire dans moins de 60 secondes ;
5. chaque étape réussie est sauvegardée avant la suivante afin de permettre une reprise après échec.

L’état est écrit atomiquement via fichier temporaire, `fsync` et `os.replace`, sous permissions `0600`; les symlinks, propriétaires inattendus et permissions trop larges sont refusés. Les `repr` des objets d’authentification masquent jetons, login, user ID, CDID et registration ID.

## Limite de lecture seule

Les données de santé sont obtenues uniquement par `GET /data/v3/{manifest}/documents`. Le module `data.py` ne doit jamais implémenter POST, PUT, PATCH, DELETE, upsert ou désenregistrement. Les appels d’écriture réseau restants servent exclusivement à l’authentification et à l’établissement de la session SCSP, jamais à modifier les données Samsung Health.

Ne jamais afficher les jetons, cookies, en-têtes d’autorisation ou fichiers d’état privés.

Les exceptions HTTP sont transformées en erreurs génériques sans URL, corps ni en-tête. Les erreurs CLI attendues renvoient le code `2` et un message `error:` sans traceback. Les sorties analytiques masquent toutes les chaînes inconnues ainsi que les champs identifiants, commentaires, packages, appareils, coordonnées, emplacements, URL et chemins, indépendamment de leur type Python.

## Limites connues

- L’API Cloud est privée et son comportement peut changer sans version publique.
- `schema TYPE` charge actuellement l’historique du type en mémoire avant de calculer ses statistiques ; préférer `schema` sans argument pour le contrôle global léger.
- Les manifests E2EE, fichiers et URL annexes sont conservés et inventoriés mais ne sont pas interprétés automatiquement.
- Une couverture de 100 % signifie que tous les champs observés sont représentés, pas qu’ils possèdent tous une signification publique.
- Le registre APK provient d’un artefact livré par Galaxy Store dont le certificat embarqué a été inspecté sans vérification indépendante complète ; 333 erreurs JADX restent explicitement exclues des preuves.
