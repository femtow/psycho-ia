# Points à arbitrer

Ce document ne reprend pas les principes déjà tranchés par le corpus ou par la demande. Il contient uniquement les décisions pour lesquelles plusieurs solutions raisonnables subsistent.

## 1. Conservation du brief de préparation

**Problème**  
Le brief est une vue dérivée. Faut-il le régénérer à chaque ouverture ou conserver chaque version ?

**Option A - régénération uniquement**

- Avantages : aucune copie obsolète ; stockage simple ; toujours aligné sur l'état courant.
- Inconvénients : impossible de savoir exactement ce que le clinicien avait vu avant une séance ; audit et analyse des erreurs limités.

**Option B - instantané systématique à chaque génération**

- Avantages : audit complet ; reproductibilité ; comparaison entre préparation et séance réelle.
- Inconvénients : multiplication de documents sensibles ; risque qu'un ancien instantané soit pris pour l'état courant.

**Option C - régénération, avec instantané seulement à la validation ou à l'ouverture clinique**

- Avantages : compromis entre cohérence et audit ; volume maîtrisé.
- Inconvénients : nécessite de définir l'événement qui déclenche la conservation.

**Recommandation**  
Option C. Conserver l'état des identifiants sources, la date de coupure et le contenu seulement lorsque le clinicien valide le brief ou l'utilise comme préparation officielle.

## 2. Représentation de la confiance dans une hypothèse

**Problème**  
Une confiance chiffrée donne une apparence de précision ; l'absence totale de graduation rend difficile la priorisation.

**Option A - score numérique**

- Avantages : tri et suivi faciles ; permet des seuils.
- Inconvénients : fausse précision ; calibration difficile ; risque de confondre confiance et vérité.

**Option B - catégories qualitatives `faible`, `moderee`, `elevee`**

- Avantages : lisible ; utile pour prioriser ; moins pseudo-précis.
- Inconvénients : nécessite des critères communs ; peut rester subjectif.

**Option C - aucun niveau, seulement preuves pour/contre et statut**

- Avantages : oblige à regarder les données ; évite la quantification arbitraire.
- Inconvénients : comparaison et tri moins rapides.

**Recommandation**  
Option B, mais facultative et accompagnée des preuves. Interdire toute conversion automatique en pourcentage et toute règle « confiance élevée = fait ».

## 3. Liste institutionnelle d'inconnues incontournables

**Problème**  
La règle générale est tranchée : seules les inconnues susceptibles de modifier une décision deviennent `inconnu_a_explorer`. Reste à décider si une courte liste institutionnelle doit toujours être vérifiée, notamment pour la sécurité et la qualité des données.

**Option A - aucune liste fixe**

- Avantages : parcimonie maximale ; adaptation complète à chaque situation.
- Inconvénients : risque d'oublier un contrôle transversal important ; pratiques moins homogènes.

**Option B - un noyau fixe commun à tous les contextes**

- Avantages : contrôle simple et uniforme ; implémentation plus facile.
- Inconvénients : certains éléments seront inutiles dans un contexte et insuffisants dans un autre.

**Option C - petits profils institutionnels selon le contexte de soin**

- Avantages : combine contrôles obligatoires et pertinence contextuelle ; permet une gouvernance distincte de la logique clinique générale.
- Inconvénients : demande de définir, valider et maintenir les profils.

**Recommandation**  
Option C si plusieurs contextes de soin sont prévus ; sinon option B. Le contenu de cette liste relève du chantier sécurité/gouvernance, pas du corpus TCC seul.

## 4. Mode de sélection des épisodes fonctionnels

**Problème**  
Le principe « épisodes sélectionnés + cycle dérivé » est tranché. Reste à décider qui sélectionne les épisodes à conserver comme preuves de la formulation.

**Option A - sélection entièrement manuelle par le clinicien**

- Avantages : contrôle clinique maximal ; faible risque d'accumulation ou d'extraction erronée.
- Inconvénients : charge de saisie ; épisodes contradictoires ou utiles parfois oubliés.

