# Spécification clinique — préparation de la prochaine séance

**Phase :** conception clinique, avant schémas de données et avant RAG  
**Date de l'analyse :** 17 août 2026  
**Destinataire :** psychologue-psychothérapeute  
**Statut du document :** recommandation d'architecture, non protocole de soin ni procédure de sécurité

## 1. Décision de conception

La liste candidate est retenue sous la forme de **douze champs**, après fusions et exclusions explicites. Le brief a une seule fonction : préparer une décision clinique située dans le temps à partir de données déjà documentées. Il ne remplace ni l'évaluation, ni la note de séance, ni la conceptualisation, ni le plan de traitement, ni les procédures de sécurité.

Le brief est une **vue opérationnelle dérivée, courte, datée et traçable**. Il n'est la source de vérité d'aucun fait, score, objectif, mécanisme, plan, tâche, vigilance ou décision. Sa conservation éventuelle sert l'audit ; elle ne l'autorise pas à mettre à jour les registres longitudinaux.

Ordre final :

1. cadre et fraîcheur des données ;
2. vigilances prioritaires ;
3. changements cliniquement pertinents ;
4. continuité de la dernière séance ;
5. objectifs actifs et progression ;
6. tâches interséances à revoir ;
7. mesures à interpréter ou recueillir ;
8. foyer fonctionnel et conceptuel actuel ;
9. questions cliniques à vérifier ;
10. priorités et agenda proposés ;
11. options d'intervention conditionnelles ;
12. provenance et limites.

L'ordre suit d'abord le risque d'erreur et de préjudice, puis la continuité des engagements, puis la valeur décisionnelle. Il ne suit ni la chronologie exhaustive du dossier ni l'ordre des champs dans une note de séance.

## 2. Conventions épistémiques

Chaque assertion clinique conserve l'un des quatre statuts suivants :

- **`explicite`** : directement soutenue par une déclaration, observation, mesure, décision ou autre source clinique identifiable ;
- **`synthese_prudente`** : compression fidèle de plusieurs éléments explicites, avec période, exceptions et contradictions pertinentes, sans ajout causal majeur ;
- **`hypothese_clinique`** : interprétation causale, fonctionnelle ou théorique révisable, avec éléments pour et contre, alternative et moyen de vérification ;
- **`inconnu_a_explorer`** : donnée absente ou insuffisante dont la clarification pourrait modifier sécurité, compréhension, objectif, intervention ou séance suivante.

Le statut d'action est séparé du statut épistémique. Une priorité ou une intervention produite automatiquement porte **`proposition_systeme`**. Elle ne devient `option_clinicien`, `decision_clinicien`, `decision_conjointe` ou `realise` qu'après l'événement correspondant, documenté par une personne autorisée.

Une non-mention n'est jamais une absence. Une tâche prévue n'est pas une tâche réalisée. Une hypothèse répétée n'est pas un fait. Une proposition bien argumentée n'est pas une décision.

## 3. Convention de citation du corpus

- Les références à Persons, Kuyken–Padesky–Dudley, Eells, Antony–Barlow et aux autres PDF utilisent la **pagination imprimée**, avec l'index PDF physique ajouté lorsque celui-ci a été vérifié et apporte une sécurité de repérage.
- L'EPUB de Beck ne contient pas d'ancres stables de pages imprimées : ses locateurs sont donc limités au chapitre et à la section. Un numéro de page n'est pas inventé.
- Les EPUB fixes de Cottraux et Bouvet contiennent des ancres de pagination imprimée fiables au niveau page/section ; une ancre peut toutefois tomber à la frontière d'un élément.
- La formalisation logicielle de la date de coupure, des sources de vérité, des statuts et des règles de rendu est une **proposition d'ingénierie clinique** soutenue indirectement par les principes d'évaluation itérative, de formulation révisable et de traçabilité ; elle n'est pas un formulaire reproduit d'un auteur.

## 4. Évaluation, fusions et exclusions de la liste candidate

### 4.1 Champs conservés séparément

- **Cadre/fraîcheur** reste distinct de la provenance détaillée : le premier prévient immédiatement un usage hors périmètre ; la provenance complète est placée en fin de document et peut être repliable.
- **Vigilances** reste distinct : sa priorité de lecture et sa gouvernance externe interdisent de la fondre dans les changements récents.
- **Changements** et **continuité** restent séparés : un événement récent n'est pas nécessairement issu de la dernière séance, et ce qui avait été décidé ou différé peut rester important sans changement récent.
- **Tâches** reste distinct des objectifs : elle possède son propre cycle de vie, ses obstacles, ses effets et son registre d'autorité.
- **Mesures** reste distinct des changements : un score brut, une tendance et un changement clinique ne sont pas le même objet.
- **Questions à vérifier** reste distinct du foyer conceptuel : elle rend visibles les incertitudes décisionnelles sans enrichir artificiellement la formulation.
- **Options conditionnelles** reste distinct de l'agenda : une séance peut avoir un agenda utile sans qu'aucune nouvelle technique soit suggérée.

### 4.2 Fusions retenues

- **Objectifs + progression** : la progression n'a de sens que relativement à un objectif, un indicateur et une période. Deux rubriques séparées créeraient des divergences.
- **Foyer fonctionnel + foyer conceptuel** : les épisodes micro et les mécanismes macro restent deux objets sources, mais une seule vue brève les met en relation pour la prochaine décision.
- **Priorités + agenda** : une priorité sans place dans l'agenda est peu actionnable ; un agenda sans motif masque son origine. Chaque item conserve donc priorité, motif et source.
- **Provenance + limites** : les limites de couverture, de temporalité et d'extraction prennent leur sens au contact des sources effectivement utilisées.

### 4.3 Éléments supprimés comme champs de premier niveau

