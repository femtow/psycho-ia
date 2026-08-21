# Principes transversaux de génération clinique

**Phase :** règles de conception avant schémas JSON et avant RAG  
**Date :** 17 août 2026  
**Portée :** documents internes d'aide au raisonnement et contenus éventuellement promus, après validation, dans le dossier patient

## 1. Contrat général

Le système doit produire le document le plus simple qui conserve l'information nécessaire pour comprendre, décider, suivre, tester et rester vigilant.

Il ne doit jamais :

- compléter un template par vraisemblance ;
- transformer une théorie générale en fait individuel ;
- transformer une hypothèse répétée en fait ;
- masquer une contradiction ;
- déduire une absence d'une non-mention ;
- confondre une proposition de l'IA avec une décision clinique ;
- augmenter la complexité théorique sans gain décisionnel.

## 2. Fondement dans le corpus

### SOURCE

- Persons traite la formulation comme une hypothèse continuellement testée par l'évaluation, l'intervention et le suivi (*The Case Formulation Approach to Cognitive-Behavior Therapy*, chap. 1 et 9-10).
- Kuyken, Padesky et Dudley demandent de commencer au niveau descriptif, de n'ajouter une explication transversale ou longitudinale que si elle aide les objectifs, et de modifier le modèle lorsque les données le contredisent (*Collaborative Case Conceptualization*, chap. 2, pp. 27-51).
- Eells distingue information descriptive et signification personnelle, observation et inférence, simplicité et complexité ; une formulation utile tôt reste nécessairement incomplète (*Handbook of Psychotherapy Case Formulation*, 3e éd., chap. 1, pp. 2-4 et 22-25).
- Beck fait de la conceptualisation, du suivi de l'intervalle, de l'agenda, des objectifs, des plans d'action et du feedback des composantes reliées du traitement (*Cognitive Behavior Therapy: Basics and Beyond*, 3e éd., chap. 2-3 et 8-11 ; EPUB sans pagination stable).

### SYNTHÈSE

Une génération rigoureuse doit séparer les données, leur compression descriptive, les hypothèses explicatives et les décisions. La qualité d'une formulation ne vient pas du nombre de concepts mais de sa capacité à organiser des données, générer des prédictions et guider une action révisable.

### PROPOSITION POUR NOTRE SYSTÈME

Appliquer les règles suivantes au niveau de chaque assertion, et non au niveau global d'un document.

Les balises éditoriales **SOURCE**, **SYNTHÈSE** et **PROPOSITION POUR NOTRE SYSTÈME** indiquent le rapport d'un énoncé au corpus bibliographique ; elles ne sont pas des statuts épistémiques appliqués aux données cliniques. De même, `proposition_systeme` est un statut d'action, distinct des quatre statuts définis ci-dessous.

## 3. Les quatre statuts épistémiques

### 3.1 `explicite`

Information directement soutenue par une source clinique identifiable.

Exemples de sources admissibles :

- déclaration documentée ;
- comportement observé et consigné ;
- score à un instrument identifié ;
- événement rapporté avec sa date ou période ;
- décision ou accord effectivement documenté.

Règles :

- conserver qui rapporte ou observe, quand et dans quel contexte ;
- distinguer événement et date de documentation ;
- conserver les négations : « nie X à cette date » ne signifie pas « X n'existe jamais » ;
- une reformulation qui ajoute cause, intention, fréquence ou généralité ne reste pas `explicite` ;
- un projet de séance ne prouve pas qu'une intervention a été réalisée.

### 3.2 `synthese_prudente`

Regroupement fidèle de plusieurs éléments explicites, sans ajout causal majeur.

Admis :

- résumer une évolution sur une période définie ;
- regrouper plusieurs manifestations sous une description neutre ;
- signaler une régularité descriptive ;
- condenser des décisions cohérentes.

Exigences :

- lier toutes les données importantes qui la soutiennent ;
- indiquer la période couverte ;
- conserver les exceptions et contradictions susceptibles de changer le sens ;
- ne pas utiliser une tendance si les points ne sont pas comparables.

### 3.3 `hypothese_clinique`

Interprétation plausible, causale, fonctionnelle ou théorique, non établie.

Une hypothèse utile contient :

- formulation précise ;
- problème(s) qu'elle cherche à expliquer ;
- éléments pour ;
- éléments contre ou exceptions ;
- hypothèses alternatives ;
- niveau de confiance qualitatif si ce choix est retenu ;
- prédiction ou question permettant de la tester ;
- conséquence clinique possible ;
- version, date et état de cycle de vie.