**Option B - candidats proposés par le système, conservation après validation**

- Avantages : réduit la charge tout en gardant la décision clinique ; rend visibles épisodes représentatifs, contradictoires ou liés à un essai.
- Inconvénients : nécessite des critères explicites et une interface de validation.

**Option C - conservation automatique selon des règles prédéfinies, avec revue ultérieure**

- Avantages : continuité et exhaustivité des traces répondant aux critères.
- Inconvénients : volume, faux positifs et risque qu'un épisode non validé influence trop tôt la formulation.

**Recommandation**  
Option B. Proposer un épisode s'il est décisionnel, contradictoire, lié à une intervention, représentatif d'une régularité ou utile pour tester une hypothèse ; ne l'utiliser comme preuve consolidée qu'après validation.

## 5. Périmètre du registre de vigilances

**Problème**  
Le brief doit rappeler les vigilances, mais le corpus inspecté ne définit pas un système complet de gestion des risques.

**Option A - registre large : risques, effets indésirables, contre-indications, facteurs de déstabilisation et échéances**

- Avantages : point d'entrée unique ; faible risque d'oubli.
- Inconvénients : mélange de niveaux de gravité ; gouvernance et responsabilités complexes.

**Option B - registre limité aux éléments de sécurité immédiate**

- Avantages : forte visibilité ; périmètre clair.
- Inconvénients : autres vigilances dispersées ; définition de « immédiat » délicate.

**Option C - registre générique avec catégories et procédures séparées selon la catégorie**

- Avantages : architecture commune sans confondre les workflows ; extensible.
- Inconvénients : demande une taxonomie et des règles institutionnelles.

**Recommandation**  
Option C. Avant implémentation, arbitrer qui crée, valide, clôt et réévalue chaque catégorie. Ne pas automatiser une conclusion d'absence de risque.

## 6. Stratégie de mesures

**Problème**  
Une batterie commune facilite le suivi ; des mesures individualisées sont souvent plus proches des mécanismes et objectifs.

**Option A - batterie commune fixe à fréquence standard**

- Avantages : comparabilité ; automatisation ; détection uniforme de tendance.
- Inconvénients : charge et manque de pertinence ; risque de pilotage par le score.

**Option B - mesures entièrement choisies au cas par cas**

- Avantages : forte pertinence idiographique ; flexibilité.
- Inconvénients : hétérogénéité ; oubli de mesures globales ; maintenance complexe.

**Option C - petit noyau commun + mesures spécifiques et ipsatives ciblées**

- Avantages : combine résultat global et processus individualisé ; cohérent avec Persons, Antony/Barlow et Bouvard/Cottraux.
- Inconvénients : nécessite de choisir le noyau, les fréquences et les règles d'interprétation.

**Recommandation**  
Option C. Le choix concret des instruments doit faire l'objet d'un travail séparé tenant compte des droits d'usage, versions, populations, seuils et procédures cliniques.

## 7. Niveau d'autonomie pour les options d'intervention

**Problème**  
Le système peut se limiter à rappeler le plan actif ou proposer de nouvelles options.

**Option A - aucun ajout : uniquement rappeler les interventions déjà décidées**

- Avantages : risque minimal de suggestion inadéquate ; comportement prévisible.
- Inconvénients : aide limitée lors des impasses ou révisions.

**Option B - nouvelles options conditionnelles seulement lors d'une impasse ou d'une révision explicite**

- Avantages : aide concentrée aux moments où le plan actuel doit être réexaminé ; faible bruit en séance ordinaire.
- Inconvénients : peut manquer une option utile avant qu'une impasse soit formalisée.

**Option C - options conditionnelles possibles à chaque préparation, selon un filtre strict**

- Avantages : valeur clinique plus précoce ; toute option reste reliée à objectif, cible, données, prérequis et historique de réponse.
- Inconvénients : extraction et logique plus exigeantes ; parfois aucune option ne sera produite.

