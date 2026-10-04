# 🚀 Przewodnik Wdrożeniowy dla Zespołu (Developer & Architecture Onboarding)
## Autonomiczny Doradca Grantowy i RAG Regionalnego Ośrodka Polityki Społecznej w Krakowie (ROPS)

---

## 1. Wprowadzenie i Rola Systemu

System **ROPS Grant & Policy AI Advisor** to produkcyjna platforma oparta na architekturze **Agentic RAG (Retrieval-Augmented Generation)**, zaprojektowana dla jednostek samorządu terytorialnego (JST), ośrodków pomocy społecznej (OPS/CUS) oraz organizacji pozarządowych (NGO) z terenu Województwa Małopolskiego.

Głównym zadaniem systemu jest:
1. **Analiza empiryczna pomysłu** w oparciu o **51 regionalnych raportów diagnostycznych ROPS** (15 104 fragmenty badawcze, 4 195 stron).
2. **Dopasowanie przetestowanych innowacji społecznych** z repozytorium **114 modeli innowacji ROPS**.
3. **Weryfikacja kwalifikowalności do naborów celowych** (aktualnie: *Usługa Wrażliwa – II Nabór*, budżet 600 000 zł, 100% dofinansowania, 5 modeli) oraz transparentne przekierowanie do funduszy systemowych, jeśli pomysł wykracza poza wąski nabór celowy.
4. **Automatyczna konstrukcja dokumentu aplikacyjnego (dossier)** w układzie triady oceny ROPS (Działania merytoryczne 80%, Promocja i WCAG 2.1 3.3%, Zarządzanie 16.7%).
5. **Generowanie publikacyjnego dokumentu PDF A4** i wysyłka przez protokół SMTP.

> [!NOTE]
> Interfejs webowy pod adresem `/` oraz `/agent-ui` jest **referencyjnym klientem demonstracyjnym** (Sample UI). Poniższa specyfikacja umożliwia zespołowi deweloperskiemu podłączenie własnego frontendu, aplikacji mobilnej, bota lub zewnętrznego systemu ERP/CRM.

---

## 2. Środowiska, Adresy Bazowe i Autoryzacja

### Adresy URL
- **Produkcja (Coolify)**: `http://ohzlsc0rzubuinsvjuapujke.57.131.158.238.sslip.io`
- **Lokalne środowisko deweloperskie (Docker)**: `http://localhost:5000`
- **Interaktywna dokumentacja Swagger/OpenAPI**: `http://ohzlsc0rzubuinsvjuapujke.57.131.158.238.sslip.io/docs`
- **Specyfikacja OpenAPI JSON**: `http://ohzlsc0rzubuinsvjuapujke.57.131.158.238.sslip.io/openapi.json`

### Uwierzytelnianie (API Key)
Wszystkie chronione endpointy wymagają przekazania klucza API w jeden z trzech sposobów:
1. **Header HTTP (zalecane)**: `X-API-Key: <TWÓJ_KLUCZ_API>`
2. **Parametr URL**: `?api_key=<TWÓJ_KLUCZ_API>`
3. **Ciało zapytania JSON**: `{"api_key": "<TWÓJ_KLUCZ_API>", ...}`

*Domyślny klucz roboczy w środowisku testowym hackathonu:* `huj_dupa_cycki_2026_hack_yeah_!`

---

## 3. Komponenty Bazy Wiedzy (Kolekcje ChromaDB)

System wykorzystuje osadzoną, persystentną bazę wektorową **ChromaDB** z modelem wektoryzacji **Google Gemini Embedding 2** (`text-embedding-004` / `gemini-embedding-2`) w przestrzeni **3072 wymiarów** (metryka odległości: `cosine`).

```
┌────────────────────────────────────────────────────────────────────────┐
│                        CHROMA VECTOR DATABASE                          │
├────────────────────┬─────────────────────┬─────────────────────────────┤
│ 1. rops_reports    │ 2. rops_innovations │ 3. grants                   │
│ 15 104 fragmentów  │ 114 innowacji       │ 1 595 fragmentów            │
│ 51 raportów ROPS   │ Przetestowane modele│ Nabory grantowe             │
│ (4 195 stron PDF)  │ wdrożeniowe ROPS    │ (w tym Usługa Wrażliwa II)  │
└────────────────────┴─────────────────────┴─────────────────────────────┘
```

