# Template prioritaire V1 - Analyse fonctionnelle synchronique d'un episode

**Statut :** specification clinique prealable a l'implementation

**Date :** 21 aout 2026

**Nom clinique court :** Analyse fonctionnelle d'un episode

**Unite :** une occurrence delimitee d'une situation-probleme

## 1. Decision

Le premier template clinique a developper apres les fondations actuelles est :

> **Analyse fonctionnelle synchronique d'un episode - V1**

Il organise un episode selon la sequence :

> contexte et antecedents -> reponses distinguees -> consequences immediates -> consequences differees -> fonction eventuelle a verifier.

Il ne constitue ni une conceptualisation globale, ni un diagnostic, ni un plan de traitement. Il peut rester descriptif lorsque les donnees ne permettent pas de formuler une fonction.

## 2. Pourquoi ce template est prioritaire

### 2.1 Valeur pour le clinicien

L'analyse transforme une note narrative en une carte breve d'une situation concrete. Elle aide a :

- distinguer ce qui declenche ou module l'episode ;
- separer comportement, evitement, emotion, sensation et cognition ;
- observer ce que les reponses produisent immediatement et plus tard ;
- rendre une fonction supposee explicite et testable ;
- identifier ce qui manque avant de choisir une intervention ;
- partager une comprehension precise avec la personne suivie.

### 2.2 Faisabilite avec Psycho IA aujourd'hui

Le JSON clinique V2 contient deja : faits rapportes, contextes, emotions, intensites, cognitions, comportements et evitements. La transcription confirmee permet de verifier la sequence et les formulations source. Les problemes suivis offrent une cible stable lorsqu'ils existent.

La limite actuelle est importante : les categories du JSON ne prouvent pas qu'elles appartiennent au meme episode, et les consequences ou sensations physiologiques ne possedent pas de champs dedies. La generation V1 doit donc :

- partir d'un episode delimite ;
- revenir a la source confirmee ;
- accepter des champs inconnus ;
- interdire la fusion de deux episodes par simple proximite thematique.

### 2.3 Demonstrateur du pipeline clinique

Ce document teste la chaine complete sans attendre une infrastructure supplementaire :

```text
note fictive
-> transcription confirmee
-> JSON clinique V2
-> candidat episode
-> extraction des composants proches de la source
-> hypothese fonctionnelle separee
-> document stable
-> revue clinique
```

## 3. Fondements bibliographiques et choix de conception

### 3.1 SECCA

**SOURCE BIBLIOGRAPHIQUE.** Cottraux decrit SECCA comme une grille didactique et pratique reliant `Stimulus`, `Emotion`, `Cognition`, `Comportement` et `Anticipation`. Sa partie synchronique analyse une sequence actuelle et ses relations avec l'entourage ; sa partie diachronique organise l'histoire. Source : Cottraux, *Les psychotherapies cognitives et comportementales*, 6e ed., chapitre 6, pp. 98-106, EPUB consulte directement.

**CONSEQUENCE.** Psycho IA ne doit pas appeler « SECCA » une grille qui ajouterait ou renommerait librement ses composants. Une vue SECCA peut etre produite uniquement si les donnees canoniques permettent de renseigner ses dimensions sans les forcer.

### 3.2 Analyse micro d'un probleme

**SOURCE BIBLIOGRAPHIQUE.** Bouvet distingue la conceptualisation macro de l'analyse fonctionnelle micro d'un probleme precis. L'analyse micro relie situation, cognitions, emotions, comportements et consequences ; elle recherche la fonction des elements et doit etre construite avec la personne. Source : Bouvet, *Manuel pratique de therapies comportementales, cognitives et emotionnelles*, chapitre 2, pp. 43-52, EPUB consulte directement.

**CONSEQUENCE.** Le document porte sur un episode et un probleme cible, non sur toute l'histoire. La comprehension partagee a une place conditionnelle en fin de document.

### 3.3 ABC, SORC et analyses comportementales

**SOURCE BIBLIOGRAPHIQUE.** L'analyse interne `01_cartographie_clinique.md`, section 5, rapporte que Persons examine les antecedents et consequences d'un comportement defini, y compris les reponses privees, et que la fonction doit etre determinee empiriquement. Elle rapporte aussi qu'Eells distingue relations predictives, force, direction, causalite supposee et modifiabilite. Cottraux presente SORC, SECCA et d'autres grilles comme des representations possibles de la meme tache clinique.

