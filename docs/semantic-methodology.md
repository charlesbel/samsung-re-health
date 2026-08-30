# Méthodologie sémantique Samsung Health

## Objectif

Le client doit couvrir **chaque couple manifest/champ réellement observé dans le miroir du compte**, sans transformer un nom plausible en fait médical ou en unité inventée.

La garantie d’exhaustivité est structurelle :

1. chaque champ observé est présent dans `fields` / `field_analysis` ;
2. chaque champ possède exactement un statut de provenance ;
3. `ignored_fields` reste vide et `coverage_percent` vaut 100 % ;
4. si aucune sémantique n’est prouvée, le nom brut est conservé et seules des statistiques mathématiques neutres sont calculées.

Cette garantie ne prétend pas que Samsung publie la signification de tous ses champs internes. Elle garantit au contraire que les inconnues restent explicitement inconnues.

## Hiérarchie de preuve

### 1. Documentation officielle Samsung

Sources principales :

- [Common fields](https://developer.samsung.com/health/android/data/api-reference/com/samsung/android/sdk/healthdata/HealthConstants.Common.html)
- [SessionMeasurement](https://developer.samsung.com/health/android/data/api-reference/com/samsung/android/sdk/healthdata/HealthConstants.SessionMeasurement.html)
- [Sleep](https://developer.samsung.com/health/android/data/api-reference/com/samsung/android/sdk/healthdata/HealthConstants.Sleep.html)
- [SleepStage](https://developer.samsung.com/health/android/data/api-reference/com/samsung/android/sdk/healthdata/HealthConstants.SleepStage.html)
- [HeartRate](https://developer.samsung.com/health/android/data/api-reference/com/samsung/android/sdk/healthdata/HealthConstants.HeartRate.html)
- [OxygenSaturation](https://developer.samsung.com/health/android/data/api-reference/com/samsung/android/sdk/healthdata/HealthConstants.OxygenSaturation.html)
- [Exercise](https://developer.samsung.com/health/android/data/api-reference/com/samsung/android/sdk/healthdata/HealthConstants.Exercise.html)
- [StepDailyTrend](https://developer.samsung.com/health/android/data/api-reference/com/samsung/android/sdk/healthdata/HealthConstants.StepDailyTrend.html)
- [Weight](https://developer.samsung.com/health/android/data/api-reference/com/samsung/android/sdk/healthdata/HealthConstants.Weight.html)
- [Valeurs numériques officielles des constantes](https://developer.samsung.com/health/android/data/api-reference/constant-values.html)

L’ancien SDK est déprécié, mais ses pages restent la source publique officielle correspondant aux manifests historiques `com.samsung.health.*` et `com.samsung.shealth.*`. La documentation actuelle du Samsung Health Data SDK est utilisée comme corroboration lorsque la correspondance de génération de schéma est démontrable ; elle n’autorise pas à renommer arbitrairement un ancien champ.

Un couple manifest/champ explicitement décrit reçoit `official_documentation`. Les noms Common/Session retrouvés dans un manifest Cloud privé dont l’héritage n’est pas publié reçoivent le statut plus prudent `official_schema_convention` : Samsung documente le nom et sa convention, mais pas l’implémentation formelle de ce manifest privé.

### 2. Projets open source

Ils servent uniquement de seconde source et ne priment jamais sur Samsung :

- [`joaoruimatos/samsung-health-to-garmin`](https://github.com/joaoruimatos/samsung-health-to-garmin) et son amont [`PhilippImhof/FromSamToGarm`](https://github.com/PhilippImhof/FromSamToGarm) : unités et structure des anciens exports d’exercices ;
- [`Devasy/samsung-health-sdk`](https://github.com/Devasy/samsung-health-sdk) : en-têtes d’exports, timestamps, fichiers de détail et segments de sommeil ;
- [`lionheart/health-csv-importer-samsung`](https://github.com/lionheart/health-csv-importer-samsung) : corroboration secondaire des stades de sommeil.

Les heuristiques non Samsung trouvées dans certains projets — scores maison, seuils de « readiness », détection de sommeil perturbé, conversion d’unité selon la grandeur numérique — sont volontairement exclues.

### 3. APK distribué par Galaxy Store, décompilé

APK analysé :

- package : `com.sec.android.app.shealth` ;
- version : `7.00.6.003` ;
- source : endpoint de livraison Galaxy Store Samsung ;
- appareil cible : `SM-S928B`, SDK 35 ;
- SHA-256 : `a778cb804a4c0ad03d540d027fb3d473d2b54451468fb03f32f6c457831e3554` ;
- certificat embarqué : sujet/émetteur Samsung Corporation, inspecté sans prétendre à une vérification cryptographique complète ni à une comparaison d’empreinte avec une version de confiance ;
- JADX : 1.5.6, huit DEX traités séparément en mode `simple`.

Artefacts locaux :

- paquet source : `com.sec.android.app.shealth` ;
- version : `7.00.6.003` ;
- décompilateur : JADX 1.5.6 (analyses statiques isolées).

JADX a signalé 333 erreurs de méthodes sur l’ensemble très obfusqué. Une constante ou une chaîne n’est donc pas suffisante à elle seule pour inventer une unité. Le registre n’accepte une sémantique APK que lorsqu’un chemin de lecture/calcul clair existe. Exemples acceptés :

- `SleepItem.getActualSleepTime()` utilise `efficiency / 100`, ce qui confirme que `efficiency` est un pourcentage ;
- `SleepItem.getSleepDuration()` multiplie le facteur `sleep_duration` par `60000`, ce qui confirme les minutes pour ce champ ;
- `ScoreFactors.toString()` nomme explicitement les facteurs de score du sommeil, sans établir pour autant une unité pour chacun.

## Corrections sommeil

- Un document `sleep` est appelé **source record**, pas « session de sommeil » tant que son rôle d’agrégat ou de fragment n’est pas prouvé.
- Le code officiel `AWAKE` inclut des éveils brefs **et des périodes agitées**. Une transition vers ce code est donc rapportée comme `awake_periods_detected`, jamais comme nombre de réveils conscients.
- `reported_efficiency_percent` est la valeur directement stockée par Samsung et confirmée comme pourcentage dans l’APK.
- `derived_stage_coverage_percent` est un calcul local sur l’union des intervalles valides, limités à la fenêtre du source record ; il ne peut pas dépasser 100 % et n’est pas présenté comme l’efficacité Samsung. Les valeurs de stade invalides, intervalles invalides et chevauchements sont comptés séparément.
- La comparaison historique est libellée `baseline_previous_source_records`, jamais « sept nuits », car plusieurs documents peuvent appartenir à une même nuit.
- Les mesures de fréquence cardiaque, SpO₂ et ronflement sont qualifiées de **temporellement concomitantes** (`join_kind=time_window_only`) ; aucun lien physiologique ou identifiant parent n’est inventé.

## Activité et déduplication

`StepDailyTrend.source_type == -2` est le total Samsung toutes sources dédupliqué. Seul ce record est agrégé. Si une journée n’en possède pas, elle est comptée dans `days_without_authoritative_all_sources` et aucun maximum arbitraire téléphone/montre n’est utilisé comme total.

## Statistiques neutres

Pour un champ non documenté :

- nombres : présence, somme, moyenne arithmétique, écart type population, écart type échantillon, minimum, maximum, dernière valeur observée ;
- booléens : vrais/faux ;
- textes : nombre et cardinalité, valeurs toujours masquées tant qu’un enum n’est pas explicitement documenté ;
- objets/listes : nombre, clés ou nombre d’éléments ;
- valeurs nulles/absentes : comptages séparés.

Ces statistiques décrivent les données ; elles ne donnent aucune unité, aucun seuil clinique et aucune signification métier.

## Validation sur le compte

`schema` inventorie tous les couples manifest/champ présents dans le miroir. `schema TYPE` charge les données locales du type et applique :

- validation d’enum lorsque Samsung publie les valeurs ;
- validation de plage lorsque Samsung publie une plage ;
- longueur maximale lorsque Samsung la publie ;
- relation `end_time >= start_time` uniquement pour les manifests dont les deux champs de session sont explicitement documentés ;
- contrôle de présence/type et statistiques neutres pour le reste.

Les sorties séparent `fields_with_applicable_rule`, `fields_without_encoded_rule`, `checked_values`, `unchecked_values` et `violation_count`. « 0 violation » signifie donc uniquement zéro violation dans le sous-ensemble réellement vérifié, jamais validation exhaustive du compte. Les rapports d’audit globaux ne révèlent aucune valeur de santé.
