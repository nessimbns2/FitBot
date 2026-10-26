# FitBot - Notes de soutenance

Durée indicative : 15 à 17 minutes, démonstration comprise.

## 01. FitBot

20 s. Présenter FitBot comme une application web métier intégrant des modules d'IA. Le projet associe React, FastAPI et PostgreSQL. Les écrans suivants proviennent de la version locale du 26 octobre 2026 et utilisent des données fictives de démonstration. Source : README.md et code du dépôt.

## 02. Le besoin et notre réponse

40 s. Décrire le problème métier sans prétendre qu'un chatbot générique échoue systématiquement. La contribution est l'intégration : données persistantes, calculs déterministes, recherche documentaire et explications IA. Distinguer les cibles calculées des estimations faites à partir d'une photo ou d'un repas proposé. Sources : backend/app/modules/nutrition/calculator.py, backend/app/modules/progressive_overload/algorithms.py, backend/app/modules/rag_core/router.py.

## 03. Un compte pour chaque utilisateur

35 s. Montrer la création du compte, puis expliquer JWT et le hachage bcrypt sans entrer dans les détails cryptographiques. Le serveur filtre les ressources par l'identifiant du compte. Les changements de mot de passe et la suppression du compte se trouvent dans le profil. Sources : backend/app/modules/auth/, frontend/src/context/AuthContext.tsx, frontend/src/components/AccountSettings.tsx. Capture réelle, données fictives.

## 04. Le tableau de bord quotidien

30 s. Le tableau de bord rassemble les informations calculées à partir du profil et de l'historique. Les valeurs visibles appartiennent au scénario de démonstration et ne constituent pas une recommandation universelle. Source : frontend/src/views/TodayView.tsx.

## 05. Profil et questionnaire de morphologie

40 s. Expliquer que le questionnaire applique un vote déterministe, puis que le LLM rédige une synthèse. Ne pas le présenter comme une mesure clinique ou un diagnostic métabolique validé. L'utilisateur garde la possibilité d'ajuster son profil. Sources : backend/app/modules/user/service.py, backend/app/prompts/guidance.py, frontend/src/components/SomatotypeQuizModal.tsx. Capture réelle de la première question.

## 06. Le bilan Athlete Blueprint

45 s. Le nouveau module reprend le profil, calcule ses indicateurs, recherche des passages et produit un bilan structuré. Pydantic définit la forme de la réponse. Des valeurs de repli existent si l'IA ne répond pas. Les projections de progrès et les catégories morphologiques restent indicatives, sans garantie individuelle. Sources : backend/app/modules/user/service.py, backend/app/modules/user/models.py, backend/app/prompts/guidance.py, frontend/src/components/AthleteBlueprintModal.tsx.

## 07. L’architecture du projet

55 s. Expliquer le trajet d'une requête : navigateur, API protégée, calcul ou recherche, appel IA éventuel, validation et retour à l'interface. Les index FAISS ne remplacent pas PostgreSQL : ils servent à la recherche documentaire. Sources : backend/main_v2.py, backend/app/core/database.py, frontend/vite.config.js, backend/app/modules/rag_core/engine.py. Modèle configuré dans le code : gemini-3.5-flash-lite, remplaçable par la configuration.

## 08. Le coach conversationnel RAG

50 s. Définir RAG : le modèle rédige à partir de passages retrouvés dans des documents. Les intentions couvrent nutrition, technique, journal d'entraînement, surcharge et général. Le serveur ajoute jusqu'à six messages précédents de la session. La persistance permet de reprendre la conversation après rechargement. Sources : backend/app/modules/rag_core/router.py, router_agent.py, frontend/src/views/ChatView.tsx.

## 09. Des sources consultables

45 s. Le chat récupère jusqu'à cinq passages, le diagnostic de plateau jusqu'à trois. La similarité aide à sélectionner le contexte, mais ne prouve pas la validité scientifique de la source. Le corpus comprend aussi un résumé sur la récupération rédigé avec IA, identifié comme tel dans l'application. Un audit documentaire reste nécessaire. Sources : backend/app/modules/rag_core/engine.py, router.py, backend/docs/manifest.json, backend/app/modules/progressive_overload/service.py.

## 10. Des cibles nutritionnelles calculées

40 s. Mentionner Mifflin-St Jeor et Katch-McArdle selon les données disponibles. Les choix de coefficients et les seuils sont des règles du projet, pas une prescription médicale. La répartition est déterministe, indépendamment de l'appel au LLM. Sources : backend/app/modules/nutrition/calculator.py, service.py et router.py.

## 11. Le journal alimentaire

35 s. Le journal récent remplace le stockage métier dans le navigateur. Un résumé affiche consommé, cible et restant. La migration conserve les anciens repas, leur date et leur propriétaire. Sources : backend/app/modules/nutrition/food_log_service.py, log_router.py, frontend/src/components/nutrition/FoodLogSection.tsx, migration e3c2b8d5f0a1.

