# Plan de transition vers le modele clinique longitudinal

**Statut :** proposition progressive, soumise aux arbitrages du document 06  
**Date :** 20 aout 2026  
**Principe :** aucune reecriture massive ; chaque phase doit conserver les fonctions validees et disposer de tests de non-regression

## 1. Point de depart protege

Le socle suivant est considere comme fonctionnel et ne doit pas etre remplace pendant la premiere phase :

- OCR `gpt-5.6-sol` avec pretraitement et controle de date ;
- extraction clinique V2 avec `gpt-5.6-terra` ;
- JSON de seance V2 ;
- synthese longitudinale V1.1 ;
- preparation de prochaine seance V1.0 ;
- empreintes SHA-256 et anti-doublon ;
- traitement multi-patients en fin de lot ;
- controles deterministes et comptabilisation des jetons ;
- separation documente / synthese prudente / suggestion IA.

Le premier travail d'implementation devra commencer par un commit propre de cet etat et une execution de la suite de tests existante. Les dossiers documentaires non suivis ne doivent pas etre ajoutes avec une commande globale.

## 2. Principes de migration

1. Ajouter des objets d'autorite avant de demander aux vues de les consommer.
2. Ne jamais convertir silencieusement une sortie LLM en decision clinique persistante.
3. Conserver les JSON V2 comme sources de seance pendant toute la transition.
4. Introduire la provenance minimale avant les rapprochements longitudinaux.
5. Faire coexister ancien et nouveau calcul assez longtemps pour comparer leurs sorties.
6. Conserver un repli explicite plutot que masquer une couverture incomplete.
7. Tester d'abord avec des cas JSON fictifs ; aucune nouvelle note manuscrite n'est necessaire.
8. Ne pas commencer la conceptualisation avant de pouvoir identifier durablement problemes et objectifs.

## 3. Phases d'implementation

### Phase 0 - Figer et documenter le socle actuel

**But :** disposer d'une base reproductible avant d'ajouter le registre.

Travaux :

- verifier l'etat Git et committer uniquement le code valide ;
- executer `python -m unittest discover -s App -p "test_*.py"` ;
- conserver les exemples JSON fictifs actuels comme fixtures de reference anonymisees ou recreees dans les tests ;
- documenter les versions des schemas et generateurs actuels ;
- verifier que le second lancement ne consomme aucun jeton.

Critere de sortie : pipeline actuel reproductible, tests verts, aucune donnee clinique ajoutee au depot par erreur.

### Phase 1 - Definir les contrats de donnees du registre, sans generation LLM

**But :** traduire le document 06 en modeles valides, sans encore modifier le pipeline principal.

Travaux :

- creer des modeles separes de `main.py` si la structure du depot le permet, par exemple un module clinique longitudinal ;
- definir les enveloppes communes : assertion statut epistemique, reference source, revision, relation et etat documentaire ;
- definir `probleme_suivi`, `objectif_therapeutique`, `tache_intersession` et `element_a_reprendre` ;
- definir une structure separee `proposition_mise_a_jour` ;
- utiliser des identifiants opaques stables et des versions croissantes ;
- interdire par validation les combinaisons incoherentes, notamment tache `non_realisee` sans source explicite et proposition systeme dans un registre valide.

Tests deterministes :

- identifiants stables apres reformulation ;
- revision sans perte de l'ancienne version ;
- non-mention sans changement d'etat ;
- reactivation historisee ;
- remplacement avec lien vers l'ancien objet ;
- statut epistemique distinct du statut d'action ;
- pointeur source inexistant refuse ;
- contradiction conservee.

Critere de sortie : schemas autonomes et testes, sans appel API et sans branchement dans `main.py`.

### Phase 2 - Construire le catalogue de provenance V1 depuis les JSON existants

**But :** rendre les donnees actuelles referencables sans changer immediatement le schema d'extraction clinique.

Travaux :

- calculer pour chaque fichier V2 un identifiant de document et son empreinte ;
- enumerer les elements par categorie et pointeur JSON ;
- calculer l'empreinte canonique de chaque element ;
- verifier patient, date, schema et existence du pointeur ;
- conserver une date de coupure et la version d'extraction ;
- refuser une provenance qui ne peut plus retrouver sa version source ;
- definir la politique d'archivage ou de correction d'un JSON deja reference.

La V1 ne modifie pas encore les JSON de seance. Un futur schema V2.1 pourra ajouter des identifiants d'elements natifs si l'experience montre que le catalogue derive est trop fragile.

Tests deterministes :

- meme fichier et meme contenu donnent les memes references ;
- changement de fichier invalide la reference de version, sans reecrire l'ancienne ;
- date ou patient divergent refuse ;
- categorie et index hors limites refuses ;
- aucune affirmation de provenance photographique fine.