| Élément candidat | Décision | Justification et destination |
|---|---|---|
| diagnostic complet | exclu du brief | utile comme donnée liée, mais insuffisant pour produire un mécanisme ou un plan ; mention seulement s'il change la séance ou une vigilance |
| anamnèse et histoire exhaustive | exclues | surcharge et risque nominatif ; seuls les facteurs historiques qui modifient une hypothèse ou une adaptation actuelle peuvent apparaître au champ 8 |
| conceptualisation complète | exclue | reste dans l'objet versionné d'autorité ; le brief n'affiche que quelques mécanismes décisionnels |
| plan de traitement complet | exclu | source de vérité séparée ; seuls objectifs, cibles, décisions actives et dates de revue nécessaires sont projetés |
| note ou transcription intégrale | exclue | source clinique, non contenu du brief ; le brief renvoie aux locateurs utiles |
| liste exhaustive de symptômes ou de problèmes | exclue | ne montrer que ce qui peut changer la séance ; l'inventaire longitudinal reste disponible ailleurs |
| tableau de bord complet des mesures | exclu | afficher seulement une tendance interprétable, un signal ou une mesure due |
| ressources/forces comme rubrique autonome | fusionnées | intégrées aux objectifs, au foyer fonctionnel et aux options seulement lorsqu'elles peuvent être mobilisées |
| alliance comme rubrique autonome | fusionnée | changements, continuité, vigilances de processus, questions et options peuvent l'accueillir ; une rupture active reste prioritaire |
| impasse comme rubrique autonome | fusionnée | transforme les champs 8, 9 et 11 en audit ciblé ; l'historique d'impasse reste un objet séparé |
| techniques ou protocole par diagnostic | exclus | bibliothèque externe ; aucune correspondance automatique diagnostic → intervention |
| module ACT permanent | exclu | ACT reste une extension conditionnelle dans le même graphe de mécanismes |
| prochaine tâche préremplie | exclue | peut apparaître comme option ; elle ne devient tâche qu'après décision collaborative |
| conclusion générale de sécurité | interdite | les procédures de sécurité et l'évaluation actuelle priment ; absence de mention ou score faible ne permettent pas de conclure |

## 5. Spécification détaillée des douze champs

### Champ 1 — `cadre_et_fraicheur_des_donnees`

**Fonction clinique**  
Définir ce que le brief couvre réellement et empêcher que la dernière information disponible soit confondue avec l'état actuel. Ce champ calibre la confiance d'usage avant toute lecture clinique.

**Informations requises**

- identifiant interne pseudonymisé ;
- date prévue de la séance, si connue ;
- dernière séance exploitable et sa date ;
- date et heure de coupure du brief ;
- catégories de sources incluses et période couverte ;
- sources attendues mais absentes, imports incomplets, transcription partielle ou retard de synchronisation ;
- version du brief et, si pertinent, version des objets longitudinaux utilisés.

**Sources théoriques traçables**

- Persons décrit la formulation initiale comme incomplète, continuellement testée et révisée par l'évaluation et le suivi : *The Case Formulation Approach to Cognitive-Behavior Therapy*, chap. 1, pp. 1–6 ; PDF pp. 16–21.
- Antony et Barlow définissent l'évaluation comme une décision itérative où données incomplètes et discordantes doivent être intégrées : *Handbook of Assessment and Treatment Planning for Psychological Disorders*, chap. 1, pp. 7–8 ; PDF pp. 26–27.
- Eells distingue observation, inférence et tension entre agir tôt et viser l'exhaustivité : *Handbook of Psychotherapy Case Formulation*, 3e éd., chap. 1, pp. 2–4 et 22–25 ; PDF pp. 15–17 et 35–38.
- Beck demande, dans « Planning Individual Sessions », de revoir notes, objectifs, plan d'action et progrès avant la séance : *Cognitive Behavior Therapy: Basics and Beyond*, 3e éd., chap. 9 ; EPUB sans pagination stable.

La date de coupure et l'indicateur de fraîcheur sont une proposition d'ingénierie clinique, non un champ textuellement prescrit par ces ouvrages.

**Statuts épistémiques autorisés**  
`explicite` pour dates, versions et présence des sources ; `synthese_prudente` pour la qualité de couverture ; `inconnu_a_explorer` si une lacune peut modifier la préparation. `hypothese_clinique` n'est pas admis dans ce champ.

**Caractère obligatoire**  
Toujours présent, même si la génération est limitée.

**Si les données sont insuffisantes**  
Nommer la lacune, sa période et sa conséquence. Réduire explicitement la portée. Si l'identité pseudonymisée, la date de coupure ou la séparation entre plusieurs dossiers ne peut être établie, refuser la génération complète.

**Risque principal**  
Fausse actualité : présenter une source ancienne, incomplète ou mal attribuée comme description du présent.

**Source de vérité et stockage**  
Le catalogue des documents, séances, imports et versions est l'autorité. Le champ est une **vue dérivée**. Un instantané peut conserver les identifiants et versions utilisés pour audit ; aucune correction de source ne s'effectue depuis le brief.

### Champ 2 — `vigilances_prioritaires`

**Fonction clinique**  
Remettre au premier plan les éléments dont l'oubli pourrait compromettre sécurité, tolérance, faisabilité ou pertinence du travail prévu, sans prétendre remplacer une évaluation actuelle.

**Informations requises**

- vigilances actives ou arrivant à échéance ;
- fait(s) et date(s) qui les fondent ;
- date et contexte de la dernière évaluation pertinente ;
- statut documenté, incertain ou à réévaluer ;
- action, échéance, responsable ou voie d'escalade uniquement s'ils sont documentés ;
- effets indésirables, contre-indications, changement médical/contextuel ou rupture de processus pouvant modifier la séance ;
- contradiction ou ancienneté qui empêche une conclusion actuelle.

**Sources théoriques traçables**

- Le dépistage est bref et probabiliste, alors que l'évaluation exige plusieurs sources et expertise ; faux positifs et taux de base imposent une évaluation ultérieure : Antony–Barlow, chap. 2, pp. 41–44 ; PDF pp. 60–63.
- L'évaluation fondée sur les preuves intègre contexte, conditions médicales, préférences, contraintes et réévaluation : Antony–Barlow, chap. 1, pp. 13–17 ; PDF pp. 32–36.
- Beck inclut adéquation du dispositif, traitements concomitants pertinents, facteurs externes et besoin d'orientation dans l'évaluation et l'audit des difficultés : chap. 5 « Objectives for the Evaluation Session » et chap. 22 « Problems in Therapy » ; EPUB sans pagination stable.
- Bouvard et Cottraux rappellent, dans un cadre de recherche, consentement et critères d'aggravation conduisant à changer de prise en charge : *Protocoles et échelles d'évaluation en psychiatrie et psychologie*, 5e éd., chap. 4, p. 39. Ce repère ne constitue pas une procédure clinique actuelle.

**Statuts épistémiques autorisés**  
Les quatre statuts sont possibles. Une hypothèse doit être séparée du fait qui la motive. Une donnée ancienne ou manquante devient `inconnu_a_explorer` si son actualisation est décisionnelle ; elle ne devient jamais une conclusion rassurante.

**Caractère obligatoire**  
Section toujours rendue ; contenu clinique conditionnel. En l'absence d'élément retrouvé, afficher la portée exacte de la recherche et la date de dernière donnée, jamais « aucune vigilance » sans évaluation explicite.