| Kolekcja | Liczba Chunków | Źródło i Zawartość | Kluczowe Metadane |
| :--- | :---: | :--- | :--- |
| `rops_reports` | **15 104** | 51 badań regionalnych ROPS (demografia, seniorzy, wykluczenie, bezdomność, piecza zastępcza, CUS/OPS) | `report_id`, `report_title`, `year`, `page_number`, `category` |
| `rops_innovations` | **114** | Przetestowane innowacje społeczne wypracowane w Małopolsce (opis, cel, grupa docelowa, narzędzia) | `innovation_id`, `title`, `target_group`, `status`, `category` |
| `grants` | **1 595** | Regulaminy, ramowe plany wdrożeń i karty oceny merytorycznej naborów ROPS | `grant_id`, `grant_name`, `document_type`, `model_name` |

---

## 4. Parametry Wejściowe Zapytania (Query Components)

Zapytanie kierowane do Agenta składa się z 3 głównych komponentów:

```json
{
  "query": "Koordynator kompleksowej opieki w miejscu zamieszkania oraz wsparcie wytchnieniowe dla opiekunów niesamodzielnych seniorów",
  "powiat": "tarnowski",
  "applicant_type": "JST"
}
```

### Szczegółowy opis parametrów:
1. **`query`** (`string`, wymagane):
   - **Co reprezentuje**: Opis problemu społecznego, diagnozy lokalnej lub koncepcji projektu, który użytkownik chce zrealizować.
   - **Przykłady**:
     - *„Budowa mobilnych łazienek dla osób starszych i z niepełnosprawnościami na terenach wiejskich”*
     - *„Integracja i wsparcie mieszkaniowe dla osób w kryzysie bezdomności”*
     - *„Wsparcie usamodzielnienia młodzieży opuszczającej pieczę zastępczą”*
2. **`powiat`** (`string`, opcjonalne, domyślnie: `"małopolskie"`):
   - **Co reprezentuje**: Nazwa powiatu w Małopolsce (np. `tarnowski`, `nowosądecki`, `krakowski`, `oświęcimski`, `m. Kraków`).
   - **Wpływ na działanie**: Służy do kalkulacji wskaźnika dopasowania terytorialnego (*Territorial Need Benchmark*) i dopasowania specyficznych diagnoz lokalnych.
3. **`applicant_type`** (`string`, opcjonalne, domyślnie: `"JST"`):
   - **Dozwolone wartości**:
     - `"JST"` – Jednostka Samorządu Terytorialnego (Gmina, Powiat, CUS, OPS, PCPR).
     - `"NGO"` – Organizacja Pozarządowa (Stowarzyszenie, Fundacja, KGW).
     - `"PES"` – Podmiot Ekonomii Społecznej / Spółdzielnia Socjalna.
   - **Wpływ na działanie**: Warunkuje ocenę formalną kwalifikowalności wnioskodawcy zgodnie z kryteriami dostępu naboru.

---

## 5. Przegląd Endpointów API

### 1. `GET /health` – Kontrola Stanu Systemu
Zwraca stan kontenera, dostępność klucza Gemini API, liczbę kolekcji ChromaDB oraz aktywny model LLM.
- **Metoda**: `GET`
- **Nagłówki**: `X-API-Key: <key>`
- **Przykładowa odpowiedź**:
```json
{
  "status": "healthy",
  "collections_count": 3,
  "embedding_model": "gemini-embedding-2",
  "generation_model": "gemini-3.8-flash (thinking: high)",
  "auth_enabled": true,
  "admin_auth_enabled": true,
  "chroma_storage": "/app/chroma_data"
}
```

---

### 2. `GET /api/agent/stream` lub `POST /api/agent/stream` – Streaming Agenta w Czasie Rzeczywistym (SSE)
Podstawowy endpoint do budowy interaktywnych interfejsów użytkownika. Wykorzystuje protokół **Server-Sent Events (SSE)**, przekazując progres kroków, logi myślenia, wywołania baz RAG oraz generowane tokeny.

- **Protokół**: `text/event-stream`
- **Metoda**: `GET` lub `POST`
- **Parametry zapytania (GET)**: `?query=...&powiat=tarnowski&applicant_type=JST&api_key=...`
- **Ciało zapytania (POST)**:
```json
{
  "query": "Organizator kompleksowej opieki w miejscu zamieszkania",
  "powiat": "tarnowski",
  "applicant_type": "JST"
}
```

