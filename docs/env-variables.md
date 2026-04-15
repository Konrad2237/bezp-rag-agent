# Zmienne środowiskowe

> Lista wszystkich zmiennych środowiskowych potrzebnych do uruchomienia systemu.
>
> Data: 2026-04-14

---

## Backend (Railway)

| Zmienna | Skąd wziąć | Opis |
|---|---|---|
| ANTHROPIC_API_KEY | console.anthropic.com → API Keys | Klucz do Claude Sonnet i Haiku |
| OPENAI_API_KEY | platform.openai.com → API Keys | Klucz do embeddingów (text-embedding-3-small) |
| SUPABASE_URL | Supabase dashboard → Settings → API → URL | URL projektu Supabase |
| SUPABASE_SERVICE_ROLE_KEY | Supabase dashboard → Settings → API → service_role | Klucz z pełnym dostępem (omija RLS). TYLKO backend! |
| SUPABASE_ANON_KEY | Supabase dashboard → Settings → API → anon | Klucz publiczny (ograniczony przez RLS) |
| PROMPT_VERSION | Ręcznie ustawiasz | Aktualna wersja PROMPT-01, np. "v1.0" |
| ENVIRONMENT | Ręcznie | "development" lub "production" |
| ALLOWED_ORIGINS | Ręcznie | URL frontendu dla CORS, np. "https://twoja-strona.vercel.app" |

### Post-MVP (Stripe)

| Zmienna | Skąd wziąć | Opis |
|---|---|---|
| STRIPE_SECRET_KEY | Stripe dashboard → Developers → API Keys | Klucz Stripe do tworzenia sesji checkout |
| STRIPE_WEBHOOK_SECRET | Stripe dashboard → Developers → Webhooks | Secret do weryfikacji podpisu webhooków |

---

## Frontend (Vercel)

| Zmienna | Skąd wziąć | Opis |
|---|---|---|
| NEXT_PUBLIC_SUPABASE_URL | Supabase dashboard → Settings → API → URL | Ten sam co na backendzie |
| NEXT_PUBLIC_SUPABASE_ANON_KEY | Supabase dashboard → Settings → API → anon | Klucz publiczny. NIGDY service_role! |
| NEXT_PUBLIC_API_URL | Railway → Settings → Domains | URL backendu, np. "https://twoja-apka.up.railway.app" |

---

## Zasady bezpieczeństwa

### NIGDY nie wstawiaj na frontend

- SUPABASE_SERVICE_ROLE_KEY — daje pełny dostęp do bazy z pominięciem RLS
- ANTHROPIC_API_KEY — każdy mógłby używać Twojego konta API
- OPENAI_API_KEY — j.w.
- STRIPE_SECRET_KEY — j.w.

### Prefiks NEXT_PUBLIC_

W Next.js prefiks `NEXT_PUBLIC_` oznacza "ta zmienna będzie widoczna w przeglądarce w JavaScript bundle". Wszystko z tym prefiksem jest publiczne — dlatego tam trafiają TYLKO anon key i URL-e.

Zmienne BEZ tego prefiksu są dostępne tylko po stronie serwera (API routes, getServerSideProps).

### Lokalny development

Plik `.env.local` w katalogu projektu (backend i frontend mają osobne). MUSI być w `.gitignore` — to PIERWSZY plik który dodajesz do .gitignore przed jakimkolwiek commitem.

### Rotacja kluczy

Co 3 miesiące wygeneruj nowe klucze API (Anthropic, OpenAI). Zaktualizuj w Railway i Vercel. Stare klucze dezaktywuj.

---

## Szablon .env.local

### Backend

```
# AI Models
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...

# Supabase
SUPABASE_URL=https://xxxx.supabase.co
SUPABASE_SERVICE_ROLE_KEY=eyJ...
SUPABASE_ANON_KEY=eyJ...

# App
PROMPT_VERSION=v1.0
ENVIRONMENT=development
ALLOWED_ORIGINS=http://localhost:3000
```

### Frontend

```
NEXT_PUBLIC_SUPABASE_URL=https://xxxx.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=eyJ...
NEXT_PUBLIC_API_URL=http://localhost:8000
```