**Si les données sont insuffisantes**  
Indiquer : « aucune vigilance active retrouvée dans les sources consultées ; cela ne démontre pas une absence de risque », puis préciser la limite ou la date de dernière évaluation. Si une question de sécurité actuelle excède les données, renvoyer aux procédures et à l'évaluation professionnelles appropriées ; ne pas générer une conclusion de sécurité.

**Risque principal**  
Déduire l'absence de risque d'une non-mention, ou amplifier un signal faible en certitude.

**Source de vérité et stockage**  
Le registre de vigilances, ses catégories et les procédures professionnelles externes constituent l'autorité. Le brief est une **vue dérivée priorisée** et n'ouvre, ne clôt ni ne réattribue une vigilance.

### Champ 3 — `changements_cliniquement_pertinents`

**Fonction clinique**  
Sélectionner ce qui a changé depuis la dernière séance exploitable et peut modifier agenda, formulation, objectifs, mesure, faisabilité ou vigilance.

**Informations requises**

- événements nouveaux datés ou période approximative explicitée ;
- évolution symptomatique, fonctionnelle ou contextuelle ;
- effets ou effets indésirables d'une intervention ;
- changement de traitement concomitant ou d'accès aux soins s'il est pertinent ;
- tendance mesurée seulement si les points sont comparables ;
- éléments stables uniquement si leur stabilité a été explicitement évaluée et change une décision ;
- source, informateur et éventuelles contradictions.

**Sources théoriques traçables**

- Persons relie suivi des résultats et processus aux décisions de poursuite ou de modification : chap. 9, pp. 182–198 ; PDF pp. 197–213.
- Antony–Barlow distingue cibles/objectifs, mécanismes et contexte/processus, avec cadences différentes : chap. 1, pp. 16–17 ; PDF pp. 35–36.
- Beck place contrôle de l'état actuel, actualisation de l'intervalle et données de progrès dans la première partie de la séance : chap. 2 « Principles of Treatment » et chap. 10 « The First Part of the Session » ; EPUB sans pagination stable.
- Le *Unified Protocol* rappelle que le progrès fluctue et qu'une variation n'est pas automatiquement une rechute : chap. 14, pp. 164–169 ; PDF pp. 177–182.

**Statuts épistémiques autorisés**  
`explicite` pour événements et valeurs ; `synthese_prudente` pour une évolution sur période définie ; `hypothese_clinique` seulement dans une sous-partie distincte si une explication est proposée. `inconnu_a_explorer` est admis pour une évolution manquante qui change la préparation.

**Caractère obligatoire**  
Facultatif et supprimé si aucune nouveauté pertinente n'est documentée. La non-mention de changement ne doit pas produire « stable ».

**Si les données sont insuffisantes**  
Omettre la conclusion et signaler au champ 1 l'absence de couverture. Si l'actualisation est nécessaire, produire une question au champ 9.

**Risque principal**  
Surpondérer le plus récent, construire une tendance avec deux points non comparables ou présenter la non-mention comme stabilité.

**Source de vérité et stockage**  
Événements cliniques explicites, séries de mesures et historique des interventions. Ce champ est une **synthèse dérivée datée** ; il ne crée pas d'événement nouveau.

### Champ 4 — `continuite_de_la_derniere_seance`

**Fonction clinique**  
Restaurer le fil du travail sans relire la note entière : ce qui a été effectivement travaillé, appris, décidé ou différé.

**Informations requises**

- objectifs réellement abordés ;
- intervention ou exercice réellement réalisé, distinct du plan prévu ;
- réaction, apprentissage ou conclusion documentés ;
- décision effectivement prise ;
- difficulté de processus ou effet indésirable apparu ;
- point explicitement différé, avec motif et priorité ;
- source précise dans la note ou la séance.

**Sources théoriques traçables**

- Beck articule actualisation, revue du plan d'action, agenda, travail, synthèses et feedback : chap. 2, chap. 6 et chap. 10 « Structuring Sessions » ; EPUB sans pagination stable.
- Cottraux décrit une séance comprenant revue des tâches, agenda, synthèses, techniques, synthèse par la personne, feedback et suite : *Les psychothérapies cognitives et comportementales*, 6e éd., chap. 13, p. 226 ; EPUB fixe.
- Le chapitre d'activation comportementale du *Clinical Handbook of Psychological Disorders* propose agenda partagé, revue interséance, nouveau travail et synthèse : chap. 9, p. 360 ; PDF p. 378.
- Persons relie la décision de séance à la formulation et au plan : chap. 10, pp. 202–214 ; PDF pp. 217–229.

**Statuts épistémiques autorisés**  
`explicite` et `synthese_prudente`. Une explication de difficulté devient `hypothese_clinique` au champ 8 ou 9. `inconnu_a_explorer` est admis uniquement si une lacune de note empêche de savoir ce qui a été décidé ou réalisé.

**Caractère obligatoire**  
Obligatoire lorsqu'une dernière séance exploitable existe. Sinon, afficher sobrement l'absence au champ 1 et adapter ou refuser la génération selon son impact.

**Si les données sont insuffisantes**  
Écrire « note absente ou incomplète » et ne pas reconstruire la séance à partir d'un agenda antérieur. Un élément « prévu » ne peut apparaître comme « travaillé ».

**Risque principal**  
Confondre intention, réalisation et apprentissage, ou perdre un engagement explicite.

**Source de vérité et stockage**  
Note de séance validée, événements de séance et registre des éléments à reprendre. Le champ est une **vue dérivée** ; les points différés restent stockés dans leur registre, non dans le brief seul.

### Champ 5 — `objectifs_actifs_et_progression`

**Fonction clinique**  
Maintenir la séance reliée aux finalités négociées et montrer quels objectifs doivent être poursuivis, précisés, révisés ou mis en pause.

**Informations requises**

- objectif actif dans sa formulation documentée ;
- problème ou domaine lié ;
- valeur, importance ou motif personnel si documenté ;
- indicateur d'atteinte et horizon ;
- priorité, statut et date de dernière révision ;
- dernière donnée de progression et période couverte ;
- obstacle documenté, sans lui attribuer automatiquement une cause ;
- désaccord ou changement de priorité.

**Sources théoriques traçables**