Une formulation élégante ou un accord partagé ne valide pas l'hypothèse. Une amélioration après intervention peut la soutenir, mais n'établit pas à elle seule une causalité spécifique.

### 3.4 `inconnu_a_explorer`

Information absente ou insuffisante dont la clarification pourrait modifier compréhension, sécurité, objectif, intervention ou prochaine séance.

Règles :

- ne matérialiser que les inconnues décisionnelles ;
- préciser pourquoi la donnée serait utile ;
- transformer si possible l'inconnue en question neutre ;
- supprimer ou archiver l'inconnue lorsqu'elle n'est plus pertinente ;
- ne jamais remplir avec une valeur « probable ».

Une absence décorative est omise ; elle ne génère pas un champ `null`.

## 4. Statut épistémique et statut d'action sont distincts

Les quatre statuts précédents qualifient ce que le système affirme sur la situation clinique. Ils ne suffisent pas à qualifier une action.

**PROPOSITION POUR NOTRE SYSTÈME :** ajouter un statut d'action séparé :

- `proposition_systeme` : option générée, non validée ;
- `option_clinicien` : option retenue pour discussion ou examen ;
- `decision_clinicien` : décision professionnelle documentée ;
- `decision_conjointe` : décision négociée et documentée ;
- `realise` : action effectivement menée ;
- `abandonne_ou_modifie` : décision révisée avec motif.

Ainsi, « envisager une exposition » n'est ni un fait clinique ni une intervention réalisée. Ses justifications conservent leurs statuts épistémiques ; l'option conserve son statut d'action.

## 5. Règles de provenance

Chaque assertion importante doit permettre le trajet :

`assertion → élément clinique source → séance/document → date → localisation`.

Pour la connaissance théorique :

`élément clinique → auteur → ouvrage → chapitre/section → page si fiable`.

La provenance minimale comprend :

- identifiant stable de la source ;
- type de source ;
- date ou période ;
- localisation suffisamment précise ;
- version de l'extraction ou du document ;
- relation de support : direct, synthétique, contradictoire ou contextuel.

La citation doit soutenir exactement l'assertion. Un lien vers une séance entière n'est pas une traçabilité suffisante si aucune localisation ne permet de retrouver le passage.

## 6. Séparer théorie, hypothèse individuelle et relation étayée

| Niveau | Exemple abstrait | Stockage |
|---|---|---|
| principe théorique | un comportement peut être renforcé par une conséquence immédiate | bibliothèque théorique |
| hypothèse individuelle | cette conséquence pourrait maintenir ce comportement dans ce contexte | conceptualisation, `hypothese_clinique` |
| relation provisoirement soutenue | plusieurs épisodes et tests concordent avec cette fonction | hypothèse renforcée, jamais convertie automatiquement en fait causal |

La récupération d'un passage théorique ne doit jamais préremplir la conceptualisation d'une personne. Elle peut seulement proposer une question, un modèle candidat ou une intervention à examiner.

## 7. Gestion des informations absentes

Le système doit distinguer :

- **absent documenté** : négation ou évaluation explicite, datée et limitée à son contexte ; l'assertion porte `explicite` ;
- **non mentionné** : aucune conclusion possible et aucun nouveau statut ;
- **donnée attendue mais indisponible** : lacune de source ou d'import, enregistrée dans la qualité des données et promue en `inconnu_a_explorer` seulement si elle est décisionnelle ;
- **inconnu à explorer** : libellé fonctionnel correspondant au statut canonique `inconnu_a_explorer` ;
- **non applicable** : indicateur d'applicabilité du champ, non statut épistémique.

Comportement de génération :

1. omettre les champs sans utilité ;
2. signaler les lacunes qui limitent le document ;
3. ne poser une question que si la réponse pourrait changer une décision ;
4. ne jamais imputer la non-réalisation d'une tâche lorsque seul son résultat manque ;
5. ne jamais conclure à la stabilité parce qu'aucun changement n'est consigné.

## 8. Contradictions et temporalité

Une contradiction ne doit pas être résolue automatiquement par moyenne, préférence pour la source la plus récente ou sélection du passage le plus détaillé.

Conserver :

- les deux assertions ;
- leur source, date et contexte ;
- la nature possible de la différence : évolution, contexte, informateur, ambiguïté ou erreur ;
- l'impact éventuel sur le plan ;
- une question de clarification si utile.

Une information récente n'annule une information antérieure que si elle documente une évolution ou une correction. Le système doit toujours afficher la **date de coupure** de ses synthèses.