**LIMITE DE VERIFICATION.** Les fichiers de Persons et Eells ne sont pas presents dans `Sources/` pendant cette mission ; ces apports proviennent donc des analyses locales anterieures, et non d'une nouvelle lecture directe.

### 3.4 Synthese retenue

**SYNTHESE DE PLUSIEURS SOURCES.** Le noyau commun le plus prudent est :

1. un episode delimite ;
2. des antecedents et facteurs contextuels ;
3. des reponses differenciees ;
4. des consequences immediates ;
5. des consequences differees ;
6. une fonction seulement supposee et testable ;
7. des variations, exceptions et donnees contradictoires.

Ce noyau n'impose ni que toute emotion soit causee par une cognition, ni que toute action soit un evitement, ni qu'une carte complexe soit toujours superieure a un ABC simple.

### 3.5 Choix Psycho IA

**CHOIX DE CONCEPTION PSYCHO IA.** Le contenu canonique n'est ni une grille SECCA modifiee ni un formulaire ABC rigide. Il utilise des rubriques neutres capables de produire, si utile :

- une vue principale Psycho IA, orientee lecture clinique ;
- une vue ABC simplifiee : antecedents, comportement/reponse cible, consequences ;
- une vue SECCA conditionnelle, sans ajouter de donnees absentes ;
- plus tard, une carte fonctionnelle plus complexe si elle change reellement la decision.

Les vues ne creent pas de copies independantes de l'analyse.

## 4. Utilisateur, moment et perimetre

### 4.1 Utilisateur principal

Psychologue ou psychotherapeute TCC. Une version partageable avec la personne suivie peut etre derivee apres revue, dans un langage plus direct et sans metadonnees techniques.

### 4.2 Quand generer le document

Generer une analyse lorsqu'au moins une des conditions suivantes est remplie :

- un episode concret illustre un probleme actif ;
- une intervention doit etre reliee a une fonction supposee ;
- deux episodes semblent montrer une regularite a verifier ;
- une contradiction ou une non-reponse exige une comprehension plus precise ;
- le clinicien demande explicitement l'analyse d'une situation.

Ne pas generer automatiquement une analyse pour chaque seance ou chaque symptome.

### 4.3 Unite d'analyse

Un seul episode delimite par :

- une situation ou un contexte identifiable ;
- une periode suffisamment precise ;
- au moins une reponse documentee ;
- un probleme cible ou une raison clinique de l'analyser.

Une journee entiere, une « anxiete generale » ou plusieurs situations semblables ne forment pas un episode unique sans delimitations supplementaires.

### 4.4 Ce que le document n'est pas

- pas une anamnese ;
- pas une analyse diachronique ;
- pas une conceptualisation complete ;
- pas une preuve de causalite ;
- pas une prescription de technique ;
- pas une note de seance ;
- pas un diagnostic.

## 5. Structure clinique exacte

Le rendu principal suit toujours l'ordre ci-dessous. Les metadonnees techniques sont presentes dans les donnees du document, mais masquees dans la vue clinique ordinaire.

### Rubrique 0 - Reperes du document

**But.** Identifier l'analyse et sa portee.

| Champ | Definition | Statut | Niveau |
|---|---|---|---|
| `identifiant_analyse` | identifiant stable, non nominatif | obligatoire | technique |
| `version_document` | version de l'analyse | obligatoire | technique |
| `statut_documentaire` | brouillon genere, revu/valide, archive/remplace | obligatoire | D/technique |
| `patient_id` | identifiant pseudonymise | obligatoire | technique |
| `probleme_cible_id` | probleme suivi concerne, s'il existe | conditionnel mais recommande | D ou B valide |
| `libelle_clinique` | titre bref de la situation-probleme | obligatoire | A ou B |
| `date_episode` | date ou intervalle de l'episode | obligatoire si connue | A |
| `date_coupure` | derniere source prise en compte | obligatoire | technique |
| `sources` | references exactes, empreintes et localisations | obligatoire | technique |
| `niveau_completude` | descriptif, chaine documentee, hypothese fonctionnelle | obligatoire | derive deterministe |