- Persons recommande des objectifs significatifs, réalistes, observables, mesurables et hiérarchisés : chap. 6, pp. 143–146 ; PDF pp. 158–161.
- Kuyken, Padesky et Dudley ajoutent formulation positive, contrôlabilité et co-construction : *Collaborative Case Conceptualization*, chap. 5, pp. 152–157 ; PDF pp. 171–176.
- Beck relie valeurs, aspirations, objectifs, étapes, obstacles et planification : chap. 9 « Values, Aspirations, and Goals » et « Planning Treatment to Accomplish a Specific Goal » ; EPUB sans pagination stable.
- Bouvet distingue stratégie révisable et technique concrète, après conceptualisation : chap. 2, pp. 31–52, et chap. 3, pp. 55–57 ; EPUB fixe.
- Antony–Barlow recommande de suivre cibles/objectifs et mécanismes séparément : chap. 1, pp. 16–17 ; PDF pp. 35–36.

**Statuts épistémiques autorisés**  
L'objectif et son statut sont `explicite` s'ils résultent d'une décision documentée. Une tendance de progression est `synthese_prudente`. Un obstacle causal reste `hypothese_clinique`. Une donnée indispensable manquante peut être `inconnu_a_explorer`.

**Caractère obligatoire**  
Obligatoire dans un traitement actif. Si aucun objectif documenté n'existe, ne pas en fabriquer : afficher « objectif actif non documenté » et placer sa clarification parmi les priorités.

**Si les données sont insuffisantes**  
Afficher l'objectif sans conclure sur la progression, puis préciser la mesure ou observation utile. Si l'objectif lui-même est ambigu ou non partagé, proposer sa clarification, non une intervention spécifique.

**Risque principal**  
Transformer un symptôme en objectif supposé, présenter un objectif ancien comme toujours prioritaire ou coder absence de mesure comme stagnation.

**Source de vérité et stockage**  
Registre longitudinal unique des objectifs. Le brief affiche une **projection datée** et ne modifie ni formulation, ni priorité, ni statut.

### Champ 6 — `taches_intersession_a_revoir`

**Fonction clinique**  
Soutenir l'apprentissage et la généralisation en examinant ce qui avait réellement été convenu, ce qui s'est produit, les effets et les obstacles, sans moraliser la réalisation.

**Informations requises**

- consigne effectivement convenue et date ;
- objectif, mécanisme ou apprentissage ciblé ;
- rationale partagé et paramètres nécessaires ;
- échéance ou fenêtre temporelle ;
- résultat rapporté, réalisation partielle ou absence de résultat documenté ;
- apprentissages, effets indésirables et obstacles ;
- faisabilité, préférence ou adaptation déjà décidée ;
- décision attendue : poursuivre, adapter, répéter, suspendre ou arrêter.

**Sources théoriques traçables**

- Beck traite choix, faisabilité, obstacles, revue et conceptualisation d'une tâche non faite : chap. 8 « Action Plans » et chap. 10 ; EPUB sans pagination stable.
- Bouvet précise que les exercices sont expliqués, discutés et choisis plutôt qu'imposés, puis repris selon leurs effets : introduction, pp. 7–10 ; EPUB fixe.
- Le chapitre d'activation comportementale recommande plan d'exécution, obstacles probables, revue effective et exploration non critique de la non-réalisation : *Clinical Handbook*, chap. 9, pp. 364–365 ; PDF pp. 382–383.
- Leahy intègre à chaque fiche une tâche, des problèmes possibles et des alternatives ; structure vérifiable dès chap. 2, pp. 17–19 de *Cognitive Therapy Techniques*, 2e éd. ; PDF physiques pp. 37–39.
- Cottraux place revue des tâches et choix des expériences suivantes dans la séance : chap. 13, p. 226.

**Statuts épistémiques autorisés**  
`explicite` pour consigne, accord et résultat rapporté ; `synthese_prudente` pour apprentissage condensé ; `hypothese_clinique` pour fonction d'un obstacle ; `inconnu_a_explorer` pour résultat non documenté si sa revue est utile. Le statut d'action de la tâche reste distinct.

**Caractère obligatoire**  
Facultatif ; rendu uniquement si une tâche a réellement été convenue ou reste active. Une simple option ancienne ne suffit pas.

**Si les données sont insuffisantes**  
Écrire « résultat non documenté », jamais « non réalisée ». Ne pas attribuer de motif. Transformer un obstacle plausible en question neutre.

**Risque principal**  
Confondre prescription envisagée et accord, moraliser la non-réalisation ou perdre l'apprentissage d'une tentative partielle.

**Source de vérité et stockage**  
Registre des tâches interséances et événements de résultat. Le champ est une **vue dérivée**. Toute nouvelle tâche ou modification est enregistrée après décision clinique/collaborative, jamais depuis la suggestion du brief.

### Champ 7 — `mesures_a_interpreter_ou_recueillir`

**Fonction clinique**  
Présenter uniquement une tendance interprétable, un signal ou une mesure due susceptible de modifier une décision.

**Informations requises**

- instrument ou méthode, version, langue et informateur ;
- construit et finalité clinique ;
- valeurs datées et conditions de recueil ;
- comparabilité, sens du score et repères documentés ;
- référence normative ou ipsative clairement distinguée ;
- ligne de base et période de tendance, si utilisables ;
- fréquence prévue et motif de la prochaine mesure ;
- limite, charge, réactivité ou donnée manquante pertinente.

**Sources théoriques traçables**

- Antony–Barlow décrit une boucle où suivi des cibles, mécanismes et processus oriente poursuite ou modification : chap. 1, pp. 16–17 ; PDF pp. 35–36 ; discussion clinique du feedback, chap. 2, pp. 29–30 et 43–44 ; PDF pp. 48–49 et 62–63.
- Persons distingue mesures de résultats et de processus et leur usage pour la décision : chap. 9, pp. 182–198 ; PDF pp. 197–213.
- Bouvard et Cottraux distinguent normatif et ipsatif, qualités métrologiques, validation linguistique et recommandent peu de mesures variées : *Protocoles et échelles*, chap. 6, pp. 55–61.
- Cottraux recommande ligne de base, mesures répétées et simplicité clinique : *Les psychothérapies cognitives et comportementales*, chap. 6, pp. 107–113.

**Statuts épistémiques autorisés**  
Valeur brute `explicite` ; tendance `synthese_prudente` ; interprétation mécanistique `hypothese_clinique` ; mesure attendue mais absente `inconnu_a_explorer` si décisionnelle.

**Caractère obligatoire**  
Facultatif et conditionnel. Un brief sans mesure peut être valide si aucune série n'est due ou interprétable.

**Si les données sont insuffisantes**  
Ne pas extrapoler. Signaler point unique, changement de version, fenêtre différente, norme inadaptée ou ancienneté. Proposer une mesure seulement si sa finalité, ses droits d'usage et la conduite à tenir sont définissables.