Critere de sortie : chaque assertion candidate peut remonter a un element JSON exact et a une version de fichier.

### Phase 3 - Generer des propositions de registre, sans modifier le registre valide

**But :** exploiter Terra pour reduire la charge de revue tout en preservant l'autorite clinique.

Travaux :

- donner au generateur les nouvelles seances, le registre valide courant et les references sources ;
- demander uniquement des operations proposees : creer, relier, reformuler, changer d'etat, remplacer ou ne rien faire ;
- exiger une justification source pour chaque operation ;
- imposer `proposition_systeme` et `brouillon_genere` ;
- calculer une empreinte incluant sources, registre de depart, schema, generateur, modele et prompt ;
- ne generer aucune proposition si aucune source nouvelle ou version de generateur n'a change ;
- comptabiliser les jetons avant les controles deterministes ;
- refuser une proposition qui invente une source, ferme un objet par non-mention ou convertit une tache en objectif.

Cas fictifs prioritaires :

1. tache convenue puis resultat non mentionne ;
2. probleme ancien non mentionne ensuite ;
3. nouvelle difficulte explicite ;
4. information incertaine ;
5. aucune mise a jour justifiee ;
6. donnees contradictoires ;
7. consigne proposee sans accord ;
8. objectif absent des sources ;
9. point explicitement differe ;
10. reformulation d'un meme probleme sans creation de doublon.

Critere de sortie : propositions auditables et conservatrices, registre valide inchange avant et apres generation.

### Phase 4 - Introduire une validation clinique minimale

**But :** permettre la promotion controlee des propositions sans attendre une interface complete.

Travaux :

- fournir une vue de revue montrant operation, difference, source et limite ;
- permettre accepter, corriger ou rejeter ;
- exiger l'identite du validateur, la date et le motif pour toute transition sensible ;
- ecrire une revision immuable dans le registre seulement apres validation ;
- conserver la proposition et la decision de revue pour audit ;
- interdire l'edition directe d'un instantane de preparation comme moyen de mise a jour.

Une interface en ligne de commande ou un petit outil local peut suffire pour la V1. La conception doit toutefois rester compatible avec une future interface graphique.

Critere de sortie : creation et mise a jour reelles des quatre registres possibles sans intervention manuelle dans le JSON brut.

### Phase 5 - Initialiser prudemment les dossiers fictifs existants

**But :** tester la migration sur l'historique actuel sans produire de fausse completude.

Travaux :

- generer des candidats de problemes et de taches depuis les JSON existants ;
- ne migrer aucun `point_a_reprendre` genere par l'ancienne synthese comme fait ;
- laisser les objectifs valides vides tant qu'aucune source ou validation ne les etablit ;
- afficher les lacunes de couverture ;
- faire valider un petit ensemble d'objets fictifs ;
- verifier les identifiants, relations, versions et sources.

Critere de sortie : au moins un dossier fictif possede un registre coherent, non duplique et explicitement incomplet lorsque les donnees manquent.

### Phase 6 - Brancher la synthese longitudinale en lecture hybride

**But :** reduire progressivement les reconstructions independantes sans supprimer la synthese actuelle.

Ordre recommande :

1. fournir les objets valides au prompt de synthese ;
2. demander a la synthese de les referencer par identifiant et version ;
3. comparer en test l'ancienne et la nouvelle sortie ;
4. projeter `problematiques_actuelles` depuis les problemes valides lorsque la couverture est suffisante ;
5. projeter `taches_actuelles` depuis les taches ;
6. separer dans `points_a_reprendre` les objets valides et les suggestions de verification ;
7. conserver emotions, cognitions, comportements, evolutions et interventions dans la logique actuelle tant que leurs futurs registres ne sont pas prets.

Regle de repli : si le registre est absent ou incomplet, la synthese actuelle peut continuer a produire une vue prudente, mais l'origine et la limite doivent etre visibles. Le repli ne cree aucun objet implicite.

Critere de sortie : aucune divergence entre objet valide et vue ; les fonctions actuelles restent disponibles.

### Phase 7 - Brancher la preparation comme vue derivee hybride

**But :** faire de la preparation une lecture des sources d'autorite, conformement a `05_preparation_prochaine_seance.md`.

Ordre recommande :

1. lire les taches et points ouverts depuis leurs registres ;
2. afficher l'objectif valide lie lorsqu'il existe ;
3. afficher les problemes actifs utiles a la prochaine seance ;
4. conserver le resume de derniere seance et les evolutions prudentes comme vues derivees ;
5. etiqueter toutes les suggestions avec `proposition_systeme` ;
6. enregistrer dans les metadonnees les identifiants et versions des objets consultes ;
7. verifier que le brief ne peut jamais modifier les registres ;
8. conserver l'anti-doublon actuel en ajoutant l'empreinte du registre et des versions consultees.

