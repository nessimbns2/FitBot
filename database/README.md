# Base de données PostgreSQL — FitBot

FitBot stocke toutes les données utilisateur dans **PostgreSQL 17** (base `fitbot_db`, rôle `fitbot`).
Avant, les repas et le programme d'entraînement restaient dans le `localStorage` du navigateur, et un seul
profil (id = 1) était partagé par tout le monde.

## Installation (une seule fois)

1. Dans **pgAdmin > Query Tool** (connecté en `postgres`), exécuter `00_create_role_and_db.sql`
   en remplaçant `CHANGE_ME…` par un mot de passe.
   `CREATE DATABASE` ne peut pas tourner dans un bloc de transaction : exécutez les instructions une par une,
   ou créez la base avec psql en tant que `fitbot`, qui a le droit `CREATEDB` :
   `psql -h localhost -U fitbot -d postgres -c "CREATE DATABASE fitbot_db OWNER fitbot;"`
2. Mettre la même valeur dans `backend/.env` :
   `DATABASE_URL=postgresql+psycopg://fitbot:<mot_de_passe>@localhost:5432/fitbot_db`
3. Créer les tables avec Alembic : `cd backend && .venv\Scripts\python -m alembic upgrade head`.
   L'API exécute aussi cette commande à chaque démarrage.

`01_schema.sql` est l'export `pg_dump --schema-only` du schéma obtenu, fourni pour le rapport.
Il n'est pas nécessaire de l'exécuter.

## Compte de démonstration

`cd backend && .venv\Scripts\python scripts\seed_demo.py` crée ou réinitialise le compte de test local
défini dans `backend/scripts/seed_demo.py` (`DEMO_EMAIL` / `DEMO_PASSWORD`). Il contient un profil,
4 semaines de séries, un programme et les repas du jour.

### Ajouter des exemples à un compte existant

Depuis `backend/` :

```powershell
.venv\Scripts\python scripts\seed_user_samples.py --email ahmed@gmail.com
```

Ce script conserve le mot de passe, le profil, le programme et les données existantes.
Il ajoute 189 séries réparties sur six semaines et sept exercices, 26 repas sur sept jours,
deux conversations explicitement marquées comme exemples et un ancien bloc de récupération terminé.
Un programme est créé uniquement si le compte n'en possède pas. Les données sont stockées dans PostgreSQL.
Relancer la commande ne duplique pas les exemples et ne décale pas l'historique sportif.
Les repas manquants des sept derniers jours sont ajoutés, dont deux pour le jour courant.

Pour tester : ouvrir **Nutrition** pour ajouter/modifier/supprimer un repas, **Workouts** pour le programme,
**Tracker** pour les graphiques et les recommandations (bench en progression, squat en plateau),
et **Coach Chat** pour les conversations enregistrées. Les réponses de démonstration ne sont pas des réponses IA réelles :
envoyer un nouveau message ou utiliser une fonction IA pour tester le fournisseur configuré dans `backend/.env`.

## Tables

| Table | Rôle | Clés |
|---|---|---|
| `users` | Comptes : email unique, nom, hash **bcrypt** du mot de passe, dates de création et de dernière connexion | PK `id`, index unique `email` |
| `user_profile` | Profil biométrique (âge, sexe, taille, poids, % MG, niveau, objectif, somatotype…) — 1 par compte | FK `user_id → users.id` (unique) |
| `chat_session` | Conversations avec le coach IA | FK `user_id → users.id` |
| `chat_message` | Messages (`user` / `assistant`) + sources RAG (JSON) | FK `session_id → chat_session.id` |
| `workout_sets` | Séries enregistrées (reps, charge, RPE/RIR) pour la surcharge progressive | FK `user_id → users.id` |
| `meal_logs` | Ancien journal conservé pour la compatibilité de l'API `/meals` | FK `user_id → users.id` |
| `food_log_entries` | Journal alimentaire détaillé : saisie, édition, photo et suggestions IA | FK `user_id → users.id` |
| `deload_records` | Prescriptions de récupération et historique du diagnostic de plateau | FK `user_id → users.id` |
| `saved_routines` | Programme suivi (JSON), 1 par compte (avant : `localStorage`) | FK `user_id → users.id` (unique) |
| `exercise_recommendations` | Alternatives affichées et retours explicites pour la personnalisation | FK `user_id → users.id` |
| `exercise_preference_models` | Coefficients JSON et évaluation du modèle ML personnel | PK/FK `user_id → users.id` |

* Toutes les clés étrangères sont en `ON DELETE CASCADE` : supprimer un compte efface toutes ses données
  (endpoint `DELETE /api/auth/me`).
* Des types ENUM PostgreSQL (`sex`, `goal`, `activitylevel`…) et des contraintes `CHECK` (âge 14–100,
  reps 1–100, etc.) protègent la cohérence des données au niveau de la base.
* Chaque requête API filtre par `user_id` du jeton JWT : un utilisateur ne peut ni lire ni modifier les
  données d'un autre. La ressource d'un autre compte renvoie 404, pas 403, pour ne pas révéler qu'elle existe.

La migration `e3c2b8d5f0a1` intègre les fonctionnalités du `main` distant. Elle copie les repas
existants de `meal_logs` vers `food_log_entries`, avec leur propriétaire et leur date,
sans supprimer les anciennes entrées. L'interface Nutrition utilise désormais `/api/nutrition/log`.

La migration `f4a8d3b2c601` ajoute les recommandations et les modèles de préférences du Workout Planner.
Le fonctionnement, les seuils d'entraînement et les limites de l'évaluation sont décrits dans
[Workout Planner AI](../docs/workout-planner-ai.md).

```
users 1───1 user_profile
  │ 1
  ├──n chat_session 1──n chat_message
  ├──n workout_sets
  ├──n meal_logs
  └──1 saved_routines
```
