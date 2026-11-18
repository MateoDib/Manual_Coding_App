# Guide de codage — Manual Coding App

L’application distingue les concepts scientifiques, leurs occurrences dans chaque DAG, l’origine des copies et les citations propres à chaque réponse. Le dépôt public contient le code ; chaque équipe ajoute ses interviews dans sa copie locale.

## Configurer et lancer

1. Sur un nouveau Mac, lancer `Installer.command` (Python 3.11–3.13). Node.js n’est pas nécessaire : l’éditeur est déjà construit.
2. Double-cliquer sur **Configurer.command**. Une fenêtre locale s’ouvre dans le navigateur : renseigner la liste des codeurs, le codeur par défaut, puis glisser le CSV dans la zone prévue ou cliquer sur **Ajouter la base plus tard**. Le fichier n’est envoyé à aucun serveur externe par cet import. Le nom de destination est toujours `interviews.csv`.
3. L’assistance IA est facultative. Le champ de clé est masqué. Choisir de garder la clé existante, d’en saisir une pour cette application, ou d’utiliser uniquement celle de l’environnement du Mac. Aucune clé n’est copiée automatiquement depuis l’environnement. Aucune requête API n’est effectuée pendant la configuration.
4. Cliquer sur **Enregistrer la configuration**, puis ouvrir **Lancer_Codage.command** ou **Lancer_Harmonisation.command**. Les ports par défaut sont 8541 et 8542 ; ils peuvent être changés dans les réglages avancés.
5. Pour les analyses, ouvrir **Lancer_Statistiques.command** à la racine de l’application. Installer au besoin leurs dépendances avec `Descriptives_Statistics/Installer.command`.

Configurer.command fonctionne aussi avant l’installation des dépendances, avec la bibliothèque standard de Python. Tous les lanceurs et les analyses lisent la même configuration privée **.env**. Les modifications prennent effet au prochain lancement ; arrêter une application ouverte dans son Terminal avec **Ctrl+C**, puis la relancer. Fermer uniquement l’onglet du navigateur ne ferme pas son serveur.

Le bouton × ferme l’assistant sans enregistrer les changements non validés. Après « Ajouter la base plus tard », le dossier est créé ; placer ensuite le CSV au chemin indiqué ou revenir dans l’assistant. Les CSV doivent être en UTF-8, séparés par des virgules, avec `PID`, `pair_id_interview`, `pair_order_interview`, `question`, `response`, et éventuellement `interview_id`. Aucune phase n’est utilisée. L’import vérifie les colonnes, les doublons et l’ordre des paires ; un fichier incompatible avec les textes déjà liés aux codages est refusé. Les fichiers sources sélectionnés restent intacts : l’assistant en enregistre une copie.

MacTeX/BasicTeX avec TikZ et `standalone` permet de compiler les aperçus PDF. Le code LaTeX reste exportable sans compilation.

## Organisation autonome du dossier

```text
Manual_Coding_App/
├── Configurer.command
├── Lancer_Codage.command
├── Lancer_Harmonisation.command
├── Lancer_Statistiques.command
├── .env.example                           # modèle public commenté
├── .env                                   # réglages privés, exclu de Git
├── data/interviews/interviews.csv         # source privée
├── outputs/
│   ├── database/visual_coding.sqlite3      # seule base de référence
│   ├── coding/<codeur>/coding.xlsx        # export à la demande
│   └── analyses_dags/<codeur>/
│       ├── report.html
│       └── descriptives.xlsx
├── Descriptives_Statistics/                # codes d’analyse
├── apps/                                  # codage et stockage
├── frontend/                              # source de l’éditeur
└── scripts/                               # configuration et lanceurs
```

La base SQLite commune sépare les codeurs et conserve toutes les révisions. Elle évite les divergences entre plusieurs bases par auteur. Les sous-dossiers `coding` et `analyses_dags` sont créés automatiquement pour chaque codeur, ainsi que pour `Harmonized`. Les exports restent dérivés de SQLite : ils ne la remplacent pas. Aucun classeur ni rapport vide n’est créé à l’installation.

