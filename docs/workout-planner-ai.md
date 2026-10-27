# Workout Planner : similarité, RAG et apprentissage supervisé

Les trois fonctions sont intégrées à **Workouts → My Routine**. Les nouveaux textes de l'interface sont en anglais.

## Utilisation

1. Cliquer sur **Swap** pour un exercice. Le bloc **Smart alternatives** affiche jusqu'à trois remplacements et les raisons du classement.
2. Les filtres de matériel sont appliqués aux alternatives. Le groupe musculaire principal et le niveau du profil sont des contraintes obligatoires. S'il existe moins de trois choix admissibles, l'application l'indique sans assouplir ces contraintes.
3. **Like** et **Not for me** enregistrent un retour explicite. **Use this exercise** sauvegarde réellement le programme avant d'enregistrer l'acceptation. Remplacer ou retirer ensuite un exercice précédemment accepté produit un événement neutre `replaced`, exclu des labels ML : ce changement ne prouve pas une préférence négative.
4. **Explain my routine** calcule les faits du programme, recherche les guides d'entraînement et produit une explication citée. Les références se déplient pour montrer les extraits et leurs pages.
5. **Your exercise preferences** montre l'avancement de la collecte et permet d'entraîner ou de mettre à jour le modèle personnel. L'effacement des préférences supprime les retours et le modèle, tout en conservant le programme.

## 1. Recommandation basée sur le contenu

Le catalogue est encodé par catégories : muscle principal, muscles secondaires, mouvement, matériel, difficulté et caractère composé/isolation. Le score est la similarité cosinus de ces vecteurs, avec poids 4 pour le muscle principal et 3 pour le mouvement. Le matériel et le niveau sont filtrés avant le classement. Les exercices déjà présents dans la séance sont exclus.

Ce classement est déterministe et fonctionne dès la première connexion. Le pourcentage affiché est une similarité de caractéristiques, pas une probabilité de succès ni une évaluation médicale. Aucun entraînement sur des utilisateurs n'est nécessaire pour ce classement initial.

## 2. Explication RAG

Le serveur reconstitue les noms, mouvements et muscles depuis les identifiants du catalogue ; les noms personnalisés et champs supplémentaires envoyés par le navigateur ne sont pas transmis au modèle. Les séries sont additionnées par muscle principal, sans double comptage des muscles secondaires. La recherche utilise uniquement l'index `exercise`, jusqu'à quatre passages.

Le prompt délimite le programme et les références comme des données, impose du JSON et interdit l'invention de chiffres et de références. La réponse est validée par Pydantic et chaque identifiant de citation doit exister. Cette validation garantit la structure et l'existence des références ; elle ne prouve pas automatiquement que chaque affirmation est justifiée. La relecture des extraits reste possible et nécessaire.

Si la génération échoue, les vrais extraits restent affichés, avec un message explicite. Sans documents retrouvés, seuls les faits calculés du programme sont présentés. Aucun faux texte IA ou fausse source n'est substitué. Le fournisseur existant configuré dans `backend/.env` est réutilisé ; aucun identifiant de compte, mot de passe ou clé n'est envoyé dans ce prompt.

## 3. Apprentissage supervisé complet

### Données

`exercise_recommendations` contient les alternatives proposées, leurs caractéristiques numériques, le propriétaire et son retour éventuel. Une proposition simplement affichée ou ignorée n'est jamais transformée en exemple négatif.

- `accepted`, `liked` → cible 1.
- `disliked` → cible 0.
- `replaced` → événement neutre, exclu de l’entraînement.
- Aucun retour → exclu de l'entraînement.

Le dernier événement de remplacement neutralise aussi les anciens labels de la même paire. Seul le dernier retour de chaque paire exercice initial/exercice proposé est retenu : cliquer plusieurs fois sur le même choix ne gonfle pas le jeu de données. Chaque compte entraîne son propre modèle, sans mélanger les retours des autres comptes.

### Conditions et modèle

Il faut au moins **30 paires différentes**, **5 exemples de chaque classe** et **8 exercices proposés distincts**. Ces seuils sont des garde-fous de démarrage pour un prototype, pas une garantie statistique de qualité.

Le modèle est une régression logistique régularisée (`C=0.5`, classes équilibrées, maximum 500 itérations). Ses caractéristiques incluent la similarité, les correspondances de matériel/mouvement, les attributs de l'exercice, l'objectif et le niveau. Les identifiants, noms, emails et mensurations ne sont pas des caractéristiques du modèle.

### Évaluation et déploiement

Le découpage d'évaluation réserve environ 25 % des **groupes d'exercices proposés**. Un même exercice proposé n'apparaît pas à la fois dans l'apprentissage et dans l'évaluation. Les deux classes doivent exister dans chaque partie ; sinon, l'entraînement est refusé en demandant davantage de diversité.