**Rendu clinique.** Afficher le titre, la date de l'episode, le probleme cible et une mention breve si l'analyse est partielle. Les empreintes et chemins restent accessibles dans un volet de provenance.

### Rubrique 1 - Episode cible

**But.** Dire exactement quelle occurrence est analysee.

| Champ | Definition | Statut | Niveau |
|---|---|---|---|
| `description_breve` | une ou deux phrases proches de la source | obligatoire | A |
| `raison_de_selection` | episode decisionnel, representatif, contradictoire, lie a un essai ou demande du clinicien | obligatoire | D ou B |
| `debut_et_fin` | bornes temporelles si documentees | conditionnel | A |
| `acteurs_pertinents` | personnes ou environnement necessaires a la comprehension, minimises | conditionnel | A |
| `episode_distinct_de` | references d'episodes voisins a ne pas fusionner | conditionnel | A/B |

**Regle.** Si l'episode ne peut pas etre distingue d'au moins un autre episode de la meme source, la generation est limitee a une proposition de delimitation et n'assemble pas les composants.

### Rubrique 2 - Contexte et antecedents

**But.** Decrire ce qui precede ou module l'episode sans supposer une cause.

Sous-rubriques, dans cet ordre :

1. contexte externe : lieu, activite, personnes, evenement ;
2. antecedents immediats internes : souvenir, pensee, emotion ou sensation deja presente ;
3. facteurs contextuels : fatigue, sommeil, substances, contrainte, environnement, uniquement s'ils sont documentes ;
4. signal ou changement qui semble marquer le debut ;
5. inconnues contextuelles decisionnelles.

| Champ | Statut | Niveau attendu |
|---|---|---|
| `contexte_externe` | obligatoire si disponible | A |
| `antecedents_internes` | conditionnel | A |
| `facteurs_contextuels` | conditionnel | A ; B seulement sur plusieurs sources concordantes |
| `declencheur_suppose` | conditionnel | C |
| `contexte_a_explorer` | conditionnel | E |

**Non-inference.** Un element present avant l'episode n'est pas automatiquement un declencheur. Une histoire ancienne n'entre pas ici sauf si elle a ete activee dans cet episode.

### Rubrique 3 - Reponses pendant l'episode

**But.** Separer les classes de reponses sans imposer leur ordre causal.

#### 3.1 Comportements observables

Actions realisees ou interrompues, decrites de facon concrete. Au moins une reponse documentee, dans cette sous-rubrique ou une autre, est obligatoire.

#### 3.2 Evitements et comportements de securite

- `evitement_documente` seulement si l'action d'eviter est explicite ;
- `comportement_de_securite_documente` seulement si son usage protecteur est explicite ;
- `fonction_d_evitement_possible` reste C si elle est seulement supposee.

La forme du comportement ne suffit pas a determiner sa fonction.

#### 3.3 Emotions

Emotion, intensite, moment et formulation source. « Anxiete » ne prouve ni peur precise ni sensation physiologique.

#### 3.4 Sensations physiologiques

Sensations explicitement rapportees : tension, chaleur, rythme cardiaque percu, souffle, douleur, etc. Si rien n'est documente, la rubrique est omise ou indiquee comme inconnue seulement si cette lacune modifie l'analyse.

#### 3.5 Cognitions, images et anticipations

Pensees, interpretations, images, souvenirs actifs et predictions, en conservant les mots de la personne lorsqu'ils sont cliniquement utiles. Le degre d'adhesion n'est ajoute que s'il est documente.

#### 3.6 Reponses de l'environnement

Reaction d'autrui ou changement externe survenu pendant l'episode. Cette sous-rubrique ne remplace pas les consequences.

**Structure commune de chaque item.**

| Champ | Definition |
|---|---|
| `contenu` | formulation precise et concise |
| `moment` | avant, debut, pendant, fin ou inconnu |
| `intensite_ou_frequence` | valeur documentee, sans conversion |
| `statut` | A, B, C ou E |
| `source` | reference atomique |
| `incertitude` | ambiguite OCR, referent, temporalite ou interpretation |

### Rubrique 4 - Consequences immediates

**But.** Decrire ce qui suit rapidement une reponse et peut contribuer a sa fonction.

Ordre :