Le bouton **Exporter le codage dans mon dossier** enregistre `outputs/coding/<codeur>/coding.xlsx` : questions, réponses, notation textuelle et tables scientifiques. Le classeur contient des onglets pour les occurrences, qualifications, groupes et relations. Les textes trop longs pour une cellule sont conservés dans l’onglet `long_text`, sans troncature. Les coordonnées exactes et les versions complètes restent dans SQLite. Les téléchargements complémentaires restent disponibles.

Les descriptifs produisent seulement `report.html` et `descriptives.xlsx` dans `outputs/analyses_dags/<codeur>/`. Le classeur inclut l’évolution individuelle ; aucun troisième fichier n’est créé pour dupliquer ces résultats.

Pour publier le code, exclure **.env**, **data/**, **outputs/** et les environnements **.venv/** : les règles `.gitignore` sont fournies. Ne pas partager une archive du dossier complet sans retirer la clé privée et les données qui ne doivent pas être transmises. Le modèle public `.env.example` contient des commentaires et aucune clé. Le .env est lu comme des valeurs ; aucune de ses lignes n’est exécutée comme une commande.

Modifier un nom d’auteur ne renomme pas ses codages antérieurs. Réutiliser exactement le même nom pour les retrouver. Pour une autre étude ou une répartition différente des paires, utiliser une copie vierge du dossier de code, sans `data/`, `outputs/` ni `.env`, puis la configurer.

## Coder simplement

Pour sélectionner plusieurs blocs, maintenir le clic gauche sur le fond et tracer un rectangle. Maj + clic ajoute ou retire un bloc de la sélection. Déplacer le cadre de sélection déplace ses blocs ensemble ; les tracés internes suivent le groupe et les liens vers les blocs extérieurs se réajustent. Les positions verrouillées restent fixes. Espace + glisser, ou le bouton central de la souris, déplace la vue ; aucun déplacement de bloc ne recentre ni ne change le zoom.

Les menus sont masqués dès que le clic est maintenu sur un bloc ou une sélection, puis réapparaissent au relâchement. « Insérer une citation » reste replié jusqu’à son ouverture. Les questions et réponses sont sélectionnables et copiables, sans être modifiables ; les raccourcis Copier/Coller du texte restent indépendants de ceux du graphe.

⌘/Ctrl C copie les blocs sélectionnés et leurs liens internes ; ⌘/Ctrl V les colle au centre de la vue, sans changer le cadrage. Le presse-papiers du graphe reste disponible pendant la session, y compris après navigation vers une autre réponse du même codeur. Les groupes sélectionnés emportent leurs membres pour ne pas créer une coexistence incomplète ; sélectionner tous les membres emporte aussi leur jonction. Une copie depuis une réponse antérieure du même entretien conserve ses origines ; ailleurs, elle constitue de nouvelles occurrences sans inventer de filiation entre participants. Les citations ne sont pas attribuées automatiquement à la réponse d’arrivée. Un collage ou une duplication est annulable en une opération.

Double-cliquer sur la toile pour créer un bloc ; cliquer ailleurs valide son texte ou supprime un bloc vide. Tirer depuis un carré crée une connexion ou le bloc suivant. Les suggestions réutilisent les topics, sous-thèmes et portées déjà codés. Les guides d’alignement ne nécessitent aucune licence Pro. Les graphes restent en noir et blanc.

Les rectangles représentent les topics ; les parenthèses et crochets qualifient le topic. Les liens sont typés : causalité, définition, coexistence, addition, priorité ou appartenance à un groupe. Un trait simple doit être qualifié avant validation scientifique. Les sources `|` sont des annotations rattachées à un objet ou à un DAG ; elles ne relient pas artificiellement deux DAGs.

Une flèche peut aboutir à un topic individuel ou à la relation « & », « + », « = », « > » ou « < » entière. Ainsi A→B et C→D, avec B & D, conserve deux causes individuelles ; A→& signifie une cause de la coexistence conjointe. Ces relations sont enregistrées et comptées séparément, sans développer une cause de la relation en causes de chacun de ses membres. Sélectionner deux topics et cliquer sur un de ces symboles crée une unité de relation explicite. Pour relier une flèche à un ancien symbole porté par un trait, la déposer sur le symbole : celui-ci devient une unité connectée à ses deux membres. Le bouton « Relier à la relation » propose la même conversion. « Ajouter un membre » choisit les traits d’appartenance sans pointe ; le mode → conserve les flèches causales vers la relation.

« = » et la priorité « > / < » relient exactement deux éléments ; « & » et « + » peuvent en réunir davantage. Les réglages de la priorité permettent de choisir l’élément prioritaire. Ce choix reste attaché au sujet, même après copie ou déplacement : le symbole « > / < » s’adapte à l’ordre spatial des deux membres dans l’éditeur et dans TikZ. Un symbole créé seul reste un brouillon jusqu’à ce que ses membres et, pour la priorité, l’élément prioritaire soient renseignés. Les figures existantes restent lisibles sans conversion automatique.

Les composantes non reliées sont automatiquement des DAGs distincts. La reprise conserve des filiations explicites, même lors de fusions et scissions. La disposition ne détermine jamais la nouveauté scientifique.

- **Reprendre le DAG précédent** copie tous les DAGs de la dernière paire précédente contenant une figure ; le survol précise laquelle.
- **Reprendre un autre DAG** ouvre les paires antérieures du même entretien et du même codeur, avec leurs questions, réponses et miniatures cochables. Plusieurs paires peuvent être choisies. On peut remplacer la figure actuelle ou ajouter les copies.
- Le mode « renseigner l’origine » sert à une reconstruction manuelle structurellement correspondante. Il n’invente pas une copie technique.

Les graphes sources gardent leurs versions. Une reprise commence en brouillon ; la passer à **Codé** après vérification. **none** signifie aucun ajout substantiel et peut conserver une figure de référence. Une paire non codée reste distincte de none.

Les modifications sont enregistrées en continu. Toute modification de fond repasse en brouillon ; un déplacement, un libellé imprimé ou une citation seule ne le fait pas. **Enregistrer** et **Enregistrer et suivant** valident le codage après contrôle de structure. Une figure vide doit être explicitement codée none. Enregistrer et suivant termine l’édition avant de naviguer. ⌘/Ctrl Z annule, y compris une reprise ou une modification de citation. Le cadrage est conservé ; Recentrer permet de le modifier volontairement.

## Justifier un topic ou un lien

Cliquer sur un objet ouvre son menu ; déplier **Insérer une citation** affiche le champ **Citation du participant**. Coller un passage de la réponse actuelle. Le contrôle retrouve le passage exact : aucune correction approximative ou suppression de mots. Les différences de retours à la ligne Windows/Mac sont tolérées, et le texte source exact reste celui enregistré. Si le passage apparaît plusieurs fois, choisir sa position. Les offsets sont des positions en caractères Unicode, y compris en présence d’accents ou d’emoji.

Une citation exacte délibérément associée à l’objet est marquée comme appui de cet objet. Le sélecteur permet de préciser « non évoqué », « attribution à vérifier » ou « remis en cause ». Le contrôle vérifie la présence du texte, pas la pertinence scientifique de son interprétation : celle-ci reste la responsabilité du codeur.

Une citation saisie sur un topic ne justifie pas automatiquement un autre topic homonyme ou une flèche. Pour une coexistence dessinée comme un petit groupe `&`, citer le groupe pour justifier la relation commune. Les citations incomplètes restent enregistrées comme brouillons et ne comptent pas comme expressions vérifiées.

Lors d’une copie vers une autre réponse, les anciennes citations et attributions ne sont pas reportées comme de nouvelles mentions. Elles restent consultables dans la version source. Modifier le sens d’un objet remet son attribution en attente de vérification ; un déplacement ou un simple changement de libellé ne le fait pas.

## Ce qui est mesuré

Trois dimensions sont conservées séparément :

1. **Origine technique de l’occurrence** : créée ici, copiée depuis une occurrence précise, ou indéterminée lors d’un import.
2. **Comparaison scientifique** : concept/relation déjà rencontré ou nouveau dans l’entretien ; DAG identique, sous-graphe, extension, recouvrement ou comparaison indéterminée.
3. **Appui dans la réponse actuelle** : attribution et citation exacte pour l’objet précis.

Un redessin manuel d’un DAG déjà rencontré garde une origine « créée ici » mais une comparaison scientifique « identique », sans nouveaux concepts ou liens. Un A redessiné dans un autre DAG reste une nouvelle occurrence d’un concept connu ; il n’est pas assimilé à l’occurrence A copiée ailleurs.

Dans A→B puis, à la réponse suivante, A→B→C et séparément A→D, on obtient quatre concepts uniques, cinq occurrences et trois relations. Les créations scientifiques nouvelles sont C, D, B→C et A→D. Les preuves textuelles sont attachées à chaque occurrence.

« Nouveau » compare toutes les paires antérieures du même entretien et du même codeur. Une paire antérieure manquante ou en brouillon rend cette conclusion provisoire. Les niveaux de qualification restent attachés à leur topic. Un lien qualifié et son regroupement au niveau des seuls topics sont tous deux disponibles ; ils ne sont pas confondus.

Une relation causale A→B diffère de B→A. Les définitions, coexistences et additions binaires sont symétriques ; une priorité conserve son dominant. Un groupe isolé à deux membres, sans autre implication, est normalisé pour l’analyse comme sa relation binaire équivalente. Les figures originales et leurs objets restent enregistrés. Un groupe portant une conséquence, plusieurs membres ou une annotation spécifique reste explicite : A,B→groupe→C ne fabrique jamais A→C ou B→C.

L’absence d’un élément dans la nouvelle figure n’est pas un retrait de croyance. Les retraits d’une reprise sont listés séparément avec un motif : correction du codage, retrait explicite ou hors du raisonnement actuel. Les citations de remise en cause permettent de documenter le discours. Les comparaisons exactes ignorent les coordonnées et libellés et vérifient la structure typée ; une comparaison trop complexe reste indéterminée plutôt que déclarée identique à tort.

## Une base de référence, des vues lisibles

La V3 enregistre automatiquement uniquement **visual_coding.sqlite3**. Conserver ce fichier avec ses révisions pour reprendre le travail. Les anciennes sorties de tests V1/V2 ne sont pas chargées dans la V3. Les graphes JSON/TikZ et les classeurs/CSV sont exportés à la demande ; le classeur local est placé dans outputs/coding/<codeur>/.

Les tables primaires `documents` et `revisions` conservent les graphes et leur historique immuable. `interview_pairs` conserve la version du texte utilisée ; une modification d’une paire source existante est détectée avant reprise. `study_info` conserve le coding scheme versionné. `coding_events` indique le type d’opération associé à chaque nouvelle révision ; les déplacements ne deviennent jamais des observations supplémentaires. Les propositions IA restent dans leur journal séparé.

Les vues scientifiques principales :

| Vue | Utilité |
|---|---|
| `pair_statistics` | Comptes uniques/occurrences, nouveaux éléments, citations actuelles et état du codage |
| `dag_statistics` | Chaque DAG et sa comparaison au passé |
| `dag_derivations` | Origines déclarées et rapprochements structurels, distingués par `basis` |
| `topics` | Une ligne par occurrence de topic, avec son origine et sa citation |
| `qualifications` | Sous-thèmes et portées rattachés à l’occurrence de topic |
| `groups` | Définition exacte des groupes n-aires |
| `relations` | Une ligne par relation, avec extrémités et type explicites |
| `coding_changes` | Modifications et retraits de la reprise, avec avant/après |
| `relation_frequencies` | Poids par participant et comptes de réponses distincts |

`pair_id`, `dag_id` et `object_id` permettent les jointures. Une occurrence s’identifie dans une paire et une version ; des identifiants locaux identiques dans deux documents ne suffisent pas à établir une filiation. `source_pair`, `source_author`, `source_dag` et `source_object` documentent une copie ; sa révision exacte reste conservée. `seen_before` signifie déjà rencontré scientifiquement. `origin` décrit seulement l’opération technique. `source_change` compare l’occurrence à son origine. `expressed` exige une citation exacte attribuée à cette réponse. `terminal` marque les dernières versions validées des lignées déclarées ; un brouillon ne remplace pas le dernier état validé. Les fréquences distinguent la présence au cours de l’entretien et la présence dans ces états terminaux. `value_json` conserve les extrémités qualifiées et groupes complets pour les analyses avancées.

`coding_valid`, `history_complete` et `lineage_valid` sont séparés : un passé incomplet ne rend pas automatiquement invalide ce qui est effectivement codé dans la réponse actuelle. `analysis_current` signale si les vues matérialisées correspondent aux dernières sauvegardes ; un changement de codage invalide ce marqueur. Les calculs de l’app et du dossier de statistiques relisent toujours un instantané cohérent des révisions. Les exports Excel présentent les vues utiles et gardent les détails techniques dans SQLite/CSV.

Les codes canoniques sont les identifiants scientifiques. Les libellés imprimés sont libres. Renommer volontairement un code crée un autre concept tant qu’une correspondance scientifique explicite n’a pas été décidée ; aucune fusion approximative n’est appliquée automatiquement.

## Statistiques et publication

Le sous-dossier **Descriptives_Statistics** calcule les descriptifs par réponse, l’évolution des DAGs et les fréquences entre participants. Son README précise le périmètre et les dénominateurs. Il produit seulement un rapport HTML et un classeur, sur demande ; le code TikZ du réseau pondéré se télécharge depuis le rapport.

Les exports TikZ individuels et l’aperçu LaTeX utilisent le document enregistré, sa révision et son empreinte. Une prévisualisation antérieure est signalée ; l’export attend la sauvegarde des changements. L’harmonisation compare les structures en ignorant la disposition et garde un codeur « Harmonized » distinct.

L’IA demeure facultative, désactivée par défaut et sollicitée seulement par le bouton prévu. `HANDCODING_AI_ENABLED=1` la rend disponible avec la clé API du projet déjà configurée. Les identifiants de participants et métadonnées de traçage ne sont pas transmis au modèle. Les propositions refusées ne sont pas des observations ; une proposition appliquée conserve son audit et nécessite la même vérification du codage et des citations.

## Organisation du code

`graph_tracking.py` gère les copies et occurrences ; `graph_evidence.py` vérifie les citations ; `graph_comparison.py` compare les graphes typés ; `graph_metrics.py` calcule les tables ; `scientific_schema.py` définit les vues lisibles ; `graph_store.py` assure sauvegarde, révisions, textes sources et calculs transactionnels. L’éditeur est dans `frontend/src/` et son build livré dans `apps/visual_component/build/`.

Pour reconstruire après modification : `npm ci`, puis `npm run build`, dans `frontend/`. Les deux fichiers de dépendances npm sont nécessaires à cette reconstruction. Aucun manifeste de livraison n’est créé. Les contrôles utilisent des données fictives hors du dossier livré ; les fichiers et dossiers temporaires de test sont supprimés après vérification.

Les réglages communs sont gérés par `scripts/app_config.py` ; `scripts/configure.py` et `scripts/setup_ui/` forment l’assistant local.

### Outils de reconstruction de l’éditeur

Au 18 novembre 2026, les dépendances de développement épinglées signalent [GHSA-fc5q-39xc-vjpf](https://github.com/advisories/GHSA-fc5q-39xc-vjpf) sur `picomatch` 4.0.7, utilisé par Vite pour les motifs de fichiers. L’avis ne référence pas de version corrigée. Cette dépendance n’est pas embarquée dans le navigateur du codeur et n’est pas exécutée par Streamlit, qui sert l’éditeur déjà construit. Réévaluer cet avis lors d’une mise à jour des outils de construction ; aucun remplacement forcé ni correctif non vérifié n’a été appliqué.
