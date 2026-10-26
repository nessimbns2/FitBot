# Rapport technique FitBot

Le document principal est `fitbot_report.tex`. Ses captures sont dans `images/` :
conserver ce dossier avec le fichier LaTeX, notamment lors d'un import dans Overleaf.
Le PDF compilé est `fitbot_report.pdf`.

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

## Résultats cités

La version de code étudiée est `43a4795`. Les résultats automatisés repris dans le
rapport sont 341 tests réussis et 2 ignorés, ainsi que l'évaluation documentaire sur
20 questions (top-5, seuil 0,10). Les estimations du scanner et des suggestions
ne sont pas présentées comme des données nutritionnelles certifiées.