1. changements internes : emotion, sensation, pensee ;
2. changements comportementaux : poursuite, arret, retrait, repetition ;
3. changements environnementaux ou sociaux ;
4. obtention, soulagement ou evitement explicitement rapporte ;
5. couts immediats.

Chaque consequence doit etre liee a une reponse ou a la sequence entiere. La simple fin simultanee de l'episode ne prouve pas que la reponse a cause le changement.

**Obligatoire pour une chaine fonctionnelle complete.** Au moins une consequence immediate documentee ou une mention `non documentee`. Une mention absente ne devient jamais « aucun effet ».

### Rubrique 5 - Consequences differees

**But.** Rendre visible ce que la sequence produit plus tard : maintien, cout, apprentissage, repercussion ou protection possible.

| Type | Exemples de contenu admissible | Niveau |
|---|---|---|
| documente ulterieurement | activite abandonnee, conflit, soulagement durable, nouvelle tentative | A |
| regularite longitudinale | meme sequence sur plusieurs episodes valides | B |
| maintien suppose | la consequence pourrait renforcer ou maintenir la reponse | C |
| donnee manquante | effet ulterieur necessaire mais inconnu | E |

Une non-mention ulterieure ne prouve ni disparition ni absence de consequence.

### Rubrique 6 - Synthese fonctionnelle actuelle

**But.** Proposer, seulement si les donnees le permettent, ce que la reponse cible semble produire ou eviter.

Sous-rubriques exactes :

1. `reponse_cible` ;
2. `fonction_supposee` ;
3. `effet_immediat_pertinent` ;
4. `cout_ou_effet_differe_pertinent` ;
5. `donnees_en_faveur` ;
6. `donnees_en_defaveur_ou_limites` ;
7. `hypotheses_alternatives` ;
8. `prediction_testable` ;
9. `confiance_qualitative` facultative : faible, moderee ou elevee, jamais numerique.

**Regles obligatoires.**

- toute fonction est C, meme si elle parait evidente ;
- aucune fonction sans au moins une consequence pertinente ;
- toute fonction affiche au moins une limite ou une alternative raisonnable ;
- une fonction ne devient pas A par repetition dans plusieurs documents ;
- « evitement », « recherche de reassurance », « controle » ou « protection » ne sont pas deduits d'un mot-cle ;
- si les donnees ne suffisent pas, afficher : « Fonction non determinee avec les donnees disponibles ».

### Rubrique 7 - Variations, exceptions et ressources

**But.** Eviter une carte deterministe et identifier les conditions dans lesquelles l'episode change.

Champs conditionnels :

- `episode_comparable_different` ;
- `facteurs_associes_a_une_reponse_plus_souple` ;
- `ressource_mobilisee` ;
- `comportement_approche_ou_competence` ;
- `limite_de_generalisation`.

Une ressource generale n'est incluse que si elle est active dans cet episode ou utile pour comprendre sa variation.

### Rubrique 8 - Contradictions, incertitudes et donnees a explorer

**But.** Montrer ce qui empeche une conclusion plus forte.

Ordre :

1. contradictions entre sources ;
2. marqueurs OCR ou formulations ambigues ;
3. temporalite incertaine ;
4. composant fonctionnel manquant ;
5. questions factuelles a explorer ;
6. question de test fonctionnel eventuelle.

Une contradiction conserve les deux formulations, leurs sources et leurs dates. Le systeme ne moyenne pas des intensites, ne choisit pas la version la plus recente sans justification et ne transforme pas deux episodes differents en contradiction.

### Rubrique 9 - Comprehension partagee et suite clinique

**But.** Relier l'analyse au travail collaboratif sans transformer une suggestion en decision.

| Champ | Statut | Niveau |
|---|---|---|
| `formulation_partagee_documentee` | ce que le clinicien et la personne ont explicitement retenu | conditionnel, D/A |
| `accord_ou_desaccord` | accord, reserve ou autre comprehension documentee | conditionnel, A/D |
| `question_a_verifier_ensemble` | question proposee ou retenue | conditionnel, E ou D |
| `implication_clinique_possible` | option reliee a l'hypothese | conditionnel, C + statut d'action |
| `decision_clinique` | essai, mesure ou travail effectivement choisi | conditionnel, D |

La rubrique peut etre absente dans un brouillon genere avant discussion. Une implication possible ne doit pas etre rendue comme une decision.