**Recommandation**  
Option B pour la première implémentation, avec possibilité d'évoluer vers C après évaluation des faux positifs. Dans les deux cas : maximum de trois options, statut `proposition_systeme` et validation obligatoire.

## 8. Déclenchement des concepts ACT

**Problème**  
Une activation trop souple rend l'ACT omniprésente ; une activation manuelle exclusive peut faire manquer un processus utile.

**Option A - activation manuelle par le clinicien**

- Avantages : contrôle maximal ; aucune injection automatique.
- Inconvénients : dépend de l'anticipation du clinicien ; un processus utile peut ne pas être examiné.

**Option B - détection comme question candidate, affichée après validation clinique**

- Avantages : rend un processus examinable sans l'introduire comme mécanisme établi ; conserve le contrôle clinique.
- Inconvénients : demande des critères de détection et peut produire des questions inutiles.

**Option C - affichage automatique seulement lorsque tout le filtre ACT est satisfait**

- Avantages : assistance plus directe tout en excluant les indices faibles et les concepts redondants.
- Inconvénients : le système évalue lui-même une plus-value théorique difficile à fiabiliser ; risque de suractivation résiduel.

**Recommandation**  
Option B. Les processus ACT utilisent les mêmes objets d'hypothèse et de plan, sans module parallèle ; aucune question candidate ne devient une hypothèse active sans validation.

## 9. Périmètre et granularité de la promotion dans le dossier

**Problème**  
Le workflow `brouillon → validation → promotion sélective` est tranché. Reste à décider quels contenus validés peuvent être promus, à quelle granularité et sous quelle responsabilité.

**Option A - promotion du document validé comme un tout**

- Avantages : geste simple ; le document promu reste lisible comme unité.
- Inconvénients : peut conserver des hypothèses ou détails internes non nécessaires au dossier.

**Option B - sélection manuelle assertion par assertion ou objet par objet**

- Avantages : minimisation maximale ; contrôle précis du contenu officiel.
- Inconvénients : charge clinique élevée ; risque d'omission ou de fragmentation du sens.

**Option C - profils de promotion par type de document, avec confirmation et ajustement manuel**

- Avantages : compromis entre charge et minimisation ; règles explicites pour faits, décisions, hypothèses et provenance.
- Inconvénients : exige une gouvernance des profils, des responsabilités et des corrections.

**Recommandation**  
Option C. Avant implémentation, définir la liste des objets ou champs promouvables, l'auteur de la validation, la règle de correction et les contenus internes exclus par défaut.

## 10. Événement qui ouvre un workflow d'impasse

**Problème**  
Un déclenchement automatique précoce peut sur-réagir ; un déclenchement entièrement manuel peut retarder la revue.

**Option A - seuils automatiques fixes**

- Avantages : détection uniforme ; rappel fiable.
- Inconvénients : seuils arbitraires ; variabilité des trajectoires et mesures.

**Option B - ouverture exclusivement manuelle**

- Avantages : jugement clinique central.
- Inconvénients : biais de confirmation et oubli possible.

**Option C - signaux automatiques non décisionnels + ouverture/validation clinique**

- Avantages : conjugue détection et jugement ; les signaux peuvent inclure aggravation, absence de progrès attendu, rupture, obstacles répétés ou divergence d'objectifs.
- Inconvénients : demande une configuration par contexte et une gestion des faux positifs.

**Recommandation**  
Option C. Le système signale et fournit les données ; le clinicien décide d'ouvrir la revue.

## Ordre recommandé des arbitrages

Avant de concevoir les schémas :

1. périmètre et gouvernance des vigilances ;
2. liste institutionnelle d'inconnues incontournables ;
3. périmètre et responsabilité de la promotion dans le dossier ;
4. mode de sélection des épisodes fonctionnels ;
5. représentation facultative de la confiance ;
6. stratégie de mesures ;
7. autonomie des suggestions et déclenchement ACT ;
8. déclencheurs du workflow d'impasse ;
9. événement qui conserve un instantané du brief.