**Risque principal**  
Fausse précision, surcharge de scores, comparaison non valide ou pilotage de la séance par ce qui est facile à mesurer.

**Source de vérité et stockage**  
Registre des séries de mesures référençant les événements de mesure canoniques, dont les valeurs brutes et métadonnées restent immuables. Le brief présente une **sélection dérivée** ; il ne recalcule ni ne remplace la série d'autorité.

### Champ 8 — `foyer_fonctionnel_et_conceptuel_actuel`

**Fonction clinique**  
Rappeler les quelques épisodes et mécanismes de maintien qui expliquent pourquoi une question ou une intervention mérite une place dans la prochaine séance.

**Informations requises**

- problème et objectif concernés ;
- épisode(s) fonctionnel(s) récent(s) ou représentatif(s) : contexte, réponses, conséquences ;
- mécanisme ou relation fonctionnelle candidate ;
- éléments pour, contre et exceptions ;
- alternative plus simple ou concurrente ;
- ressources, facteurs protecteurs ou conditions où le cycle ne se produit pas ;
- réponse aux interventions antérieures et prédiction testable ;
- version/date de la conceptualisation active et niveau d'inférence.

**Sources théoriques traçables**

- Persons distingue formulation du cas, d'un problème et d'un épisode, puis relie mécanisme, cible, intervention et mesure : chap. 1, p. 7 ; PDF p. 22 ; analyse d'épisodes, chap. 3, pp. 42–64 ; PDF pp. 57–79.
- Kuyken–Padesky–Dudley recommande le niveau d'inférence le plus bas suffisant, des thèmes fondés sur plusieurs épisodes et une révision du modèle contredit : chap. 2, pp. 27–43 ; PDF pp. 46–62 ; chap. 5–6, pp. 139–144 et 181–189 ; PDF pp. 158–163 et 200–208.
- Eells décrit des relations fonctionnelles observables, prédictives et modifiables : chap. 11, pp. 323–339 ; PDF pp. 336–352.
- Bouvet distingue formulation macro et analyse micro, et exige une conceptualisation parcimonieuse et révisable : chap. 2, pp. 37–52.
- Cottraux présente analyses qualitatives, SECCA et cercles vicieux, sans les confondre avec l'évaluation complète : chap. 6, pp. 98–113.
- Beck fait de la conceptualisation cognitive une hypothèse commencée tôt et révisée : chap. 3 « Cognitive Conceptualization » ; EPUB sans pagination stable.

**Statuts épistémiques autorisés**  
Composants d'un épisode `explicite` ; régularité descriptive `synthese_prudente` ; fonction, croyance ou mécanisme `hypothese_clinique` ; donnée manquante déterminante `inconnu_a_explorer`.

**Caractère obligatoire**  
Facultatif. Ne rien afficher si aucune hypothèse suffisamment reliée aux données ne peut modifier la séance. Limite recommandée : trois mécanismes ou relations au maximum.

**Si les données sont insuffisantes**  
Afficher au plus une question fonctionnelle concrète au champ 9. Ne pas générer une explication standard à partir du diagnostic, ni ajouter une origine historique pour remplir la rubrique.

**Risque principal**  
Réifier une hypothèse, confondre forme et fonction, multiplier les modèles ou reconstruire une causalité à partir d'une seule cooccurrence.

**Source de vérité et stockage**  
Registre des épisodes fonctionnels et conceptualisation versionnée. Le champ est une **vue dérivée**, jamais une deuxième conceptualisation. Les modèles SECCA, SORC, cognitifs ou ACT éventuels sont des vues du même graphe, non des vérités parallèles.

### Champ 9 — `questions_cliniques_a_verifier`

**Fonction clinique**  
Transformer contradictions, inconnues et hypothèses décisionnelles en questions neutres, observables ou discutables pendant la séance.

**Informations requises**

- question concise et non confirmatoire ;
- hypothèse, contradiction ou inconnue d'origine ;
- faits qui motivent la question ;
- décision qui dépend de la réponse ;
- information ou observation attendue ;
- priorité et date de création ;
- statut après vérification : résolue, partiellement résolue, maintenue ou abandonnée.

**Sources théoriques traçables**

- Persons présente la formulation comme hypothèse testée par suivi, intervention et progrès : chap. 1, pp. 1–6, et chap. 9–10, pp. 182–214.
- Kuyken–Padesky–Dudley demande de modifier ou abandonner un modèle lorsque observations ou expériences le contredisent : chap. 2, pp. 29–31 ; PDF pp. 48–50.
- Eells distingue données et inférences et souligne l'incomplétude nécessaire d'une formulation précoce : chap. 1, pp. 2–4 et 22–25.
- Antony–Barlow recommande formulations alternatives, triangulation, vigilance aux biais et expériences pour les tester : chap. 1, p. 15 ; PDF p. 34.
- Bouvet décrit la conceptualisation comme hypothèse simplifiée et révisable : chap. 2, pp. 38–42.

**Statuts épistémiques autorisés**  
La question découle principalement de `hypothese_clinique` ou `inconnu_a_explorer`. Les faits qui la motivent restent `explicite` ou `synthese_prudente`. La question n'est pas présentée comme une assertion.

**Caractère obligatoire**  
Facultatif ; maximum recommandé de trois questions. Une question n'est conservée que si sa réponse peut modifier sécurité, compréhension ou action.

**Si les données sont insuffisantes**  
Préférer une question neutre à une réponse probable. Si aucune vérification réaliste n'est possible ou si la question est seulement théorique, l'omettre.

**Risque principal**  
Question confirmatoire, curiosité sans conséquence, accumulation d'inconnues décoratives ou suggestion implicite d'une cause.

**Source de vérité et stockage**  
Registre des hypothèses, contradictions et éléments à reprendre. Le brief en affiche une **sélection dérivée**. La réponse produite en séance doit être documentée comme nouvelle évidence avant toute révision de la formulation.

### Champ 10 — `priorites_et_agenda_proposes`

**Fonction clinique**  
Traduire l'état longitudinal en proposition de séance claire, limitée et révisable avec le clinicien puis avec la personne suivie.

**Informations requises**

- deux ou trois priorités au maximum, ordonnées ;
- motif de chaque priorité : vigilance, engagement antérieur, objectif, changement, mesure, tâche, hypothèse ou question ;
- données sources et degré d'incertitude ;
- temps ou place relative seulement si utile, sans rigidité ;
- prérequis ou point à vérifier avant une intervention ;
- éléments explicitement différés ;
- statut d'action `proposition_systeme`.

**Sources théoriques traçables**

