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

Copia els fitxers d'entorn i emplena'ls amb els teus valors:

```bash
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env
```

Aixeca el backend (FastAPI + Postgres) i el frontend (SvelteKit):

```bash
docker compose up -d
cd frontend && bun install && bun run dev
```

El frontend queda disponible a `http://localhost:5173` i l'API a
`http://localhost:8000`. Les migracions s'apliquen automàticament a
l'arrencada del backend.

Per poblar la base de dades, classificar episodis amb IA o afegir
migracions, mira els scripts a `backend/commands/` i les tasques a
`backend/tasks/`. La classificació requereix `OPENAI_API_KEY`.

Les tasques en segon pla (Celery + Redis) estan darrere d'un perfil de
Docker Compose i no s'aixequen per defecte. Si les necessites:

```bash
docker compose --profile celery up -d
```

Els tests del backend s'executen contra Postgres, en una base de dades
dedicada el nom de la qual ha d'acabar en `_test`. Crea-la un cop i
executa els tests dins del contenidor del backend (substitueix `user` i
`password` pels valors del teu `backend/.env`):

```bash
docker compose exec postgres createdb -U user en_guardia_test
docker compose exec -e DATABASE_URL=postgresql://user:password@postgres:5432/en_guardia_test backend python -m pytest
```

Les migracions s'apliquen automàticament abans dels tests, i cada test
s'executa dins d'una transacció que es desfà en acabar.

---

# Avís legal

El codi font d’aquest projecte està publicat sota la llicència MIT.

Aquesta llicència s’aplica exclusivament al codi i no concedeix cap dret
sobre continguts de tercers.

Tots els drets sobre els podcasts, àudios, textos, marques i materials
relacionats amb En Guàrdia! pertanyen als seus respectius titulars.

L’ús d’aquest programari és responsabilitat de l’usuari final, que ha
d’assegurar-se de complir la normativa i condicions aplicables.