## 6. Champs obligatoires et niveaux de completude

### 6.1 Minimum valide : `descriptif`

Le document peut etre genere si les elements suivants existent :

- episode cible suffisamment delimite ;
- probleme ou raison clinique ;
- contexte ou antecedent disponible ;
- au moins une reponse documentee ;
- provenance exacte ;
- limites et champs manquants.

Il ne porte alors aucune fonction.

### 6.2 Niveau `chaine_documentee`

Le niveau est atteint si, en plus :

- l'ordre temporel est suffisamment clair ;
- au moins une consequence immediate est documentee ;
- les composants appartiennent au meme episode.

### 6.3 Niveau `hypothese_fonctionnelle`

Le niveau est atteint si, en plus :

- une fonction est formulee comme hypothese ;
- les donnees pour et les limites/contre-donnees sont explicites ;
- une alternative est examinee ;
- une prediction ou question de test est formulee.

Ce niveau n'est pas un label de qualite superieur. Une description fidele est preferable a une fonction speculative.

## 7. Sources cliniques attendues

### 7.1 Sources admissibles en V1

Par ordre de proximite :

1. transcription de seance confirmee et liee a son empreinte ;
2. JSON clinique V2 derive de cette transcription ;
3. objet longitudinal valide pertinent ;
4. autre seance confirmee si elle documente une consequence differee ou une variation ;
5. mesure ou auto-observation validee, lorsque sa provenance est disponible.

Une synthese longitudinale peut aider a retrouver une source, mais elle ne doit pas etre l'unique preuve d'un composant d'episode si la source primaire est accessible.

### 7.2 Granularite de provenance

Chaque composant conserve : patient pseudonymise, date de seance, fichier et empreinte, categorie JSON ou passage source, version et nature du support (`soutient`, `contredit`, `contextualise`).

Une date de seance seule n'est pas une provenance suffisante.

## 8. Regles de generation

### 8.1 Sequence obligatoire

1. verifier l'admissibilite et la fraicheur des sources ;
2. identifier un ou plusieurs candidats episodes ;
3. choisir ou faire confirmer un seul episode ;
4. extraire les composants directement documentes ;
5. ordonner sans inventer les liens temporels ;
6. rechercher consequences immediates et differees dans les sources admissibles ;
7. isoler les contradictions et incertitudes ;
8. produire d'abord la version descriptive ;
9. ajouter une synthese B seulement si plusieurs faits la soutiennent ;
10. ajouter une fonction C seulement si les criteres de la section 6.3 sont remplis ;
11. produire une vue clinique breve et une provenance detaillee separee ;
12. soumettre le document a la revue clinique avant qu'il alimente une conceptualisation.

### 8.2 Selection de l'episode

Recommandation V1 : le systeme propose au maximum trois candidats, chacun avec date, description et raison de selection. Le clinicien confirme un candidat ou delimite manuellement l'episode. Une proposition non confirmee reste un brouillon et ne devient pas preuve consolidee.

### 8.3 Regroupement autorise

Deux items peuvent etre relies au meme episode seulement si au moins un indice les rattache :

- meme contexte explicite ;
- meme repere temporel ;
- enchainement explicite dans la note ;
- referent non ambigu ;
- confirmation clinique.

Une similitude de theme ou de vocabulaire ne suffit pas.

### 8.4 Parcimonie

- une a trois reponses cibles principales ;
- consequences les plus decisionnelles ;
- une fonction principale, exceptionnellement deux si elles sont distinctes et etayees ;
- maximum trois hypotheses alternatives ;
- maximum cinq donnees a explorer, ordonnees par impact clinique.

## 9. Regles de non-inference

Le generateur ne doit jamais :

1. diagnostiquer a partir de l'episode ;
2. inventer une sensation physiologique a partir d'une emotion ;
3. deduire une emotion d'un comportement visible ;
4. deduire une pensee automatique d'un diagnostic ou d'un schema theorique ;
5. appeler « evitement » toute absence, pause ou sortie ;
6. appeler « comportement de securite » une action sans fonction protectrice etayee ;
7. attribuer une intention a la personne ou a un tiers ;
8. confondre antecedent temporel et cause ;
9. confondre soulagement et preuve de renforcement sans prudence ;
10. transformer une consequence a court terme en maintien a long terme sans donnees ;
11. reconstruire un mot incertain de l'OCR ;
12. considerer une non-mention comme absence, resolution ou non-realisation ;
13. choisir une intervention ou un protocole sans decision clinique ;
14. generaliser un episode unique a tout le probleme ;
15. fusionner des episodes de dates ou contextes differents.

