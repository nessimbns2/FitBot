# Rapport technique FitBot

Le document principal est `fitbot_report.tex`. Ses captures sont dans `images/` :
conserver ce dossier avec le fichier LaTeX, notamment lors d'un import dans Overleaf.
Conserver aussi `optimisation_securite.tex`, `annexe_prompts.tex` et le dossier
`prompts/`, qui contiennent le chapitre de sécurité et les listings intégraux.
Le PDF compilé est `fitbot_report.pdf`. L'archive `FitBot_Rapport_Complet.zip`
regroupe les sources nécessaires et le PDF pour un import dans Overleaf.

## Recompiler

Depuis ce dossier, avec une distribution LaTeX disposant des packages du préambule :

```powershell
latexmk -pdf fitbot_report.tex
```

Ou avec Tectonic :

```powershell
tectonic -X compile fitbot_report.tex
```

## Refaire les captures

Lancer le backend et le frontend. Depuis `frontend/` :

```powershell
node scripts/capture_report.mjs
```

Le script utilise Chrome en mode headless, crée un compte temporaire et des données
synthétiques, appelle les services IA réellement configurés, puis supprime ce compte.
Les résultats du modèle peuvent changer entre deux exécutions. Le manifeste
`images/captures.json` ne contient ni jeton d'accès ni mot de passe.

La photographie de salade de démonstration est d'Anna Pelzer :
[Bowl of vegetable salads, Unsplash](https://unsplash.com/photos/bowl-of-vegetable-salads-IGfIGP5ONV0),
utilisée sous la licence Unsplash. Elle est conservée dans `images/demo-meal.jpg`
pour reproduire la capture Vision.

## Actualiser les prompts de l'annexe

Depuis la racine du dépôt :

```powershell
backend/.venv/Scripts/python.exe report/tools/export_prompts.py
```

Le script utilise uniquement l'AST Python : il n'importe pas le backend, ne lit pas
`.env` et n'appelle pas Gemini. Il exporte 38 éléments issus des prompts et des
services : instructions, messages, variantes du plateau, fragments communs,
banque du questionnaire et fonctions d'assemblage. Les variables des chaînes
formatées restent des marqueurs ; aucune donnée de compte réelle n'est insérée.
Le gabarit nutrition par morphotype non appelé est explicitement identifié.

`prompts/manifest.json` contient la provenance, les lignes, les empreintes SHA-256
des textes et l'inventaire des appels du code. Après toute évolution du backend,
régénérer puis vérifier la couverture des nouvelles fonctionnalités et recompiler.
Le chapitre de sécurité distingue les protections exécutées, les consignes du
modèle, leurs limites et les améliorations proposées.

## Résultats cités

Le rapport présente les fonctionnalités sans identifiants de commits. Il inclut
les alternatives par similarité, l'explication RAG citée et le modèle supervisé
personnel du Workout Planner, avec leurs contraintes et limites. Les résultats
automatisés consignés repris dans le rapport sont 400 tests réussis et 2 ignorés,
ainsi que l'évaluation documentaire sur
20 questions (top-5, seuil 0,10). Les estimations du scanner et des suggestions
ne sont pas présentées comme des données nutritionnelles certifiées.