## 9. Conceptualisation évolutive

### Déclencheurs de révision

- nouvelles données significatives ;
- événement ou changement de contexte ;
- résultat contraire à une prédiction ;
- absence de progrès attendu ou aggravation ;
- effets indésirables ;
- divergence sur problèmes, objectifs ou tâches ;
- hypothèse alternative plus simple ou mieux soutenue ;
- nouvelle information diagnostique ou médicale pertinente.

### Révision autorisée

- renforcer ou affaiblir une hypothèse ;
- ajouter une alternative ;
- scinder un mécanisme trop général ;
- revenir d'une explication longitudinale à une description plus sobre ;
- abandonner ou remplacer le modèle ;
- modifier cible, intervention ou mesure.

### Historique obligatoire

Conserver version, date, auteur/validateur, motif, données déclenchantes et conséquences sur le plan. Une nouvelle version ne doit pas effacer les données contradictoires ni réécrire rétrospectivement l'ancienne hypothèse.

## 10. Principe de parcimonie clinique

Un champ ou une assertion n'est admis que s'il remplit au moins une fonction :

- comprendre un problème ;
- influencer une décision ;
- préparer une séance ;
- suivre une évolution ;
- tester une hypothèse ;
- soutenir une vigilance ;
- conserver une information utile qui serait autrement perdue.

Test d'inclusion :

1. Quelle décision ou action cette information peut-elle changer ?
2. Existe-t-elle déjà dans une source de vérité ?
3. Peut-elle être extraite avec une fiabilité acceptable ?
4. Son statut épistémique peut-il être rendu clairement ?
5. Son bénéfice dépasse-t-il le risque de surinterprétation et la charge de maintenance ?

Si aucune réponse satisfaisante n'existe, ne pas créer le champ.

## 11. Profondeur graduée de la formulation

**SOURCE :** Kuyken et al. recommandent de partir du niveau le moins inférentiel suffisant ; Eells souligne la tension entre observation et inférence.

**PROPOSITION POUR NOTRE SYSTÈME :**

1. **descriptif** : problèmes, impacts, forces et faits ;
2. **transversal fonctionnel** : situations, réponses, conséquences et cycles de maintien actuels ;
3. **mécanisme théorique** : cognition, apprentissage, émotion ou processus candidat ;
4. **longitudinal** : vulnérabilités et origines possibles.

Les niveaux 1 et 2 constituent le socle. Les niveaux 3 et surtout 4 sont ajoutés seulement lorsqu'ils améliorent une prédiction, un objectif, une adaptation ou la résolution d'une impasse.

## 12. Place secondaire et conditionnelle de l'ACT

### SOURCE

*Learning ACT*, 2e éd., présente l'ACT comme une approche fonctionnelle organisée autour de processus de flexibilité psychologique et d'une conceptualisation spécifique (chap. 1-8). Le chapitre ACT d'Eells illustre qu'il s'agit d'un cadre de formulation à part entière, et non d'une simple liste de techniques (chap. 13, pp. 380-409 ; PDF pp. 393-422).

### SYNTHÈSE

Ajouter systématiquement les six processus ACT créerait une seconde grille, augmenterait les données manquantes et favoriserait une conceptualisation pilotée par le modèle plutôt que par le cas.

### PROPOSITION POUR NOTRE SYSTÈME

Un concept ACT n'est affiché que si :

1. des données individuelles le rendent plausible ;
2. il ajoute une compréhension ou une option clinique non redondante ;
3. il est relié à un objectif actif ;
4. il modifie une question, un test ou une intervention ;
5. il s'intègre dans le même graphe de mécanismes au lieu de créer une formulation parallèle.

Exemples de déclencheurs possibles, jamais suffisants à eux seuls : évitement expérientiel documenté, fusion avec certaines cognitions, conflit entre conduites et valeurs, difficulté d'action engagée. Il n'existe aucun champ ACT obligatoire.

## 13. Règles de génération par étape

### Étape 1 - Délimiter

- définir la fonction, le destinataire, la date de coupure et les sources autorisées ;
- vérifier que la préparation de séance ne prétend pas être une évaluation actuelle exhaustive.

### Étape 2 - Extraire

- produire des unités explicites avec dates et provenance ;
- préserver négations, incertitudes et informateurs ;
- détecter les sources manquantes ou incomplètes.

### Étape 3 - Consolider

- résoudre les doublons textuels sans supprimer les versions cliniquement différentes ;
- ordonner temporellement ;
- mettre à jour les registres uniques.