## 10. Gestion de l'incertitude

### 10.1 Types d'incertitude

- **source :** OCR incertain, rature, passage incomplet ;
- **referent :** pronom ou personne non identifiable ;
- **temporalite :** ordre des composants non clair ;
- **appartenance :** doute sur le fait que deux items appartiennent au meme episode ;
- **mesure :** intensite ou frequence non comparable ;
- **inference :** fonction ou lien causal insuffisamment etaye.

### 10.2 Rendu

Dans le corps clinique, utiliser :

- « Donnee source incertaine » ;
- « Ordre temporel a confirmer » ;
- « Appartenance au meme episode a verifier » ;
- « Fonction non determinee » ;
- « Hypothese a verifier ».

Ne pas afficher un code technique seul. La provenance detaillee conserve le type exact d'incertitude.

## 11. Gestion des contradictions

1. verifier d'abord qu'il s'agit du meme episode et du meme moment ;
2. conserver chaque assertion avec sa source ;
3. distinguer variation reelle, correction, difference d'informateur et contradiction non resolue ;
4. ne jamais choisir arbitrairement une version ;
5. limiter la synthese aux elements non contradictoires ;
6. si la contradiction modifie la fonction, retirer l'hypothese ou la presenter comme faible ;
7. transformer la contradiction en question clinique seulement si sa resolution peut modifier une decision.

## 12. Presentation clinique

### 12.1 Vue principale

Format vise : une page dans la majorite des cas, deux pages maximum pour une analyse complete.

Ordre visuel :

1. titre et episode ;
2. chaine fonctionnelle en cinq blocs ;
3. hypothese a verifier ;
4. variations et ressources ;
5. donnees a explorer ;
6. comprehension partagee et decision, si disponibles.

Les listes courtes sont preferees aux paragraphes. Les formulations sources utiles peuvent etre entre guillemets, sans longue citation. Les noms et details de tiers sont minimises.

### 12.2 Taille cible

- 250 a 500 mots pour une analyse ordinaire ;
- 8 a 15 items cliniques principaux ;
- provenance technique hors corps principal ;
- aucun paragraphe generique de conclusion.

### 12.3 Variante ABC

Vue facultative, generee a partir des memes champs :

- A : contexte et antecedents ;
- B : reponse cible et autres reponses ;
- C : consequences immediates et differees.

La fonction supposee reste sous la grille, comme hypothese separee.

### 12.4 Variante SECCA

Vue facultative seulement si elle aide le clinicien :

- Stimulus ;
- Emotion ;
- Cognition ;
- Comportement ;
- Anticipation.

Les consequences et la fonction restent presentes en dessous, car elles appartiennent au noyau fonctionnel Psycho IA. Cette vue doit etre nommee « vue SECCA » et non presenter le template entier comme une reproduction canonique de la grille de Cottraux.

## 13. Exemple fictif complet

### Analyse fonctionnelle d'un episode - trajet en transport

**Episode cible**

Le 3 septembre 2026, une personne fictive entreprend un trajet en bus pour se rendre a un rendez-vous. Cet episode a ete choisi parce qu'il associe une forte anxiete initiale, un comportement de protection et la poursuite du trajet.

**Contexte et antecedents**

- Bus plus frequente que prevu au moment de la montee.
- Anxiete rapportee a `7/10` avant le depart.
- Pensee rapportee : « Si l'angoisse monte, je vais devoir descendre. »
- Fatigue, sensations physiques anterieures et experience des trajets precedents non documentees pour cet episode.

**Reponses pendant l'episode**

- S'assoit pres de la porte et garde le telephone dans la main.
- Verifie a deux reprises l'emplacement du prochain arret.
- Rapporte de la peur et une difficulte a detourner son attention des sensations.
- Sensations physiologiques precises non documentees.
- Pensee rapportee pendant le trajet : « Je peux sortir au prochain arret si necessaire. »

**Consequences immediates**