Les métriques enregistrées sont la balanced accuracy, la log loss, le score de Brier et les effectifs. Le modèle doit dépasser 0,5 en balanced accuracy et améliorer la log loss par rapport à une probabilité constante calculée sur la partie d'apprentissage. Sinon, le modèle actuel est conservé. Il s'agit d'une validation sur un jeu réservé ; une étude plus large devra ajouter une validation croisée et un jeu final indépendant avant toute revendication de performance générale.

Après validation, le modèle est réentraîné sur tous les retours disponibles. Les coefficients, l'intercept, la version des caractéristiques et les métriques sont stockés en JSON dans `exercise_preference_models`, sans fichier pickle à charger. L'inférence utilise ces coefficients ; elle ne relance pas l'entraînement à chaque demande.

Le score de classement devient `0.8 × similarité + 0.2 × préférence prédite`. Les contraintes obligatoires restent appliquées avant ce score. Le score de préférence est un outil de classement personnel ; sa calibration probabiliste n'est pas établie sur un petit jeu de retours.

### Démarrage sans données réelles

Le projet ne prétend pas disposer d'un modèle utilisateur entraîné avant la collecte des retours. Les repas/séries de démonstration ne sont pas des labels de préférence et ne sont pas utilisés pour l'entraînement. Les tests automatisés utilisent des jeux synthétiques dans une base isolée uniquement pour vérifier le pipeline. Leurs résultats ne constituent pas une mesure de performance sur des sportifs réels.

Depuis `backend/`, inspecter puis entraîner un compte existant :

```powershell
.venv\Scripts\python scripts\train_exercise_preferences.py --email ahmed@gmail.com
.venv\Scripts\python scripts\train_exercise_preferences.py --email ahmed@gmail.com --train
```

La seconde commande refuse l'entraînement si les données sont insuffisantes. Le même parcours est disponible depuis l'interface.

## API, base et validation

Toutes les nouvelles routes exigent un compte authentifié :

| Route | Fonction |
|---|---|
| `POST /api/exercises/alternatives` | Proposer et mémoriser les alternatives affichées |
| `PUT /api/exercises/recommendations/{id}/feedback` | Enregistrer ou corriger son propre retour |
| `GET /api/exercises/preferences/status` | État de la collecte et métriques du modèle personnel |
| `POST /api/exercises/preferences/train` | Entraîner, évaluer, puis éventuellement déployer |
| `DELETE /api/exercises/preferences` | Effacer ses retours et son modèle |
| `POST /api/exercises/routine/explanation` | Explication du programme à partir des guides |

La migration `f4a8d3b2c601` ajoute les deux tables sans modifier les données existantes. Leurs clés étrangères sont en suppression en cascade ; la suppression complète du compte les efface aussi explicitement pour les bases de test SQLite.

```powershell
cd backend
.venv\Scripts\python -m alembic upgrade head
.venv\Scripts\python -m pytest tests/test_workout_planner_ai.py tests/test_exercises.py -q
```

Les tests couvrent les contraintes, les résultats vides, l'authentification, l'isolation des comptes, les retours répétés, la sauvegarde avant acceptation, le remplacement, le refus d'un modèle moins bon que la référence, l'inférence, l'effacement et les réponses RAG invalides ou sans sources.

## Corrections de cohérence métier

- Les règles de niveau, de matériel et de rôle Push/Pull sont partagées par la génération et les suggestions. Le générateur ne réutilise pas un exercice deux fois dans une même séance. Une contrainte impossible entraîne une omission signalée plutôt qu’un exercice incompatible.
- Le PPL à deux jours est refusé pour éviter de supprimer entièrement les jambes. Les semaines PPL à quatre/cinq jours indiquent leur fréquence inégale.
- Le champ canonique de volume est `weekly_sets_per_muscle`, calculé depuis les identifiants du catalogue. L’ancienne clé est normalisée à la lecture/sauvegarde. La plage `volume_target` vient du même calcul backend pour le graphique, les avertissements et les suggestions. Il s’agit de séries prévues par muscle principal, pas de séries effectives mesurées.
- Le matériel est sélectionnable dans le générateur et conservé dans le programme. Les ajouts IA respectent ce matériel, le niveau et la séance, ainsi que la marge de séries disponible. Un manque de candidat n’est plus présenté comme un programme équilibré.
- Les programmes existants sont conservés. Leur lecture recalcule les faits et avertit sur les choix incompatibles ; une régénération applique les nouvelles règles sans écrasement automatique des choix personnels.
- Le RAG recherche les noms et mouvements réels du programme, récupère huit candidats, puis conserve au plus quatre pages distinctes. La vérification des références ne constitue toujours pas une preuve automatique de chaque affirmation.
- La version du modèle de préférences passe à `exercise-preferences-v2-explicit-feedback`. Les anciens coefficients, entraînés avec les remplacements considérés comme négatifs, restent stockés mais sont inactifs jusqu’à un nouvel entraînement valide.
