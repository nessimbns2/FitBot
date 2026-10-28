"""Export the report's prompt appendix without importing the app or reading .env.

Run from any directory with Python 3.10+. AST extraction preserves literal prompt
text; f-string expressions remain explicit placeholders. The export also inventories
every provider-facing call site so additions can be noticed during report updates.
"""
from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "report"
OUT = REPORT / "prompts"
records: list[dict] = []
cache: dict[str, tuple[str, ast.Module]] = {}


def source(path: str) -> tuple[str, ast.Module]:
    if path not in cache:
        text = (ROOT / path).read_text(encoding="utf-8-sig")
        cache[path] = text, ast.parse(text)
    return cache[path]


def scope(path: str, name: str | None = None) -> ast.AST:
    tree = source(path)[1]
    if name is None:
        return tree
    return next(n for n in ast.walk(tree)
                if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == name)


def assignments(path: str, name: str, function: str | None = None) -> list[ast.Assign | ast.AnnAssign]:
    nodes = []
    for node in ast.walk(scope(path, function)):
        targets = node.targets if isinstance(node, ast.Assign) else [node.target] if isinstance(node, ast.AnnAssign) else []
        if any(isinstance(t, ast.Name) and t.id == name for t in targets):
            nodes.append(node)
    return sorted(nodes, key=lambda n: n.lineno)


def render(node: ast.AST) -> str:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.JoinedStr):
        return "".join(render(part) for part in node.values)
    if isinstance(node, ast.FormattedValue):
        conv = "!" + chr(node.conversion) if node.conversion != -1 else ""
        spec = ":" + render(node.format_spec) if node.format_spec is not None else ""
        return "{" + ast.unparse(node.value) + conv + spec + "}"
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        return render(node.left) + render(node.right)
    return "{" + ast.unparse(node) + "}"


def add(code: str, title: str, path: str, node: ast.AST, text: str,
        note: str = "", kind: str = "gabarit") -> None:
    # Keep the exported string byte-for-byte (including trailing newlines).
    records.append(dict(id=code, title=title, source=path, line=node.lineno,
                        kind=kind, note=note, text=text,
                        sha256=hashlib.sha256(text.encode("utf-8")).hexdigest()))


def const(code: str, title: str, path: str, name: str, note: str = "") -> None:
    node = assignments(path, name)[0]
    add(code, title, path, node, ast.literal_eval(node.value), note)


def local(code: str, title: str, path: str, function: str, name: str,
          index: int = 0, note: str = "") -> None:
    node = assignments(path, name, function)[index]
    add(code, title, path, node, render(node.value), note, "gabarit dynamique")


def excerpt(code: str, title: str, path: str, function: str, note: str = "") -> None:
    node = scope(path, function)
    add(code, title, path, node, ast.get_source_segment(source(path)[0], node),
        note, "code d'assemblage exact")


def tex(value: str) -> str:
    return "".join({"\\": r"\textbackslash{}", "&": r"\&", "%": r"\%",
                    "$": r"\$", "#": r"\#", "_": r"\_", "{": r"\{",
                    "}": r"\}", "~": r"\textasciitilde{}", "^": r"\textasciicircum{}"}.get(c, c)
                   for c in value)