- Rapporte un soulagement bref apres s'etre placee pres de la porte.
- Reste dans le bus jusqu'a l'arret prevu.
- Anxiete rapportee a `4/10` a l'arrivee.

**Consequences differees**

- Le trajet prevu a ete realise.
- Aucun effet sur le trajet suivant n'est documente.
- Il n'est pas possible de conclure si la baisse d'anxiete est liee au temps passe dans le bus, a la possibilite de sortir, au telephone ou a un autre facteur.

**Hypothese fonctionnelle a verifier**

Le placement pres de la porte et les verifications pourraient procurer un sentiment de controle immediat. Ils pourraient aussi limiter l'apprentissage que le trajet peut etre poursuivi sans ces moyens de protection.

Donnees en faveur : soulagement rapporte apres le placement ; pensee centree sur la possibilite de sortir.

Limites : l'anxiete diminue et le trajet est mene a son terme ; aucune comparaison sans ces comportements n'est disponible.

Alternative : la diminution peut correspondre au deroulement normal de l'episode ou a une frequentation moins forte apres le depart.

Prediction a discuter : si ces comportements jouent une fonction de protection, leur modification graduelle devrait changer le sentiment de controle, l'anxiete ou l'apprentissage rapporte. Aucun test n'est decide dans les sources.

**Variations, ressources et exceptions**

- Poursuite du trajet malgre l'anxiete initiale.
- Capacite a observer et coter l'evolution de l'anxiete.
- Absence de comparaison avec un autre trajet suffisamment similaire.

**Donnees a explorer**

1. Quelles sensations etaient presentes et a quel moment ?
2. Le telephone ou la proximite de la porte etaient-ils percus comme necessaires ?
3. Que pensait la personne qu'il arriverait si elle ne pouvait pas descendre ?
4. Comment l'anxiete a-t-elle evolue entre `7/10` et `4/10` ?

**Comprehension partagee et suite**

Aucune formulation partagee ni decision d'intervention n'est documentee. L'hypothese reste a discuter avec la personne suivie.

### Lecture epistemique de l'exemple

- Les circonstances, paroles, comportements et intensites sont A dans cet exemple fictif.
- « sentiment de controle » et maintien possible sont C.
- L'absence de donnees sur sensations et necessite percue est E.
- Aucun objectif, test ou retrait de comportement de securite n'est D.

## 14. Criteres de qualite

Une analyse est acceptable si :

- [ ] elle porte sur un seul episode delimite ;
- [ ] elle distingue contexte, reponses et consequences ;
- [ ] elle ne force pas toutes les classes de reponses ;
- [ ] chaque assertion importante a une source retrouvable ;
- [ ] les formulations source utiles sont preservees sans exposition nominative ;
- [ ] les consequences immediates et differees ne sont pas confondues ;
- [ ] tout evitement ou comportement de securite est documente ou qualifie d'hypothese ;
- [ ] toute fonction est separee des faits ;
- [ ] une hypothese fonctionnelle montre preuves, limites et alternative ;
- [ ] les contradictions restent visibles ;
- [ ] une absence d'information n'est pas transformee en reponse negative ;
- [ ] les ressources ou exceptions pertinentes sont recherchees sans etre inventees ;
- [ ] une suggestion n'apparait pas comme decision ;
- [ ] la taille reste proportionnee a la decision ;
- [ ] l'analyse peut rester descriptive sans etre consideree comme un echec.

## 15. Erreurs typiques a eviter

### 15.1 Episode trop large

Mauvais : « Quand la personne est anxieuse, elle evite. »

Correctif : choisir une occurrence, une date, un contexte et une reponse observables.

### 15.2 Categorie prise pour une fonction

Mauvais : « Regarder son telephone est un comportement de securite. »

Correctif : decrire l'action ; qualifier sa fonction seulement avec consequences et donnees concordantes.

### 15.3 Remplissage theorique

Mauvais : ajouter palpitations, croyance centrale ou peur de perdre le controle parce que le cas concerne l'anxiete.

Correctif : laisser ces dimensions absentes ou a explorer.

### 15.4 Confusion court terme / long terme

Mauvais : « Le soulagement maintient necessairement le trouble. »

Correctif : documenter le soulagement ; presenter le maintien comme hypothese et chercher les donnees longitudinales.

