# flake8: noqa: E501
"""The prompt that reviews categories for propose_category_merges."""

from prompts import CLASSIFICATION_KEYS

CATEGORY_REVIEW_ACTIONS = ["keep", "merge", "rollup", "delete"]

CATEGORY_REVIEW_SCHEMA = {
    "name": "category_review",
    "strict": True,
    "schema": {
        "type": "object",
        "properties": {
            "decisions": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "integer"},
                        "action": {
                            "type": "string",
                            "enum": CATEGORY_REVIEW_ACTIONS,
                        },
                        "target_id": {"type": ["integer", "null"]},
                        "new_name": {"type": ["string", "null"]},
                        "new_type": {
                            "type": ["string", "null"],
                            "enum": [*CLASSIFICATION_KEYS, None],
                        },
                        "reason": {"type": "string"},
                    },
                    "required": [
                        "id",
                        "action",
                        "target_id",
                        "new_name",
                        "new_type",
                        "reason",
                    ],
                    "additionalProperties": False,
                },
            },
        },
        "required": ["decisions"],
        "additionalProperties": False,
    },
}


def category_review_prompt(
    items: list[dict], general_categories: list[dict]
) -> str:
    general = "\n".join(
        f"- {_format_review_category(category)}"
        for category in general_categories
    )
    categories = "\n\n".join(_format_review_item(item) for item in items)

    return f"""
# ROL
Actua com un historiador i documentalista que revisa les categories de l'arxiu del programa de ràdio En Guàrdia.

# CONTEXT
Les categories es van generar automàticament episodi a episodi i n'hi ha massa: sinònims i variants d'un mateix nom, categories amb un tipus equivocat, i convidats o experts del programa classificats com a personatges històrics.
Les categories molt específiques són valuoses encara que només les faci servir un episodi: alguns episodis tracten temes molt concrets.
Hi ha quatre tipus: `temàtica` (temes, fets i conceptes), `època` (períodes i segles), `personatges` (persones històriques) i `localització` (llocs).

# TASCA
Decideix una acció per a cada categoria de la llista. Cada categoria porta alguns títols d'episodis que la fan servir, per entendre-la en context, i una llista de candidats: altres categories amb un nom semblant o que apareixen als mateixos episodis. A més, la llista de categories generals recull les temàtiques i localitzacions més utilitzades de l'arxiu.

## Accions
- `merge`: la categoria és la mateixa entitat o concepte que un dels candidats, amb un altre nom, grafia o numeració: "II Guerra Mundial" → "Segona Guerra Mundial", "Pere III el Cerimoniós" → "Pere el Cerimoniós", "Pirineu" → "Pirineus". La categoria desapareix i els seus episodis passen al destí. Com a destí, tria la forma més correcta i habitual en català; si totes dues ho són, la que té més episodis. També serveix per corregir el tipus quan l'equivalent ja existeix al tipus correcte.
- `rollup`: la categoria és vàlida i és un cas concret d'una categoria més general, d'entre els candidats o les categories generals: "Història de la televisió" dins de "Comunicació", "Batalla d'Almansa" dins de "Guerra de Successió". La categoria es manté i els seus episodis també passen a tenir la categoria general, perquè apareguin quan es filtri per qualsevol de les dues.
- `delete`: la categoria no descriu el contingut històric de l'episodi: convidats, experts o historiadors que participen al programa (inclòs el presentador, Josep Maria Solé i Sabaté), noms incomplets que no identifiquen ningú ("Maria"), o etiquetes que no serveixen com a filtre ("Personatges històrics").
- `keep`: la categoria és vàlida i diferent de tots els candidats. Si cal, en pots corregir el nom amb `new_name` (ortografia, nom incomplet, majúscules) o el tipus amb `new_type` quan cap candidat del tipus correcte no hi és equivalent.

## Regles
- `target_id` és obligatori amb `merge` i `rollup`, i ha de ser l'identificador d'un dels candidats d'aquella categoria o d'una categoria general. En qualsevol altre cas, `null`.
- `merge` només uneix noms d'una mateixa cosa. Un cas concret i el tema general que l'inclou són coses diferents: "Història de la televisió" no és "Comunicació", i per tant és `rollup`, no `merge`.
- `rollup` només cap a una categoria del mateix tipus que n'és el marc directe i evident, mai cap a etiquetes tan àmplies que no filtren res ("Catalunya", "Història"). Mai per a `personatges`, `època` ni `localització`: un episodi ja situat en un lloc concret no ha de dur també el territori que el conté.
- `new_name` i `new_type` només amb `keep`; si no hi ha res a corregir, `null`.
- En cas de dubte entre `merge` i `keep`, tria `keep`: fusionar dues coses diferents és pitjor que deixar un duplicat. Noms semblants no volen dir el mateix: "Guerra de Corea" i "Guerra de Crimea" són guerres diferents. En cas de dubte entre `rollup` i `keep`, tria `keep`.
- `reason`: una frase curta que justifiqui la decisió.
- Retorna exactament una decisió per a cada categoria de la llista, amb el seu `id`.

# CATEGORIES GENERALS
{general}

# CATEGORIES A REVISAR
{categories}
"""


def _format_review_item(item: dict) -> str:
    lines = [_format_review_category(item)]
    if item["titles"]:
        titles = "; ".join(f'"{title}"' for title in item["titles"])
        lines.append(f"Episodis: {titles}")
    lines.append("Candidats:")
    lines += [
        f"- {_format_review_category(candidate)}"
        for candidate in item["candidates"]
    ] or ["- (cap)"]
    return "\n".join(lines)


def _format_review_category(category: dict) -> str:
    return f'[{category["id"]}] {category["key"]} · "{category["name"]}" · {category["episodes"]} episodis'