La preparation V1.0 actuelle reste disponible jusqu'a ce que les tests de couverture prouvent que la nouvelle projection ne perd aucune information utile.

Critere de sortie : une modification validee d'un objectif ou d'une tache se repercute dans la preparation sans copie manuelle et sans nouvel objet divergent.

### Phase 8 - Stabiliser le modele longitudinal V1

**But :** verifier la robustesse avant d'ajouter l'analyse fonctionnelle.

Tests d'acceptation :

- chaque objet a une source de verite unique ;
- chaque assertion importante a une provenance retrouvable ;
- aucune fermeture par non-mention ;
- aucune suggestion devenue decision sans validation ;
- toute modification conserve l'histoire ;
- une contradiction reste visible ;
- un objectif modifie est coherent dans toutes les vues ;
- une tache sans resultat reste `resultat_non_documente` ;
- le second lancement sans changement effectue zero appel API ;
- les patients restent separes ;
- un rejet deterministe conserve les jetons ;
- aucune donnee nominative n'entre dans les fixtures ou les documents de conception.

Critere de sortie : V1 figee, documentee et testee sur plusieurs trajectoires fictives.

## 4. Etapes suivantes apres la V1

### Etape 9 - `episode_fonctionnel`

Ajouter une selection de candidats fondes sur des episodes precis : contexte, reponses, consequences, donnees manquantes et fonction supposee separee. Le systeme propose ; le clinicien valide les episodes utilises comme preuves consolidees.

Dependances deja preparees : identifiants de problemes, objectifs, provenance atomique, statut epistemique, validation et historique.

### Etape 10 - `conceptualisation_versionnee`

Construire une formulation descriptive puis transversale : problemes expliques, mecanismes prioritaires, preuves pour et contre, alternatives, predictions et motifs de revision. Les hypotheses restent `hypothese_clinique` et ne deviennent jamais des faits par repetition.

### Etape 11 - `plan_de_traitement`

Relier explicitement probleme, objectif, mecanisme ou cible, intervention, prediction, indicateur et critere de revision. Le diagnostic ou une bibliotheque de techniques ne doit jamais creer automatiquement ce lien.

### Etapes ulterieures

- series de mesures apres arbitrage de la strategie et de la gouvernance ;
- vigilances apres chantier securite specifique ;
- essais d'intervention et effets comme evenements cliniques structures ;
- plan de maintien/rechute ;
- profils de promotion dans le dossier ;
- ACT comme extension conditionnelle du meme graphe, jamais comme dossier parallele.

## 5. Matrice de non-regression

| Fonction validee | Pendant la transition | Verification |
|---|---|---|
| OCR et extraction V2 | inchangees jusqu'a chantier source V2.1 | tests OCR/date/extraction existants |
| synthese longitudinale | conservee, puis lecture hybride | comparaison d'instantanes fictifs et controles de dates |
| preparation V1.0 | conservee jusqu'a couverture suffisante | contenu, provenance, zero appel au second lancement |
| multi-patients | registre et propositions sous dossier patient | tests d'isolation et traitement par lot |
| anti-doublon | empreintes et versions etendues | changement source/prompt/registre et absence de changement |
| jetons | comptabilisation avant validation | tests de rejet deterministe |
| donnees manquantes | aucune completion automatique | cas sans objectif, resultat ou point explicite |
| suggestions IA | restent separees | validation du statut d'action |

## 6. Ordre concret du prochain chantier de code

Apres validation des arbitrages du document 06 :

1. creer les modeles Pydantic du registre et des propositions dans un module dedie ;
2. ajouter les tests purs de cycle de vie et de statuts ;
3. creer le catalogue de provenance depuis les JSON V2 ;
4. ajouter les tests de provenance et de contradiction ;
5. construire des fixtures JSON fictives couvrant les dix cas de la phase 3 ;
6. seulement ensuite, definir le prompt Terra de propositions de mise a jour ;
7. garder `main.py` inchange jusqu'a validation des sorties de ce generateur isole ;
8. integrer la validation et la lecture hybride par petites modifications testees.

Cet ordre evite de faire dependre le schema clinique d'une sortie LLM avant d'avoir fixe les frontieres d'autorite et les controles deterministes.

## 7. Decisions bloquantes avant codage

Seuls les trois arbitrages du document `06_modele_clinique_longitudinal_v1.md` bloquent le debut :

1. validation obligatoire ou import automatique limite ;
2. transition hybride ou bascule immediate de la preparation ;
3. politique de candidats d'objectifs lorsque l'historique n'en documente aucun.

Les arbitrages sur les mesures, vigilances, episodes, promotion dans le dossier, ACT et impasses restent importants, mais ils ne doivent pas bloquer la definition des quatre objets V1 et de leur provenance minimale.
