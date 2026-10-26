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

## Tables

| Table | Rôle | Clés |
|---|---|---|
| `users` | Comptes : email unique, nom, hash **bcrypt** du mot de passe, dates de création et de dernière connexion | PK `id`, index unique `email` |
| `user_profile` | Profil biométrique (âge, sexe, taille, poids, % MG, niveau, objectif, somatotype…) — 1 par compte | FK `user_id → users.id` (unique) |
| `chat_session` | Conversations avec le coach IA | FK `user_id → users.id` |
| `chat_message` | Messages (`user` / `assistant`) + sources RAG (JSON) | FK `session_id → chat_session.id` |
| `workout_sets` | Séries enregistrées (reps, charge, RPE/RIR) pour la surcharge progressive | FK `user_id → users.id` |
| `meal_logs` | Journal alimentaire (avant : `localStorage`) | FK `user_id → users.id` |
| `saved_routines` | Programme suivi (JSON), 1 par compte (avant : `localStorage`) | FK `user_id → users.id` (unique) |

* Toutes les clés étrangères sont en `ON DELETE CASCADE` : supprimer un compte efface toutes ses données
  (endpoint `DELETE /api/auth/me`).
* Des types ENUM PostgreSQL (`sex`, `goal`, `activitylevel`…) et des contraintes `CHECK` (âge 14–100,
  reps 1–100, etc.) protègent la cohérence des données au niveau de la base.
* Chaque requête API filtre par `user_id` du jeton JWT : un utilisateur ne peut ni lire ni modifier les
  données d'un autre. La ressource d'un autre compte renvoie 404, pas 403, pour ne pas révéler qu'elle existe.

```
users 1───1 user_profile
  │ 1
  ├──n chat_session 1──n chat_message
  ├──n workout_sets
  ├──n meal_logs
  └──1 saved_routines
```