#### Typy Zdarzeń SSE (Event Protocol):
| Nazwa Zdarzenia | Payload (`data: {...}`) | Znaczenie w UI |
| :--- | :--- | :--- |
| `agent_start` | `{"query": "...", "powiat": "..."}` | Rozpoczęcie pipeline'u |
| `step_start` | `{"step": 1, "title": "Diagnoza Potrzeb Społecznych"}` | Aktywacja danego etapu na stepperze UI |
| `thought` | `{"step": 1, "text": "Przeszukiwanie 51 raportów ROPS..."}` | Wewnętrzne wnioskowanie agenta |
| `tool_call` | `{"tool": "query_reports", "query": "..."}` | Wywołanie zapytania wektorowego do bazy |
| `tool_result` | `{"tool": "query_reports", "count": 5, "top_match": "..."}` | Wyniki z bazy wektorowej |
| `stream_delta` | `{"delta": "## 1. Karta Oceny..."}` | Kawałki generowanego tekstu Markdown |
| `agent_complete` | `{"status": "completed", "scorecard": {...}}` | Zakończenie pracy; dane podsumowujące |
| `error` | `{"message": "Treść błędu"}` | Błąd krytyczny |

---

### 3. `POST /api/agent/evaluate` – Synchroniczna Ewaluacja Pomysłu
Dla klientów backend-to-backend, którzy nie potrzebują streamingu kroków, a kompletnego wyniku w jednym obiekcie JSON.

- **Metoda**: `POST`
- **Nagłówki**: `Content-Type: application/json`, `X-API-Key: <key>`
- **Request Body**:
```json
{
  "query": "Wsparcie opiekunów niesamodzielnych seniorów w powiecie tarnowskim",
  "powiat": "tarnowski",
  "applicant_type": "JST"
}
```
- **Response Body**:
```json
{
  "status": "success",
  "query": "Wsparcie opiekunów niesamodzielnych seniorów...",
  "powiat": "tarnowski",
  "applicant_type": "JST",
  "scorecard": {
    "evidence_alignment_score": 34.7,
    "urgency_index": 24.0,
    "territorial_benchmark": 19.5,
    "innovation_feasibility": 8.5,
    "grant_eligibility_score": 10.0,
    "total_score": 96.7,
    "rating_class": "Klasa A (Wysoki Priorytet)"
  },
  "grant_match": {
    "is_eligible": true,
    "grant_name": "Usługa Wrażliwa - II Nabór",
    "distance": 0.28,
    "similarity_pct": 72.0,
    "matched_model": "Organizator kompleksowej opieki w miejscu zamieszkania",
    "max_funding_pln": 600000.0,
    "own_contribution_pct": 0.0
  },
  "scanned_sources": [
    {
      "source": "rops_reports",
      "title": "Wyzwania i potrzeby sektora opiekuńczego w Małopolsce",
      "year": 2026,
      "page": 42,
      "relevance": 0.94
    }
  ],
  "markdown_report": "# 📋 Raport Analityczny i Uzasadnienie Merytoryczne..."
}
```

---

### 4. `POST /api/agent/send-email` – Wysyłka Raportu z Załącznikiem PDF (SMTP)
Generuje oficjalne, sformatowane dossier aplikacyjne w formacie **PDF A4** (z polskimi fontami `DejaVuSans`, tabelami, nagłówkami i stopkami z paginacją) oraz wysyła je na wskazany adres e-mail przez skonfigurowany serwer SMTP.

- **Metoda**: `POST`
- **Nagłówki**: `Content-Type: application/json`, `X-API-Key: <key>`
- **Request Body**:
```json
{
  "recipient_email": "dyrektor@ops-gmina.pl",
  "recipient_name": "Ośrodek Pomocy Społecznej",
  "query": "Koordynator kompleksowej opieki w miejscu zamieszkania",
  "markdown_report": "# 📋 Dossier Aplikacyjne ROPS\n\nTreść wygenerowana przez Agenta..."
}
```
- **Response Body**:
```json
{
  "status": "success",
  "mock": false,
  "pdf_attached": true,
  "recipient": "dyrektor@ops-gmina.pl",
  "message": "Raport w formacie PDF został pomyślnie wysłany na adres dyrektor@ops-gmina.pl."
}
```
*(Jeśli zmienne środowiskowe SMTP nie są ustawione, API zwraca `"mock": true` i symuluje pomyślną wysyłkę).*

---

### 5. Bezpośrednie Endpointy Wyszukiwania RAG

Dla modułów wyszukiwarki lub własnych agentów udostępniono niskopoziomowe metody odpytywania bazy wektorowej:

#### A. Multi-kolekcyjna Wyszukiwarka Agregująca: `POST /api/rag/search`
Przeszukuje równocześnie raporty, innowacje i dokumentację grantową.
```json
{
  "query": "mobilne łazienki osoby starsze",
  "collections": ["rops_reports", "rops_innovations", "grants"],
  "top_k": 3
}
```

