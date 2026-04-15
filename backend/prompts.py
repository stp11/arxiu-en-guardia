# flake8: noqa: E501
from models import Episode

CLASSIFICATION_KEYS = ["temàtica", "època", "personatges", "localització"]

CLASSIFICATION_SCHEMA = {
    "name": "episode_classification",
    "strict": True,
    "schema": {
        "type": "object",
        "properties": {
            "temàtica": {"type": "array", "items": {"type": "string"}},
            "època": {"type": "array", "items": {"type": "string"}},
            "personatges": {"type": "array", "items": {"type": "string"}},
            "localització": {"type": "array", "items": {"type": "string"}},
        },
        "required": CLASSIFICATION_KEYS,
        "additionalProperties": False,
    },
}


def classification_prompt(
    episode: Episode,
    existing_categories_by_type: dict[str, list[str]] | None = None,
) -> str:
    existing_section = _build_existing_categories_section(
        existing_categories_by_type
    )

    return f"""
# ROL
Actua com un expert historiador i analista de dades.

# TASCA
A partir del títol i descripció proporcionats, extreu i classifica la informació històrica PRINCIPAL en quatre claus: `temàtica`, `època`, `personatges` i `localització`.
Centra't primer en el títol per identificar allò principal; exclou allò que sigui secundari de la descripció.
Ignora sempre qualsevol menció a convidats o experts del programa de ràdio: centra't exclusivament en el contingut històric.
Si no estàs segur d'una classificació concreta, retorna una llista buida per aquella clau en comptes d'inventar-la.
{existing_section}
# GUIA PER CADA CLAU

## temàtica
- Identifica el tema històric principal (i opcionalment temes secundaris extrets de la descripció).
- Reutilitza una categoria existent si el tema és conceptualment equivalent, fins i tot si el nom exacte no apareix al text (e.g. "la revolta de 1640" → "Guerra dels Segadors").
- Fes servir noms propis o sintagmes nominals (e.g. "Revolució Francesa", "Brigades Internacionals").
- Associa "Catalunya" o "catalans" com a categoria NOMÉS quan sigui estrictament necessari.

## època
- Sigues el més concret possible, però NO especifiquis l'any.
- Si fas servir el segle, crea una categoria per cada segle. NO especifiquis part del segle: "inicis del segle XX" → "Segle XX"; "antiguitat tardana" → "Segle V".
- Combina fets concrets amb èpoques generals complementàries: "Revolució Francesa" + ["Antic Règim", "Segle XVIII"].
- Aquesta és una llista gairebé tancada: reutilitza sempre una època existent si encaixa.

## personatges
- Només personatges històrics rellevants al fet tractat. MAI convidats, experts o historiadors del programa.
- Fes servir nom i cognom complets: "Jean-Jacques Rousseau", no "Rousseau".
- Retorna una llista buida si l'episodi no es centra en individus concrets.

## localització
- Només llocs rellevants al fet històric. Ignora llocs associats als convidats (universitats, instituts, ciutats de residència).
- Retorna una llista buida si l'episodi no té una localització geogràfica clara.

# EXEMPLES

## EXEMPLE 1 — temàtica, personatges i localització clars
# TITOL
La Guerra Civil a l'Alt Urgell i la Cerdanya
# DESCRIPCIÓ
Capítol 1211. Els anarquistes, especialment els sectors més durs, van assumir el poder i van substituir els ajuntaments legalment constituïts a les comarques de l'Alt Urgell i la Cerdanya després del cop d'estat militar del juliol del 1936. Tant a la Seu d'Urgell com a Puigcerdà es van viure episodis de violència. Un dels anarquistes més destacats va ser l'anomenat Cojo de Málaga. En parlem amb l'historiador Josep Maria Solé i Sabaté i amb Pau Chica, membre de l'Institut d'Estudis Comarcals de l'Alt Urgell.
# SORTIDA JSON
{{
    "temàtica": ["Guerra Civil Espanyola", "Anarquisme"],
    "època": ["Segle XX"],
    "personatges": ["Cojo de Málaga"],
    "localització": ["Alt Urgell", "Cerdanya"]
}}

## EXEMPLE 2 — sense personatges concrets
# TITOL
Les muralles de Barcelona
# DESCRIPCIÓ
Un recorregut per l'evolució de les muralles defensives de Barcelona des de l'època romana fins al seu enderroc a mitjans del segle XIX. Hi participa l'arqueòleg Julia Beltrán de Heredia.
# SORTIDA JSON
{{
    "temàtica": ["Història de Barcelona", "Arquitectura militar"],
    "època": ["Època Romana", "Segle XIX"],
    "personatges": [],
    "localització": ["Barcelona"]
}}

---
# DADES A PROCESSAR
# TITOL
{episode.title}

# DESCRIPCIÓ
{episode.description}
"""


def _build_existing_categories_section(
    existing_categories_by_type: dict[str, list[str]] | None,
) -> str:
    if not existing_categories_by_type:
        return ""

    sections = []
    for key in CLASSIFICATION_KEYS:
        names = existing_categories_by_type.get(key) or []
        if not names:
            continue
        sections.append(f"## {key}\n{', '.join(sorted(names))}")

    if not sections:
        return ""

    joined = "\n\n".join(sections)
    return f"""
# CATEGORIES EXISTENTS
Aquestes categories ja existeixen a la base de dades, agrupades pel tipus que els correspon. Dona-hi prioritat sempre que sigui possible per mantenir la consistència, i assigna-les únicament a la clau del seu tipus.

{joined}
"""