### Étape 4 - Synthétiser

- regrouper seulement ce qui est cohérent ;
- conserver période, exceptions et contradictions ;
- limiter chaque synthèse à sa fonction documentaire.

### Étape 5 - Formuler des hypothèses

- séparer les données, la relation suspectée et le mécanisme théorique ;
- documenter pour/contre, alternative et test ;
- préférer une question neutre à une conclusion prématurée.

### Étape 6 - Proposer

- relier toute option à un objectif et une cible ;
- indiquer conditions, prérequis, vigilances et données manquantes ;
- limiter les options ;
- marquer `proposition_systeme`.

### Étape 7 - Vérifier

- contrôler fidélité aux sources, statut, temporalité, contradictions et duplication ;
- rechercher tout passage affirmatif sans preuve ;
- vérifier que le langage est professionnel, descriptif et non péjoratif ;
- obtenir la validation clinique requise.

## 14. Seuils de refus ou d'abstention

Le système doit s'abstenir d'une synthèse ou d'une proposition spécifique lorsque :

- la source indispensable manque ou est trop ancienne pour la question ;
- plusieurs sources importantes se contredisent sans résolution ;
- l'extraction est ambiguë ;
- une cause est inférée d'une seule cooccurrence ;
- une intervention dépend d'une évaluation non disponible ;
- la proposition relève d'un protocole de sécurité non défini ;
- l'incertitude ne peut pas être communiquée sans risque de confusion.

L'abstention doit être informative : données manquantes, conséquence de la limite et prochaine vérification possible.

## 15. Langage clinique

- décrire conduites, contextes et effets plutôt que traits réifiés ;
- éviter « manipulateur », « résistant », « non compliant » ou formulations moralisantes sans analyse ;
- préférer « obstacle documenté », « accord partiel », « résultat non documenté », « hypothèse à vérifier » ;
- ne pas attribuer d'intention sans donnée explicite ;
- conserver les mots de la personne lorsque leur précision clinique est utile, sans exposer de données nominatives ;
- minimiser les informations sur des tiers.

## 16. Validation et promotion dans le dossier

Trois états documentaires doivent rester distincts :

1. **brouillon généré** : aide interne, non validée ;
2. **validé par le clinicien** : contenu contrôlé, utilisable pour le raisonnement ;
3. **promu au dossier** : contenu explicitement sélectionné pour conservation, avec auteur, date et version.

Une correction après promotion conserve l'ancienne version et son motif. Une hypothèse détaillée utile en interne n'est pas automatiquement adaptée à une sortie patient ou tierce.

### 16.1 Confirmation de la source clinique

La validite technique d'un fichier ne constitue pas une confirmation humaine.
Une transcription non vide et un JSON conforme au schema restent des productions
machine tant qu'aucun acte clinique explicite n'est lie a leur version exacte.

La confirmation V1 porte sur l'ensemble de la transcription d'une seance : le
clinicien confirme qu'elle correspond suffisamment a sa note pour etre utilisee
par Psycho IA. Elle est liee a une empreinte SHA-256, a un patient pseudonymise,
a une date de seance et a une version. Une modification ulterieure rend cette
confirmation obsolete. Une correction conserve la version machine, l'avant et
l'apres, puis exige la confirmation de la nouvelle version.

Un JSON clinique peut indiquer qu'il derive d'une transcription confirmee. Cette
relation ne signifie jamais que chaque categorie ou assertion du JSON a ete
validee individuellement. Les marqueurs `[illisible]` et
`[mot incertain : ...]` peuvent rester dans une transcription confirmee, mais ne
peuvent etre reconstruits automatiquement comme faits certains.

## 17. Contrôle qualité final

Avant de rendre un document, vérifier :

- [ ] chaque assertion importante a un statut ;
- [ ] chaque fait a une provenance retrouvable ;
- [ ] les synthèses indiquent leur période ;
- [ ] les hypothèses montrent pour, contre, alternatives et test utile ;
- [ ] les données absentes n'ont pas été inventées ;
- [ ] les contradictions importantes sont visibles ;
- [ ] aucune proposition n'est présentée comme décision ;
- [ ] les objets longitudinaux sont référencés, non dupliqués ;
- [ ] les concepts ACT sont conditionnels et non redondants ;
- [ ] le diagnostic n'a pas déterminé seul le mécanisme ou le plan ;
- [ ] les informations nominatives sont minimisées ;
- [ ] la date de coupure et les limites sont explicites ;
- [ ] le document est aussi court que sa fonction le permet.