#### B. Wyszukiwarka Raportów Diagnostycznych: `POST /api/reports/query`
Dedykowana kolekcji `rops_reports` z możliwością filtrowania po roku i kategorii.
```json
{
  "query": "przeciwdziałanie bezdomności zima",
  "top_k": 5,
  "filter": {
    "year": 2026,
    "category": "bezdomnosc"
  }
}
```

#### C. Wyszukiwarka Innowacji Społecznych: `POST /api/query`
Dedykowana kolekcji `rops_innovations`.
```json
{
  "query": "wsparcie wytchnieniowe opiekunów",
  "n_results": 3
}
```

---

## 6. Architektura 5 Kroków Agenta (The 5-Step Pipeline)

Podczas wywołania `/api/agent/stream` agent realizuje sekwencyjny potok logiczny:

```
┌────────────────────────────────────────────────────────────────────────┐
│                        AGENT EXECUTION PIPELINE                        │
└────────────────────────────────────────────────────────────────────────┘
    │
    ▼
┌────────────────────────────────────────────────────────────────────────┐
│ KROK 1: DIAGNOZA POTRZEB SPOŁECZNYCH (EVIDENCE RETRIEVAL)              │
│ • Zapytanie do `rops_reports` (15k chunków).                           │
│ • Ekstrakcja twardych wskaźników, cytatów, tytułów raportów i stron.   │
│ • Obliczenie wskaźników Evidence Alignment & Urgency Index.            │
└──────────────────────────────────┬─────────────────────────────────────┘
                                   │
                                   ▼
┌────────────────────────────────────────────────────────────────────────┐
│ KROK 2: DOPASOWANIE INNOWACJI SPOŁECZNYCH (INNOVATION MATCHING)        │
│ • Zapytanie do `rops_innovations` (114 modeli).                        │
│ • Identyfikacja przetestowanego rozwiązania gotowego do wdrożenia.     │
│ • Pobranie metodyki, narzędzi i grupy docelowej innowacji.             │
└──────────────────────────────────┬─────────────────────────────────────┘
                                   │
                                   ▼
┌────────────────────────────────────────────────────────────────────────┐
│ KROK 3: WERYFIKACJA NABORU CELOWEGO (GRANT COMPLIANCE & DISTANCE)      │
│ • Weryfikacja wektorowa odległości do naboru Usługa Wrażliwa II.       │
│ • Próg kwalifikowalności: Cosine Distance <= 0.46 (Zbieżność >= 54%).   │
│ • Jeśli dystans > 0.46: transparentny brak sztucznego naginania,       │
│   rekomendacja otwartych źródeł finansowania (FEdM, PFRON, Maluch+).   │
└──────────────────────────────────┬─────────────────────────────────────┘
                                   │
                                   ▼
┌────────────────────────────────────────────────────────────────────────┐
│ KROK 4: KOSZTORYS I TRIADA OCENY ROPS (BUDGET & FEASIBILITY)           │
│ • Budżet: do 600 000,00 PLN (0% wkładu własnego).                      │
│ • Rygorystyczny podział kosztów:                                       │
│   - Działania merytoryczne: 80.0% (480 000 zł)                         │
│   - Promocja i dostępność cyfrowa WCAG 2.1: 3.3% (20 000 zł)          │
│   - Zarządzanie i koordynacja: 16.7% (100 000 zł)                      │
└──────────────────────────────────┬─────────────────────────────────────┘
                                   │
                                   ▼
┌────────────────────────────────────────────────────────────────────────┐
│ KROK 5: SYNTEZA DOSSIER, PDF I EKSPORT (SYNTHESIS & REPORT)            │
│ • Generowanie pełnego dokumentu Markdown w prostym, urzędowym języku.  │
│ • Gotowość do natychmiastowej konwersji do PDF i wysyłki e-mailem.     │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 7. Przykłady Integracji Kodu dla Zespołu

### A. JavaScript / TypeScript – Pobieranie Strumienia SSE (Frontend Client)

```typescript
const query = "Koordynator opieki w miejscu zamieszkania";
const powiat = "tarnowski";
const apiKey = "huj_dupa_cycki_2026_hack_yeah_!";

const url = `/api/agent/stream?query=${encodeURIComponent(query)}&powiat=${encodeURIComponent(powiat)}&api_key=${encodeURIComponent(apiKey)}`;
const eventSource = new EventSource(url);

