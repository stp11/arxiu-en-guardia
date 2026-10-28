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


WIKIPEDIA_ARTICLES_SCHEMA = {
    "name": "wikipedia_articles",
    "strict": True,
    "schema": {
        "type": "object",
        "properties": {
            "articles": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["articles"],
        "additionalProperties": False,
    },
}


def wikipedia_articles_prompt(
    episode: Episode, max_articles: int, category_names: list[str]
) -> str:
    categories = ", ".join(category_names) or "(cap)"

    return f"""
# ROL
Actua com un historiador i documentalista que enllaça els episodis de l'arxiu del programa de ràdio En Guàrdia amb articles de la Viquipèdia en català.

# TASCA
A partir del títol, la descripció i les categories de l'episodi, digues quins articles de la Viquipèdia en català (ca.wikipedia.org) tracten allò de què parla l'episodi, del més al menys important, fins a {max_articles}.

## Regles
- Escriu el títol de l'article tal com és a la Viquipèdia en català, sense URL: "Guerra dels Segadors", "Jaume el Conqueridor", "Fets del sis d'octubre". Si no en saps el títol exacte, escriu-ne el nom més habitual en català: es comprovarà a la Viquipèdia.
- Només el tema principal: el fet, la persona, el lloc, l'obra o el fenomen de què tracta l'episodi. Si en tracta més d'un ("El pare Ubach i Francesc Cambó"), inclou-los tots.
- Evita els articles genèrics que no ajuden a saber més de l'episodi ("Catalunya", "Història", "Segle XX", "Guerra"), tret que l'episodi en tracti específicament.
- Ignora els convidats, experts i historiadors que participen al programa.
- Si cap article no hi encaixa, retorna una llista buida.

# EPISODI
## TÍTOL
{episode.title}

## DESCRIPCIÓ
{episode.description or "(sense descripció)"}

## CATEGORIES
{categories}
"""


WIKIPEDIA_CHOICES_SCHEMA = {
    "name": "wikipedia_choices",
    "strict": True,
    "schema": {
        "type": "object",
        "properties": {
            "choices": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "integer"},
                        "title": {"type": ["string", "null"]},
                    },
                    "required": ["id", "title"],
                    "additionalProperties": False,
                },
            },
        },
        "required": ["choices"],
        "additionalProperties": False,
    },
}


def wikipedia_choices_prompt(
    episode: Episode, searches: dict[int, tuple[str, list]]
) -> str:
    """searches maps an id to a proposed name and the articles found for it."""
    names = "\n\n".join(
        _format_search(id, name, results)
        for id, (name, results) in searches.items()
    )

    return f"""
# ROL
Actua com un historiador i documentalista que enllaça els episodis de l'arxiu del programa de ràdio En Guàrdia amb articles de la Viquipèdia en català.

# TASCA
Per a l'episodi, es van proposar uns noms d'article que no corresponen exactament a cap article de la Viquipèdia, o que en corresponen a una pàgina de desambiguació. Per a cada nom, tria d'entre els resultats de la cerca a la Viquipèdia l'article que tracta allò que el nom volia dir en aquest episodi.

## Regles
- `title` ha de ser exactament el títol d'un dels resultats d'aquell nom, o `null` si cap no tracta el mateix tema.
- Un tema proper o més general no serveix: per a "Moviment veïnal", "Barcelona" no és vàlid.
- En cas de dubte, `null`: un enllaç equivocat és pitjor que cap enllaç.
- Retorna exactament una tria per a cada nom, amb el seu `id`.

# EPISODI
## TÍTOL
{episode.title}

## DESCRIPCIÓ
{episode.description or "(sense descripció)"}

# NOMS PROPOSATS
{names}
"""


def _format_search(id: int, name: str, results: list) -> str:
    lines = [f'[{id}] "{name}"', "Resultats:"]
    lines += [
        f'- "{article.title}"'
        + (f" · {article.description}" if article.description else "")
        for article in results
    ] or ["- (cap)"]
    return "\n".join(lines)
