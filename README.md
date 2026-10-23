# En Guàrdia

Arxiu **no oficial** del programa
[En Guàrdia!](https://www.3cat.cat/3cat/en-guardia/)
de **Catalunya Ràdio**.

Aquest projecte organitza i indexa informació pública del programa
per facilitar la cerca, la navegació i el filtratge mitjançant una
interfície alternativa.

**Projecte independent**
Aquest projecte **no està afiliat ni avalat** per Catalunya Ràdio
ni per la Corporació Catalana de Mitjans Audiovisuals (CCMA).

---

## Desenvolupament

Requisits: [Docker](https://www.docker.com/) i [Bun](https://bun.sh/).
Les ordres habituals són al [`Makefile`](Makefile).

Copia els fitxers d'entorn (si encara no existeixen) i instal·la les
dependències del frontend:

```bash
make setup
```

Després emplena `backend/.env` i `frontend/.env` amb els teus valors.

Aixeca el backend (FastAPI + Postgres) i el frontend (SvelteKit):

```bash
make start-backend
make start-frontend
```

El frontend queda disponible a `http://localhost:5173` i l'API a
`http://localhost:8000`. Les migracions s'apliquen automàticament a
l'arrencada del backend. Per aturar-lo, `make stop-backend` (les
dades de la base de dades es conserven).

Per poblar la base de dades, classificar episodis amb IA o afegir
migracions, mira els scripts a `backend/commands/` i les tasques a
`backend/tasks/`. La classificació necessita una `OPENAI_API_KEY`.

Les tasques en segon pla (Celery + Redis) estan darrere d'un perfil de
Docker Compose i no s'aixequen per defecte. Si les necessites:

```bash
make start-celery
```

Per executar els tests del backend:

```bash
make test-backend
```

El `Makefile` també té ordres per regenerar el client de l'API
(`make generate-client`) i per formatar i revisar el frontend
(`make lint-frontend`).

---

# Avís legal

El codi font d’aquest projecte està publicat sota la llicència MIT.

Aquesta llicència s’aplica exclusivament al codi i no concedeix cap dret
sobre continguts de tercers.

Tots els drets sobre els podcasts, àudios, textos, marques i materials
relacionats amb En Guàrdia! pertanyen als seus respectius titulars.

L’ús d’aquest programari és responsabilitat de l’usuari final, que ha
d’assegurar-se de complir la normativa i condicions aplicables.