### 15.5 SECCA hybride non declare

Mauvais : appeler SECCA une grille qui remplace Anticipation par Consequence et ajoute des cases arbitraires.

Correctif : conserver le template canonique Psycho IA et offrir une vue SECCA fidele lorsque pertinente.

### 15.6 Intervention automatique

Mauvais : conclure « exposition recommandee » a partir d'un seul episode.

Correctif : separer implication possible, prerequis, objectif et decision clinique.

### 15.7 Apparence de collaboration

Mauvais : « Le patient est d'accord avec cette analyse » sans source.

Correctif : laisser la rubrique de comprehension partagee vide jusqu'a une discussion documentee.

### 15.8 Precision excessive

Mauvais : score numerique de confiance ou causalite forte issue d'une note breve.

Correctif : confiance qualitative facultative, preuves visibles et abstention autorisee.

## 16. Tests cliniques necessaires a la future implementation

La mission de code suivante devra au minimum couvrir des cas fictifs ou :

1. un episode complet contient antecedent, reponse et consequence ;
2. une emotion est documentee sans comportement ;
3. un comportement est documente sans consequence ;
4. deux episodes similaires ne doivent pas etre fusionnes ;
5. une consequence differee provient d'une seance ulterieure ;
6. une intensite contradictoire concerne le meme moment ;
7. deux intensites differentes concernent des moments differents et ne sont pas contradictoires ;
8. un marqueur OCR incertain touche un element central ;
9. un evitement est explicite ;
10. un comportement pourrait etre protecteur mais sa fonction n'est pas documentee ;
11. une hypothese fonctionnelle a des donnees pour et contre ;
12. aucune fonction n'est justifiee ;
13. une comprehension partagee est documentee ;
14. une option est proposee mais aucune decision n'est prise ;
15. un second lancement sans changement ne regenere pas inutilement le document.

## 17. Dependances minimales pour le developpement

Necessaires :

- sources cliniques fictives confirmees et versionnees ;
- acces au JSON V2 et a la transcription correspondante ;
- reference atomique par composant ;
- selection ou confirmation d'un candidat episode ;
- statut documentaire distinct du statut epistemique ;
- rendu stable et controles deterministes ;
- empreinte incluant sources et version du generateur/template.

Non necessaires pour une V1 utile :

- nouvelle base de donnees ;
- moteur de recherche semantique ;
- RAG ou embeddings ;
- refonte du pipeline OCR/extraction ;
- conceptualisation automatique ;
- plan de traitement automatique ;
- interface graphique complete.

## 18. References

### Sources consultees directement

- Bouvet, C., *Manuel pratique de therapies comportementales, cognitives et emotionnelles*, chapitre 2, notamment pp. 31-52 : distinction macro/micro, situation, cognitions, emotions, comportements, consequences, fonction et collaboration.
- Cottraux, J., *Les psychotherapies cognitives et comportementales*, 6e ed., chapitre 6, notamment pp. 98-106 : grilles d'analyse fonctionnelle, SORC, SECCA, partie synchronique et partie diachronique.
- Beck, J. S., *Cognitive Behavior Therapy: Basics and Beyond*, 3e ed., chapitres 2, 3, 9 et 10 : conceptualisation evolutive, planification, collaboration et structure des seances.
- Bouvard, M., et Cottraux, J., *Protocoles et echelles d'evaluation en psychiatrie et psychologie*, 5e ed., chapitres 1, 2 et 6 : mesures repetees, cas unique, mesures normatives et ipsatives.

### Sources reprises des analyses locales anterieures

- Persons, J. B., *The Case Formulation Approach to Cognitive-Behavior Therapy*, chapitre 3, pp. 42-64 / PDF 57-79.
- Kuyken, W., Padesky, C. A., et Dudley, R., *Collaborative Case Conceptualization*, chapitre 6, pp. 171-216 / PDF 190-235.
- Eells, T. D. (dir.), *Handbook of Psychotherapy Case Formulation*, 3e ed., chapitre 11, pp. 323-339 / PDF 336-352.

Ces trois references sont localisees et synthetisees dans `00_inventaire_sources.md` et `01_cartographie_clinique.md`. Leurs fichiers n'ont pas pu etre rouverts directement dans cette mission car ils ne sont pas actuellement presents dans `Sources/`.