- Beck détaille choix d'un problème/objectif, planification de séance, agenda, rythme, déviation négociée et synthèse : chap. 9 « Planning Individual Sessions » et « Deciding Whether to Focus on an Issue or Goal », chap. 10–11 ; EPUB sans pagination stable.
- Cottraux décrit agenda collaboratif, revue, synthèses et feedback : chap. 9, p. 157, et chap. 13, p. 226.
- Le *Clinical Handbook* décrit agenda partagé, revue interséance, nouveau travail et synthèse : chap. 9, p. 360 ; PDF p. 378.
- Persons relie les décisions de séance à la formulation, aux objectifs et au suivi : chap. 10, pp. 202–214 ; PDF pp. 217–229.

**Statuts épistémiques autorisés**  
Les justifications conservent leurs statuts parmi les quatre. L'agenda lui-même n'est pas une assertion clinique : il porte `proposition_systeme` jusqu'à validation. Il ne doit jamais être présenté comme `explicite` au seul motif qu'il figure dans le brief.

**Caractère obligatoire**  
Toujours présent dans un brief généré avec succès. Si les données ne permettent pas un agenda clinique spécifique, la première priorité est l'actualisation ou la clarification. Si même cette proposition ne peut être attribuée au bon dossier ou à la bonne période, refuser la génération complète.

**Si les données sont insuffisantes**  
Proposer collecte/clarification, revue d'engagements ou actualisation de vigilance avant toute technique. Ne pas remplir avec des thèmes génériques.

**Risque principal**  
Rigidifier la séance, oublier la collaboration ou prioriser ce qui est facile à extraire plutôt que ce qui est cliniquement important.

**Source de vérité et stockage**  
Le champ dépend des registres de vigilances, objectifs, tâches, mesures, formulation, plan et éléments différés. Il est **entièrement dérivé** et n'a pas de source de vérité propre. L'agenda réel est documenté après discussion dans la note de séance.

### Champ 11 — `options_d_intervention_conditionnelles`

**Fonction clinique**  
Rendre visibles quelques options plausibles lorsque leur valeur dépend de vérifications en séance, sans préempter le jugement clinique ni transformer une bibliothèque en protocole.

**Informations requises**

- objectif et mécanisme/cible liés ;
- données favorables, défavorables et manquantes ;
- intervention déjà tentée et réponse observée ;
- rationale théorique et source ;
- prérequis, compétence nécessaire, préférence, consentement, contre-indication ou vigilance ;
- paramètre à individualiser et indicateur de réponse ;
- solution de repli ou raison de ne rien proposer ;
- statut `proposition_systeme`.

**Sources théoriques traçables**

- Persons définit le plan comme lien problème → objectif → mécanisme → intervention → prédiction → mesure et révision : chap. 7, pp. 150–165 ; PDF pp. 165–180.
- Bouvet distingue stratégie et technique, demande une cible connue et l'évaluation de ce qui a effectivement changé : chap. 3, pp. 55–60.
- Leahy présente son ouvrage comme boîte à outils dépendant de la conceptualisation, non protocole automatique : chap. 1, pp. 3–11 ; ses fiches comprennent description, intervention, tâche, problèmes et alternatives, chap. 2, pp. 17–19.
- Beck relie interventions, objectifs, formulation et obstacles, puis propose un audit avant de changer de technique : chap. 9 « Potential Interventions » et chap. 22 « Remediating Problems in Therapy » ; EPUB sans pagination stable.
- Antony–Barlow demande de combiner preuves, priorités, préférences, expériences antérieures, contexte, conditions médicales et contraintes : chap. 1, pp. 13–17 ; PDF pp. 32–36.

**Statuts épistémiques autorisés**  
Les éléments justificatifs peuvent porter les quatre statuts. L'option reste un statut d'action `proposition_systeme`, jamais une décision. Un mécanisme hypothétique ne devient pas explicite parce qu'une technique lui correspond.

**Caractère obligatoire**  
Facultatif. Zéro option vaut mieux qu'une option générique. Maximum de trois, chacune conditionnelle et reliée à une décision possible.

**Si les données sont insuffisantes**  
Omettre l'option ou indiquer la vérification préalable, sans détailler une procédure d'intervention. Refuser toute suggestion qui dépend d'une évaluation de sécurité, d'une indication, d'une compétence ou d'une information absente.

**Risque principal**  
Automatiser diagnostic → protocole, répéter une intervention inefficace, ignorer une mauvaise tolérance ou produire un catalogue décoratif.

**Source de vérité et stockage**  
Plan de traitement, historique des interventions et bibliothèque théorique sont les dépendances. Le brief est une **vue de possibilités**. Une option sélectionnée n'entre dans le plan qu'après validation et documentation ; elle n'est jamais promue depuis le brief seul.

### Champ 12 — `provenance_et_limites`

**Fonction clinique**  
Permettre l'audit rapide de toute information importante et rendre visibles les limites qui changent l'interprétation ou l'usage du brief.

**Informations requises**

- pour chaque item important : objet source, document/séance, date et locateur ;
- relation de support : directe, synthétique, contradictoire ou contextuelle ;
- date de coupure et version d'extraction ;
- sources omises, illisibles, partielles ou trop anciennes ;
- contradictions non résolues ;
- limites de comparaison des mesures ;
- limites théoriques ou populationnelles d'une option ;
- statut de validation du brief : brouillon généré, validé, éventuellement promu.

**Sources théoriques traçables**

- Eells exige de distinguer phénomènes observés et inférences et rappelle la dépendance des mécanismes au cadre théorique : chap. 1, pp. 2–4 et 22–25 ; PDF pp. 15–17 et 35–38.
- Persons traite la formulation comme hypothèse révisable soumise aux données : chap. 1, pp. 1–6 ; PDF pp. 16–21.
- Antony–Barlow insiste sur l'intégration de plusieurs sources, les données discordantes et la qualité d'usage des mesures : chap. 1, pp. 7–8 ; PDF pp. 26–27.
- Kuyken–Padesky–Dudley demande de réduire ou abandonner un modèle contredit : chap. 2, pp. 29–31 ; PDF pp. 48–50.

La granularité `assertion → source → date → locateur → version` est une proposition d'architecture nécessaire à l'audit ; elle n'est pas un formulaire repris mot pour mot du corpus.

**Statuts épistémiques autorisés**  
Métadonnées `explicite` ; qualité ou couverture `synthese_prudente` ; lacune décisionnelle `inconnu_a_explorer`. Une hypothèse clinique n'a pas sa place dans les métadonnées, mais ses limites et sa provenance y sont référencées.

