# Descriptives_Statistics — codages V3

Ce dossier produit les statistiques essentielles une fois les interviews codées. Il lit un instantané de la base V3 **en lecture seule**. Il ne modifie ni les interviews ni les codages et ne sollicite aucune API.

## Lancer

Configurer l’application avec **Configurer.command**, puis ouvrir **Lancer_Statistiques.command** à sa racine. Le codeur sélectionné par défaut et les emplacements proviennent du même `.env` que le codage et l’harmonisation. Installer au besoin les dépendances en ouvrant `Installer.command` dans ce sous-dossier.

```text
Manual_Coding_App/
├── .env
├── outputs/database/visual_coding.sqlite3
├── outputs/analyses_dags/<codeur>/
│   ├── report.html
│   └── descriptives.xlsx
└── Descriptives_Statistics/compute.py
```

Le rapport HTML est autonome et s’ouvre dans un navigateur. Le classeur contient le protocole, le périmètre des participants, les comptes par paire, les DAGs, les fréquences des topics, les groupes, les relations, les motifs et le cumul individuel de topics. **Ces deux fichiers sont les seules sorties automatiques d’un lancement** ; ils sont actualisés aux lancements suivants. Le code TikZ du réseau pondéré peut être téléchargé depuis le rapport.

Commandes personnalisées, depuis la racine de l’application :

```bash
python -B scripts/statistics.py
python -B scripts/statistics.py --author Harmonized
python -B scripts/statistics.py --author Mateo --min-participants 2
```

`--author` choisit un codeur déclaré dans la configuration ou Harmonized ; aucune donnée de deux codeurs n’est mélangée. `--db` et `--output` choisissent d’autres emplacements explicites pour les vérifications. Python 3.11–3.13 est requis. Le code réutilise le noyau scientifique de `apps/` pour éviter deux définitions divergentes des statistiques. Les sorties contiennent des données de recherche et restent exclues de Git.

## Périmètre scientifique par défaut

Le dénominateur comprend les participants dont toutes les paires sont à l’état **Codé** ou **none**, sans erreur de structure et avec les filiations résolues. Les autres apparaissent dans `cohort` avec leur motif d’exclusion. Une paire manquante ou brouillon n’est jamais interprétée comme l’absence d’un topic.

`--include-partial` permet une exploration des entretiens incomplets en retenant seulement leurs paires valides et en indiquant ce choix dans le protocole. Le rapport ne présente pas des fréquences de 0 % lorsque le dénominateur est nul.

Le regroupement par défaut est **qualified** : les sous-thèmes et portées des extrémités sont conservés. `--level topic` ignore explicitement ces qualifications pour une vue plus globale ; ce choix figure dans le protocole. Une comparaison entre deux regroupements demande deux dossiers de sortie distincts pour conserver les deux rapports.

## Mesures retenues

- **Par paire** : concepts uniques, occurrences de concepts, qualifications, relations et nouveaux éléments dans l’entretien ; expressions étayées par une citation actuelle.
- **Évolution individuelle** : cumul de topics distincts présents dans les DAGs validés, plus la comparaison des DAGs aux paires précédentes. Les copies et redessins n’ajoutent pas artificiellement un nouveau concept.
- **Entre participants** : topics, relations et motifs présents dans au moins un DAG validé. Chaque participant pèse une fois par élément ou motif, même s’il en conserve dix copies.

Pour les relations :

| Variable | Sens |
|---|---|
| `n_participants` | Participants distincts portant cette relation dans le périmètre retenu |
| `n_final_participants` | Participants conservant ce lien dans une version terminale validée, après les reprises déclarées |
| `denominator` | Participants inclus dans ce même périmètre |
| `frequency` | `n_participants / denominator` |
| `n_expressed_pairs` | Paires où la relation est attribuée à la réponse avec une citation exacte |
| `n_snapshot_pairs` | Paires dont la figure validée contient cette relation, y compris les reprises |

Une citation sur A ne justifie pas automatiquement A→B. Copier une figure ne crée pas une nouvelle expression dans la réponse suivante. Les fréquences de présence d’une relation et les fréquences d’expression documentée restent donc séparées. Les états antérieurs explicitement codés restent présents dans les statistiques historiques même s’ils sont retirés ensuite ; la vue `coding_changes` de la base et les dernières versions des DAGs permettent d’étudier ces retraits séparément.

Les comptes de nouveauté sont calculés sur tout le codage antérieur du même entretien et du même auteur. Une histoire incomplète est signalée par `history_complete`. L’ordre des réponses et l’historique d’édition du codeur sont deux dimensions distinctes.

## Réseau généralisé et motifs

Le réseau présente un seul lien par relation sémantique, avec une largeur proportionnelle à son support par participant et le pourcentage indiqué. Il ne duplique pas artificiellement les mêmes B et C pour dessiner deux chemins.

Exemple : une personne code A→B→C et une autre B→C. Le réseau indique **A→B : 50 %**, **B→C : 100 %**. Le tableau des motifs indique **A→B→C : 50 %**. Ainsi, la vue synthétique et la récurrence du chemin complet restent toutes deux disponibles.

Les motifs retenus pour cette première version sont les chemins causaux de **deux liens**. Ils sont cherchés au niveau des occurrences, dans un même DAG validé. A→B dans un DAG et B→C dans un autre ne créent pas un motif ; deux occurrences différentes de B ne sont pas raccordées par leur seul code. `n_dag_versions` mesure les versions où le motif est présent ; le poids principal demeure le participant distinct. `n_expressed_pairs` exige l’appui actuel des deux relations.

Les unités de relation `&`, `+`, `=` et de priorité `> / <` portant une cause ou une conséquence gardent leur identité conjointe. Les appartenances restent des traits sans pointe ; elles ne deviennent pas des causes individuelles ni des étapes artificielles des motifs causaux. Le classeur conserve leurs membres et, dans la colonne `dominant`, le sujet prioritaire. Le réseau généralisé nomme ce sujet pour que la priorité reste lisible indépendamment de la disposition de ses membres. Une unité isolée à deux membres est traitée comme sa relation binaire équivalente, selon les mêmes règles que l’application.

Pour la lisibilité, la figure montre au plus les 40 relations principales, complétées par les appartenances nécessaires pour garder les groupes explicites. Le classeur conserve toutes les relations. `--min-participants` filtre les relations principales. Un cycle dans le réseau agrégé est signalé et conservé : aucun lien n’est supprimé pour imposer un DAG.

Ces statistiques décrivent le raisonnement codé. Elles ne démontrent pas une causalité réelle et ne corrigent pas automatiquement les différences d’exposition aux questions, de longueur d’entretien ou de précision du discours. Les pourcentages doivent être interprétés avec le périmètre, le protocole et les données sources.

## Reproductibilité

Le classeur et le rapport indiquent le codeur, le coding scheme, l’empreinte des révisions analysées, les options, le dénominateur et les versions des bibliothèques. Une seule lecture cohérente de la base alimente les deux sorties. Le premier onglet du classeur contient ces paramètres ; aucun manifeste séparé n’est écrit.

Les données exportées restent privées et doivent être partagées selon le protocole de l’étude. Le dossier de code peut être publié sans `outputs/`, sans base et sans environnement `.venv`.