eventSource.addEventListener('step_start', (e) => {
  const data = JSON.parse(e.data);
  console.log(`[Krok ${data.step}] ${data.title}`);
});

eventSource.addEventListener('thought', (e) => {
  const data = JSON.parse(e.data);
  console.log(`💡 Myśl: ${data.text}`);
});

eventSource.addEventListener('stream_delta', (e) => {
  const data = JSON.parse(e.data);
  // Dopisuj przychodzące tokeny do podglądu markdown
  document.getElementById('reportOutput').textContent += data.delta;
});

eventSource.addEventListener('agent_complete', (e) => {
  const data = JSON.parse(e.data);
  console.log('✅ Raport wygenerowany!', data.scorecard);
  eventSource.close();
});

eventSource.onerror = (err) => {
  console.error('Błąd połączenia SSE:', err);
  eventSource.close();
};
```

---

### B. Python – Synchroniczne Wywołanie i Wysyłka E-mail

```python
import requests

BASE_URL = "http://ohzlsc0rzubuinsvjuapujke.57.131.158.238.sslip.io"
HEADERS = {"X-API-Key": "huj_dupa_cycki_2026_hack_yeah_!"}

# 1. Wywołanie ewaluacji pomysłu
eval_response = requests.post(
    f"{BASE_URL}/api/agent/evaluate",
    headers=HEADERS,
    json={
        "query": "Organizator kompleksowej opieki w miejscu zamieszkania",
        "powiat": "tarnowski",
        "applicant_type": "JST"
    }
)
result = eval_response.json()
print("Ocena punktowa:", result["scorecard"]["total_score"])

# 2. Wysłanie wygenerowanego raportu PDF na e-mail
email_response = requests.post(
    f"{BASE_URL}/api/agent/send-email",
    headers=HEADERS,
    json={
        "recipient_email": "kontakt@ops-gmina.pl",
        "recipient_name": "Gminny Ośrodek Pomocy Społecznej",
        "query": result["query"],
        "markdown_report": result["markdown_report"]
    }
)
print("Status wysyłki PDF:", email_response.json())
```

---

### C. cURL – Szybki Test z Terminala

```bash
# 1. Sprawdzenie stanu bazy i modeli
curl -s -H "X-API-Key: huj_dupa_cycki_2026_hack_yeah_!" \
  http://ohzlsc0rzubuinsvjuapujke.57.131.158.238.sslip.io/health

# 2. Bezpośrednie przeszukanie raportów ROPS
curl -s -X POST \
  -H "Content-Type: application/json" \
  -H "X-API-Key: huj_dupa_cycki_2026_hack_yeah_!" \
  -d '{"query": "opiekunowie faktyczni seniorów zmęczenie", "top_k": 2}' \
  http://ohzlsc0rzubuinsvjuapujke.57.131.158.238.sslip.io/api/reports/query
```

---

## 8. Zmienne Środowiskowe Kontenera (DevOps / Coolify)

W panelu Coolify (zakładka **Environment Variables**) skonfigurowane są następujące zmienne:

| Zmienna | Przeznaczenie | Wartość produkcyjna |
| :--- | :--- | :--- |
| `GEMINI_API_KEY` | Klucz Google Gemini API (modele LLM i embeddings) | Klucz Google AI Studio |
| `GEMINI_EMBEDDING_MODEL` | Nazwa modelu embeddingów | `gemini-embedding-2` |
| `CHROMA_PERSIST_DIRECTORY` | Ścieżka do wolumenu ChromaDB w kontenerze | `/app/chroma_data` |
| `API_AUTH_KEY` | Klucz autoryzacji zapytań użytkowników | `huj_dupa_cycki_2026_hack_yeah_!` |
| `ADMIN_API_KEY` | Klucz administracyjny (zarządzanie kolekcjami) | Klucz admina |
| `SMTP_HOST` | Host serwera pocztowego (np. `smtp.gmail.com`) | Serwer pocztowy |
| `SMTP_PORT` | Port SMTP (np. `587` lub `465`) | `587` |
| `SMTP_USERNAME` | Użytkownik / e-mail konta wysyłkowego | Adres e-mail |
| `SMTP_PASSWORD` | Hasło aplikacji (App Password) | Hasło aplikacji |
| `SMTP_FROM_EMAIL` | Adres nadawcy wiadomości | Adres nadawcy |
| `SMTP_FROM_NAME` | Nazwa nadawcy (np. `Doradca Grantowy ROPS`) | Nazwa |
| `SMTP_USE_TLS` | Szyfrowanie STARTTLS (`true` / `false`) | `true` |