## 12. Des idées de repas adaptées au restant

45 s. Les préférences alimentaires entrent dans le prompt. Le backend parse le JSON, retire les éléments inutilisables et calcule lui-même si une suggestion respecte les calories restantes. Les nombres d'un repas proposé restent des estimations de l'IA, contrairement aux cibles quotidiennes. Source : backend/app/modules/nutrition/suggestion_service.py et frontend/src/components/nutrition/FoodLogSection.tsx.

## 13. L’analyse d’une photo de repas

45 s. L'image de démonstration a réellement été analysée par l'API. Ne pas lire les calories comme une mesure exacte : quantité, assaisonnement et aliments cachés rendent l'estimation incertaine. La photo n'est pas enregistrée dans la base. Un échec d'API ne produit pas de faux repas. Sources : backend/app/modules/nutrition/router.py, backend/app/prompts/vision.py. Photo : Cupofjoy, « Salad in a bowl.jpg », Wikimedia Commons, CC0 1.0, https://commons.wikimedia.org/wiki/File:Salad_in_a_bowl.jpg.

## 14. Le programme d’entraînement

35 s. Montrer le split Upper/Lower comme exemple. La génération de base ne demande pas au modèle d'inventer une routine à partir de rien : elle utilise le catalogue et les règles Python. Les modifications de l'utilisateur persistent dans PostgreSQL. Sources : backend/app/modules/exercises/generator.py, router.py et frontend/src/views/WorkoutsView.tsx.

## 15. L’assistant IA du programme

40 s. Décrire le partage des tâches : le code inspecte le programme, sélectionne une proposition dans le catalogue et prépare les faits. L'IA explique ce choix avec une réponse courte. Selon le cas, une réponse équilibrée peut provenir du chemin déterministe. La suggestion n'est pas appliquée sans action utilisateur. Source : backend/app/modules/exercises/router.py, endpoint ai-suggest-exercise, backend/app/prompts/routine.py.

## 16. La technique des exercices

35 s. Montrer la différence entre les consignes du catalogue et l'enrichissement par des documents. Les conseils sur la douleur incluent des précautions et ne servent pas à établir un diagnostic. Sources : backend/app/modules/exercises/catalog.py, router.py, frontend/src/views/WorkoutsView.tsx.

## 17. Le suivi et le diagnostic de plateau

60 s. Le scénario fictif garde une charge de 80 kg, avec RPE croissant et baisse des répétitions. L'algorithme signale un profil compatible avec la fatigue et propose une réduction temporaire. Il s'agit d'une interprétation heuristique des séances, pas d'un diagnostic physiologique. La prose est contrôlée pour rester cohérente avec les faits calculés. Sources : backend/app/modules/progressive_overload/algorithms.py et service.py. Les constantes sont versionnées v1.1.

## 18. Comment nous améliorons la sortie IA

60 s. Préciser que la température 0,3 concerne le diagnostic de plateau, pas tous les appels. La validation de forme ne garantit pas la vérité de la réponse. Le préchargement des embeddings réduit le coût du premier message et le streaming améliore la perception du temps d'attente. Si le fournisseur échoue, le chat peut afficher les extraits retrouvés et signaler son état dégradé. Sources : backend/app/modules/rag_core/engine.py et router.py, backend/app/core/privacy.py, backend/app/core/config.py, backend/app/modules/progressive_overload/service.py.

## 19. Validation et protection des données

50 s. Résultat observé dans le journal de test du 26 octobre 2026 : 341 passed, 2 skipped. Le build Vite et la vérification TypeScript ont aussi réussi. La suite utilise un LLM factice et SQLite isolé. Des contrôles API avec PostgreSQL ont validé les nouvelles routes et la suppression des comptes temporaires. Les identifiants reconnus sont masqués avant certains appels texte, mais cela ne constitue pas une anonymisation complète. Sources : .git/pytest-final-sync.log, backend/tests/test_sync_integration.py, backend/tests/conftest.py et backend/app/core/privacy.py.

## 20. Limites et prochaines évolutions

45 s. Ne pas annoncer de taux d'absence d'hallucination ni d'économies de 75 % : le projet ne fournit pas une mesure actuelle les démontrant. Des métriques utiles seraient la pertinence des passages, l'exactitude des citations, la conformité du JSON et la latence par module. Le bilan morphologique et les projections doivent rester indicatifs. La gestion de session et le masquage peuvent aussi être renforcés pour une mise en production.

## 21. Démonstration du projet

60 s. Passer à la démonstration dans le navigateur. Les captures servent de support de secours si l'API externe est indisponible. Montrer les valeurs calculées, un échange RAG et la conservation des données au rechargement. Terminer par les questions. Code source : https://github.com/nessimbns2/FitBot.