**Caractère obligatoire**  
Toujours présent, possiblement sous forme repliable. Les limites critiques restent visibles à proximité de l'item concerné et ne sont pas reléguées uniquement en fin de document.

**Si les données sont insuffisantes**  
Ne pas masquer la limite. Empêcher l'assertion correspondante ou réduire sa portée. Une provenance introuvable pour une information déterminante impose son omission ou le refus de la génération complète selon le risque.

**Risque principal**  
Fausse traçabilité : lien vers une séance qui ne soutient pas l'assertion, ou accumulation de références illisibles qui masque les lacunes.

**Source de vérité et stockage**  
Catalogue documentaire, graphe de provenance, versions des objets et journal de validation. Le champ est une **vue dérivée** ; l'instantané du brief peut conserver les identifiants et versions consultés pour reproductibilité.

## 6. Règles de sélection et de rendu

### 6.1 Test d'inclusion d'un item

Un item n'entre dans le brief que si les réponses suivantes sont satisfaisantes :

1. Quelle décision, question ou vigilance de la prochaine séance peut-il changer ?
2. Sa source est-elle attribuable, datée et suffisamment précise ?
3. Son statut épistémique peut-il être rendu sans ambiguïté ?
4. Est-il déjà représenté par sa source de vérité plutôt que recopié comme nouvel objet ?
5. Son bénéfice dépasse-t-il le risque de surinterprétation et la charge de lecture ?

Si aucune décision n'est affectée, l'item est omis. `inconnu_a_explorer` n'est utilisé que pour une lacune décisionnelle, jamais pour remplir un template.

### 6.2 Ordre interne

- Les vigilances actives ou obsolètes à réévaluer passent avant le reste.
- Les engagements de la dernière séance et objectifs prioritaires passent avant les suggestions nouvelles.
- Les changements sont ordonnés par conséquence clinique, non par nouveauté seule.
- Une contradiction est affichée près de l'assertion concernée.
- Une hypothèse est accompagnée de la question ou donnée qui peut la modifier.
- Chaque item d'agenda cite son motif et sa source.
- Une option d'intervention apparaît après, jamais avant, le mécanisme, l'objectif et les prérequis qui la justifient.

### 6.3 Parcimonie de rendu

- Résumé opérationnel : idéalement une à deux pages, avec détails et provenance repliables.
- Maximum recommandé : trois mécanismes, trois questions, trois priorités et trois options.
- Les champs 1, 2, 10 et 12 sont toujours rendus dans un brief complet.
- Le champ 5 est rendu dans tout traitement actif ; les champs 3, 4 et 6 à 9 et 11 sont conditionnels selon les règles précisées.
- Aucun champ vide, `null`, inventé ou rempli par une généralité théorique.
- Les formulations décrivent conduites, contextes et effets ; elles évitent intentions supposées, traits réifiés et vocabulaire moralisant.

## 7. Filtre ACT conditionnel

Il n'existe aucun champ ACT permanent et aucune conceptualisation ACT parallèle par défaut.

Une question ou option ACT ne peut apparaître que si les six conditions sont réunies :

1. des données individuelles soutiennent un processus pertinent, par exemple évitement expérientiel, fusion, conflit avec des valeurs ou difficulté d'action engagée ;
2. le processus apporte une information ou une option qui n'est pas déjà suffisamment représentée par l'analyse cognitive ou comportementale ;
3. il est relié à un objectif actif ;
4. il modifie une question, une prédiction, un test ou une intervention ;
5. compétence du clinicien, consentement, cadre et vigilances permettent l'option ;
6. il s'intègre au même graphe de mécanismes et conserve son statut hypothétique.

**Sources :** *Learning ACT*, 2e éd., introduction, pp. 3–12 ; PDF pp. 15–24, présente l'ouvrage comme compagnon de formation plutôt que recette ; Eells, chap. 13, pp. 380–409 ; PDF pp. 393–422, montre qu'ACT constitue un cadre fonctionnel complet ; les pièges de mise en œuvre sont discutés dans *Learning ACT*, pp. 385–389 ; PDF pp. 397–401.

L'extension est masquée ou abandonnée si le processus n'est pas confirmé, n'apporte pas de valeur décisionnelle, détourne d'une priorité de sécurité ou d'un déficit direct, rigidifie le travail, dégrade l'alliance ou ne montre pas d'utilité malgré une mise en œuvre adéquate.

## 8. Garde-fous obligatoires

1. **Identité minimisée.** Utiliser un identifiant pseudonymisé ; aucun nom de personne suivie ou de tiers dans le brief, les exemples ou les exports d'analyse.
2. **Temporalité explicite.** Date de coupure, dernière source et période de chaque tendance toujours visibles.
3. **Non-mention ≠ absence.** Ne jamais conclure à stabilité, sécurité ou non-réalisation sans donnée explicite.
4. **Proposition ≠ décision.** Toute suggestion porte `proposition_systeme` et nécessite validation.
5. **Théorie ≠ fait individuel.** Un passage de manuel peut suggérer une question, jamais remplir une formulation personnelle.
6. **Diagnostic ≠ mécanisme ≠ plan.** Aucun déclenchement automatique de protocole ou de technique à partir du diagnostic ou de mots-clés.
7. **Contradictions conservées.** Ne pas résoudre automatiquement par moyenne, récence ou détail apparent.
8. **Hypothèses versionnées.** Afficher pour, contre, alternative et test ; une hypothèse abandonnée reste dans l'historique mais disparaît de la vue courante.
9. **Mesures proportionnées.** Instrument, version, langue, licence, population et finalité doivent être connus ; ne pas reproduire d'items protégés sans droit.
10. **Charge minimale.** Ne montrer que les éléments susceptibles de changer la séance ; ne pas importer une batterie de recherche dans la pratique courante.
11. **Sécurité hors automatisation.** Le corpus ne définit pas à lui seul les procédures contemporaines d'urgence, de violence, de maltraitance, de pharmacovigilance ou d'incapacité. Les règles locales et le jugement professionnel priment.
12. **Compétence et consentement.** Une intervention spécialisée ou expérientielle ne doit pas être proposée sans indication, compétence, cadre, préférences et vigilances suffisants.
13. **Validation avant conservation.** Distinguer brouillon généré, validation clinique et promotion sélective dans le dossier ; conserver auteur, date et version des corrections.
14. **Pas de mise à jour depuis le brief.** Toute modification se fait dans le registre source puis est reprojetée.

## 9. Squelette non rempli