def main() -> None:
    coach = "backend/app/prompts/coach.py"
    for code, title, name in [
        ("C01", "Persona commune du coach", "COACH_PERSONA"),
        ("C02", "Note éducative commune", "SAFETY_DISCLAIMER"),
        ("C03", "Coach : nutrition", "NUTRITION_PROMPT_TEMPLATE"),
        ("C04", "Coach : technique des exercices", "EXERCISE_TECHNIQUE_PROMPT_TEMPLATE"),
        ("C05", "Coach : progression et surcharge", "OVERLOAD_ADVICE_PROMPT_TEMPLATE"),
        ("C06", "Coach : confirmation de séance", "WORKOUT_LOGGING_PROMPT_TEMPLATE"),
        ("C07", "Coach : questions générales", "GENERAL_PROMPT_TEMPLATE"),
    ]:
        const(code, title, coach, name)
    local("C08", "Classification de l'intention en dernier recours",
          "backend/app/modules/rag_core/router_agent.py", "classify_intent", "sys",
          note="Le message utilisateur constitue l'autre entrée. Les règles locales sont essayées avant cet appel.")

    nutrition = "backend/app/modules/nutrition/router.py"
    meal_plan = scope(nutrition, "meal_plan")
    calls = sorted([n for n in ast.walk(meal_plan) if isinstance(n, ast.Call)
                    and isinstance(n.func, ast.Attribute) and n.func.attr == "complete"], key=lambda n: n.lineno)
    assert len(calls) == 3, "Revoir l'inventaire du plan nutrition : nombre d'appels modifié."
    for i, (title, call) in enumerate(zip(["Timing des repas", "Hydratation", "Compléments alimentaires"], calls), 1):
        kwargs = {k.arg: k.value for k in call.keywords}
        messages = ast.literal_eval(kwargs["messages"])
        text = "SYSTEM:\n" + render(kwargs["system"]) + "\n\nUSER:\n" + messages[0]["content"]
        add(f"N0{i}", title, nutrition, call, text,
            "Le marqueur de jointure représente les passages récupérés pour ce thème ; k = 2. Aucun gabarit du coach n'est ajouté à ces trois appels.")
    suggestions = "backend/app/modules/nutrition/suggestion_service.py"
    const("N04", "Idées de repas : instructions système", suggestions, "SYSTEM_PROMPT")
    excerpt("N05", "Idées de repas : construction du message utilisateur", suggestions, "_build_user_message",
            "Les nombres viennent du solde calculé ; le texte résultant est ensuite passé à redact_pii avant l'appel.")

    const("V01", "Scanner de repas : instruction multimodale intégrale",
          "backend/app/prompts/vision.py", "MEAL_SCAN_VISION_PROMPT",
          "La photo accompagne ce texte. Les doubles accolades du gabarit deviennent des accolades simples après format().")
    local("V02", "Scanner : contexte facultatif de créneau", nutrition, "scan_meal", "meal_slot_context",
          note="Expression conditionnelle exacte : chaîne vide si le créneau est absent.")

    exercises = "backend/app/modules/exercises/router.py"
    local("E01", "Technique : instructions et contexte", exercises, "get_form_cues", "sys")
    local("E02", "Technique : question utilisateur ou question par défaut", exercises, "get_form_cues", "question",
          note="L'expression conserve le choix entre la question pseudonymisée et la question standard.")
    body_call = next(n for n in ast.walk(scope(exercises, "get_body_type_guidance"))
                     if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == "complete")
    sys = next(k.value for k in body_call.keywords if k.arg == "system")
    add("E03", "Conseils par morphotype : contexte système", exercises, sys, render(sys))
    guidance = "backend/app/prompts/guidance.py"
    const("E04", "Conseils par morphotype : demande d'entraînement", guidance, "SOMATOTYPE_EXERCISE_USER_TEMPLATE")
    const("E05", "Gabarit nutrition par morphotype non appelé", guidance, "SOMATOTYPE_NUTRITION_USER_TEMPLATE",
          "Défini et exporté dans le code, mais sans appel fonctionnel trouvé dans les routes actuelles. Ce n'est pas une fonctionnalité supplémentaire démontrée.")
    const("P01", "Questionnaire de morphotype : système", guidance, "SOMATOTYPE_PREDICTION_SYSTEM_PROMPT")
    const("P02", "Questionnaire de morphotype : réponses", guidance, "SOMATOTYPE_PREDICTION_USER_TEMPLATE",
          "Les formulations médicales du prompt sont reproduites à des fins d'audit ; elles ne prouvent pas la validité scientifique du questionnaire.")
    questions = assignments(guidance, "SOMATOTYPE_QUESTIONS")[0]
    bank = ast.literal_eval(questions.value)
    add("P03", "Questionnaire : banque de questions et choix", guidance, questions,
        json.dumps(bank, ensure_ascii=False, indent=2),
        "Donnée d'entrée du formulaire, et non instruction système supplémentaire. Le message P02 reçoit les libellés des réponses validées.",
        "donnée de formulaire")
    const("B01", "Athlete Blueprint : système et schéma", guidance, "ATHLETE_BLUEPRINT_SYSTEM_PROMPT")
    const("B02", "Athlete Blueprint : profil, cibles et passages", guidance, "ATHLETE_BLUEPRINT_USER_TEMPLATE")

    routine = "backend/app/prompts/routine.py"
    const("R01", "Assistant routine : justification système", routine, "ROUTINE_SUGGESTION_SYSTEM_PROMPT")
    const("R02", "Assistant routine : contexte de volume", routine, "ROUTINE_SUGGESTION_USER_TEMPLATE")
    const("R03", "Workout Planner : explication documentaire structurée",
          "backend/app/prompts/planner_explanation.py", "PLANNER_EXPLANATION_SYSTEM")
    excerpt("R04", "Workout Planner : faits, recherche et validation des références",
            "backend/app/modules/exercises/planner_explanation.py", "explain_routine",
            "Les données du programme sont reconstruites depuis le catalogue. Huit passages sont recherchés ; au plus quatre pages distinctes sont conservées. Le contrat JSON et les identifiants de citation sont vérifiés, sans preuve automatique de validité sémantique.")

    plateau = "backend/app/modules/progressive_overload/service.py"
    function = "generate_diagnosis_explanation"
    const("D01", "Plateau : exemple abstrait de format", plateau, "_ABSTRACT_FORMAT_ILLUSTRATION",
          "Exemple de structure dans un autre domaine, sans valeur de preuve ; les règles interdisent d'en recopier les phrases.")
    for code, title, name, index in [
        ("D02", "Plateau : contexte avec sources", "research_instruction", 0),
        ("D03", "Plateau : contexte sans source", "research_instruction", 1),
        ("D04", "Plateau ambigu : instructions système", "system_prompt", 0),
        ("D05", "Plateau ambigu : message utilisateur", "user_message", 0),
        ("D06", "Plateau standard : instructions système", "system_prompt", 1),
        ("D07", "Plateau standard : message utilisateur", "user_message", 1),
    ]:
        local(code, title, plateau, function, name, index,
              note="Les références research_instruction et _ABSTRACT_FORMAT_ILLUSTRATION sont remplacées par D02 ou D03, puis D01. Les autres champs proviennent des signaux et stratégies calculés par Python."
              if name == "system_prompt" else "")

    engine = "backend/app/modules/rag_core/engine.py"
    excerpt("T01", "Assemblage des gabarits du coach et de la mémoire", engine, "build_prompt")
    excerpt("T02", "Sérialisation finale des rôles pour le fournisseur", engine, "_build_prompt",
            "Les préfixes SYSTEM, USER et ASSISTANT sont du texte concaténé dans une seule entrée du SDK. Ils ne constituent pas une séparation de rôles native et inviolable.")

    OUT.mkdir(parents=True, exist_ok=True)
    manifest = []
    for record in records:
        filename = record["id"] + ".txt"
        (OUT / filename).write_text(record["text"], encoding="utf-8", newline="\n")
        manifest.append({k: v for k, v in record.items() if k != "text"} | {"file": filename})

    calls = []
    for path in sorted((ROOT / "backend/app").rglob("*.py")):
        relative = path.relative_to(ROOT).as_posix()
        for node in ast.walk(source(relative)[1]):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr in {"complete", "stream", "generate_content"}:
                calls.append(dict(source=relative, line=node.lineno, method=node.func.attr))
    calls.sort(key=lambda c: (c["source"], c["line"]))
    (OUT / "manifest.json").write_text(json.dumps({
        "method": "AST only; no runtime import or secret access; f-string expressions kept as placeholders",
        "records": manifest, "provider_call_sites": calls,
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    groups = [
        ("Coach conversationnel et classification", "C"),
        ("Plan nutrition et idées de repas", "N"),
        ("Analyse multimodale des repas", "V"),
        ("Technique et conseils par morphotype", "E"),
        ("Questionnaire de morphotype", "P"),
        ("Bilan Athlete Blueprint", "B"),
        ("Assistant de routine", "R"),
        ("Diagnostic de plateau : toutes les variantes", "D"),
        ("Assemblage final et protocole texte", "T"),
    ]
    lines = [r"% Generated by tools/export_prompts.py; do not edit by hand.",
             r"\section{Catalogue intégral des prompts IA}\label{annexe:prompts}",
             "Cette annexe reproduit les chaînes et gabarits lus dans le code, sans appel au fournisseur. "
             "Les prompts sont conservés en anglais, leur langue d'exécution. Les champs entre accolades "
             "désignent des variables : aucun profil personnel ni secret réel n'est inséré. Les expressions "
             "des chaînes formatées restent visibles lorsqu'elles dépendent du contexte d'exécution.",
             f"Le catalogue contient \\textbf{{{len(records)} éléments}} : instructions, messages, fragments réutilisés, "
             "banque de questions et fonctions d'assemblage. Ce nombre ne désigne pas des appels indépendants. "
             "Le fichier \\path{prompts/manifest.json} enregistre leur provenance et l'empreinte SHA-256 de chaque texte.",
             r"\subsection{Mode de lecture et composition}",
             "Pour le chat, C01 et C02 sont injectés dans un seul gabarit parmi C03--C07, puis T01 ajoute les passages et la mémoire récente. "
             "C08 ne sert qu'au classement de l'intention en dernier recours. La question nutrition dédiée réutilise C03 ; "
             "elle ne possède pas de prompt caché supplémentaire.",
             "N01--N03 sont des couples système/utilisateur ; N04 et N05 forment la requête des suggestions. "
             "V01 est formaté avec V02 et accompagné de la photo. E01 et E02 forment la requête de technique ; "
             "E03 et E04 celle des conseils par morphotype. E05 est conservé pour l'audit mais n'est pas appelé.",
             "P01 et P02 utilisent les choix P03. B01/B02 et R01/R02 sont les couples du bilan et de la routine. "
             "R03 encadre l'explication RAG du Workout Planner ; R04 reproduit sa construction du contexte, sa recherche et sa validation. "
             "D04/D05 ou D06/D07 sont utilisés selon le diagnostic ; D02 ou D03 et D01 complètent le système. "
             "T02 sérialise les requêtes texte. Le scanner envoie directement une entrée multimodale au SDK.",
             r"\begin{principlebox}{Portée des formulations reproduites}",
             "Une instruction telle que « validé », « expert », « scientifique » ou « JSON valide » décrit ce que le prompt demande au modèle. "
             "Elle ne certifie ni la qualité médicale, ni l'exactitude des chiffres générés, ni le respect effectif du format. "
             "Les protections exécutées par Python et leurs limites sont documentées dans les sections précédentes.",
             r"\end{principlebox}"]
    for title, prefix in groups:
        lines.extend([r"\clearpage", r"\subsection{" + tex(title) + "}"])
        for r in records:
            if not r["id"].startswith(prefix):
                continue
            lines.extend([r"\subsubsection{" + tex(r["id"] + " - " + r["title"]) + "}",
                          r"{\small Source : \path{" + r["source"] + "}, ligne " + str(r["line"]) + ". " + tex(r["kind"]) + ".}"])
            if r["note"]:
                lines.append(tex(r["note"]))
            lines.append(r"\lstinputlisting[style=promptstyle]{prompts/" + r["id"] + ".txt}")
    (REPORT / "annexe_prompts.tex").write_text("\n\n".join(lines) + "\n", encoding="utf-8")
    print(f"Exported {len(records)} elements and inventoried {len(calls)} call sites.")


if __name__ == "__main__":
    main()