```text
PRÉPARATION DE LA PROCHAINE SÉANCE — [identifiant interne pseudonymisé]
Séance prévue : [...] | Généré le : [...] | Données jusqu'au : [...]
Dernière séance exploitable : [...] | Couverture/limites critiques : [...]

1. CADRE ET FRAÎCHEUR DES DONNÉES
[sources incluses, période, lacunes et portée]

2. VIGILANCES PRIORITAIRES
[fait daté | statut actuel ou inconnu | dernière évaluation | action documentée]

3. CHANGEMENTS CLINIQUEMENT PERTINENTS
[changement | période | source | conséquence possible]

4. CONTINUITÉ DE LA DERNIÈRE SÉANCE
[travail réellement effectué | apprentissage | décision | point à reprendre]

5. OBJECTIFS ACTIFS ET PROGRESSION
[objectif référencé | indicateur | dernière donnée | statut/révision]

6. TÂCHES INTERSÉANCES À REVOIR
[tâche convenue | cible | résultat documenté/inconnu | apprentissage/obstacle]

7. MESURES À INTERPRÉTER OU RECUEILLIR
[instrument/version | construit | points comparables | tendance/limite | motif]

8. FOYER FONCTIONNEL ET CONCEPTUEL ACTUEL
[épisode(s) | mécanisme hypothétique | pour/contre | alternative | objectif lié]

9. QUESTIONS CLINIQUES À VÉRIFIER
[question neutre | origine | décision dépendante | donnée attendue]

10. PRIORITÉS ET AGENDA PROPOSÉS
[priorité | motif | source | prérequis] — statut : `proposition_systeme`

11. OPTIONS D'INTERVENTION CONDITIONNELLES
[option | cible/objectif | conditions | données manquantes | indicateur] — `proposition_systeme`

12. PROVENANCE ET LIMITES
[assertion → statut épistémique → objet source → séance/document → date → locateur → version]
[contradictions, lacunes, limites de mesure/théorie et statut de validation]
```

Les rubriques conditionnelles sans contenu utile sont supprimées au rendu. Le squelette sert à vérifier l'architecture, non à imposer douze blocs visibles à chaque séance.

## 10. Critères d'acceptation du brief généré

Un brief est acceptable seulement si :

- l'identifiant pseudonymisé, la date de coupure, la dernière source et la version sont connus ;
- les champs 1, 2, 10 et 12 sont présents ; le champ 5 l'est pour un traitement actif ;
- chaque fait important a une provenance retrouvable et chaque synthèse indique sa période ;
- chaque hypothèse est séparée des faits, reliée à des éléments pour/contre et à une vérification possible ;
- les contradictions susceptibles de changer la séance sont visibles ;
- aucun champ n'est rempli par vraisemblance, théorie générale ou diagnostic seul ;
- objectifs, tâches, mesures, vigilances et formulation renvoient à leurs registres d'autorité ;
- une tâche sans résultat documenté n'est pas présentée comme non réalisée ;
- une tendance n'est produite qu'à partir de données comparables ;
- chaque priorité d'agenda montre son motif et conserve `proposition_systeme` ;
- chaque option d'intervention est liée à un objectif, une cible, des prérequis, l'historique de réponse et un indicateur ;
- les limites critiques sont visibles au point d'usage, pas seulement en annexe ;
- les seuils de parcimonie sont respectés ou leur dépassement justifié ;
- aucune information nominative n'apparaît ;
- le langage reste descriptif, professionnel et non péjoratif ;
- le document n'a mis à jour aucun objet longitudinal et son statut de validation est explicite.

## 11. Abstention, génération limitée et refus

### 11.1 Omission ciblée d'un champ

Omettre un champ facultatif, sans refuser tout le brief, lorsque :

- aucune donnée pertinente n'existe ;
- l'information n'a pas de conséquence sur la séance ;
- la source est trop faible pour soutenir l'assertion ;
- une option dépend d'une évaluation ou d'une compétence non disponible ;
- le seuil de parcimonie serait dépassé sans valeur ajoutée.

L'omission est préférable à une généralité. Une lacune n'est matérialisée que si elle change une décision.

### 11.2 Génération limitée

Produire un brief explicitement limité lorsque l'identité et la période sont sûres, mais que certaines sources manquent. Le document doit alors :

- annoncer la lacune au champ 1 ;
- éviter les conclusions sur changement ou progression ;
- convertir les inconnues décisionnelles en questions ;
- proposer d'abord actualisation, clarification ou revue des engagements ;
- supprimer les options d'intervention non fondées.

### 11.3 Refus de génération complète

Ne pas produire un brief clinique ordinaire lorsque :

1. les données de plusieurs personnes ou épisodes de soin risquent d'être mélangées ;
2. l'identifiant pseudonymisé, la période ou la date de coupure ne peuvent être établis ;
3. la provenance d'une information déterminante est introuvable ou l'extraction est manifestement corrompue ;
4. des contradictions critiques de temporalité, d'identité ou de sécurité ne peuvent être rendues sans créer une conclusion trompeuse ;
5. la demande exige une conclusion de sécurité, un diagnostic certain ou un plan de traitement à partir de sources insuffisantes ;
6. l'agenda spécifique dépend d'une évaluation actuelle absente et qu'une simple clarification ne suffit pas ;
7. le système ne peut pas empêcher l'exposition d'informations nominatives ou de données d'un tiers non nécessaire ;
8. la génération contournerait une procédure professionnelle, une validation ou une responsabilité requise.

Le refus doit être informatif : nature de la limite, conséquence clinique, données ou validation nécessaires et prochaine action sûre. En présence d'une situation potentiellement urgente, le système ne produit ni conclusion rassurante ni séance TCC ordinaire ; il renvoie au dispositif professionnel de sécurité applicable.

## 12. Conclusion

La structure recommandée n'est pas un résumé du dossier. Elle met en avant ce qui peut réellement changer la prochaine rencontre : qualité des données, vigilances, changements, engagements, objectifs, tâches, mesures, mécanismes, inconnues, agenda et options conditionnelles. La provenance rend cette compression contrôlable.

Le choix le plus parcimonieux consiste à maintenir les objets cliniques dans leurs registres d'autorité et à générer le brief comme projection datée. Beck soutient le shell de séance et la continuité ; Persons, Kuyken et Eells gouvernent la formulation révisable et la distinction données–inférences ; Antony–Barlow et Bouvard/Cottraux gouvernent l'évaluation et la mesure ; Bouvet distingue stratégie et technique ; Leahy structure la bibliothèque d'interventions ; ACT reste une extension conditionnelle. Cette répartition évite qu'un modèle unique, un diagnostic ou un catalogue de techniques ne prenne le contrôle du raisonnement clinique.
