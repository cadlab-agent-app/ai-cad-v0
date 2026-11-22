---
title: Mohamed CAD Lab
emoji: 🛠️
colorFrom: blue
colorTo: gray
sdk: docker
app_port: 7860
pinned: false
---
# Mohamed CAD Lab · v0.1

**A working local prototype, not a finished engineering product.** Choose one of four parametric parts, edit its dimensions in mm, inspect a 3D preview, and download real STEP and STL files. Manual CAD needs no AI key and makes no external requests. The 3D viewer is bundled locally, with no CDN dependency at runtime.

## ابدأ هنا

دي نسخة أولى شغالة محليًا من فكرتك. تختار نوع القطعة، تدخل المقاسات بالمليمتر، وتشوف مجسّم ثلاثي الأبعاد وتنزّل **STEP + STL** حقيقيين. مش برنامج بيرسم أي قطعة من أي صورة. دلوقتي فيه ٤ قوالب محددة:

- لوح تثبيت بأربع ثقوب `plate`
- جلبة أو فاصل دائري `bushing`
- زاوية تثبيت بحرف L، بثقبين في القاعدة `bracket`
- علبة مفتوحة من فوق، من غير غطا `enclosure`

كل قطعة بيتفحص إنها جسم واحد سليم، حجمها موجب ومطابق للحساب، وأبعادها الخارجية مطابقة للمطلوب. ده **مش اعتماد هندسي** ولا ضمان إن القطعة تتحمل حمل أو مناسبة للتصنيع. راجع المقاسات والتفاوتات والخامة وإعدادات الطباعة بنفسك.

### التثبيت والتشغيل

تم التجريب على Linux x86_64 وPython 3.10.12. يُنصح تبدأ بـPython 3.10 في بيئة جديدة. التشغيل على أنظمة أخرى محتاج اختبار، وتوفّر مكتبات OCCT الجاهزة بيعتمد على النظام ومعمارية الجهاز. التثبيت الأول يحتاج إنترنت ومساحة لملفات CAD الثقيلة.

**Linux / macOS:**

```bash
cd ai-cad-v0
python3.10 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

**Windows PowerShell:**

```powershell
cd ai-cad-v0
py -3.10 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

افتح **http://127.0.0.1:8000**. لو تفعيل البيئة مش مسموح في PowerShell، استخدم `.\.venv\Scripts\python.exe` بدل `python` من غير تفعيل. للإيقاف اضغط Ctrl+C. لو المنفذ مشغول بدّل `8000` بـ`8001` وافتح نفس المنفذ في المتصفح.

1. اختار نوع القطعة.
2. عدّل المقاسات. مقاسات الثقوب بالقطر، مش نصف القطر.
3. اضغط إنشاء الموديل.
4. لفّ الموديل بالماوس، وقرّب بعجلة الماوس أو باللمس.
5. نزّل STEP للتعديل الهندسي أو STL للطباعة. استورد STL بوحدة **mm** لأنه لا يخزّن وحدة القياس.

الملفات الناتجة بتتحفظ في `output/<job-id>/`. مش بتتمسح تلقائيًا. امسح محتويات `output` يدويًا والبرنامج مقفول لو عايز توفر مساحة. ملفات أمثلة جاهزة وصور الواجهة موجودة في `examples/`.

### تفعيل «صوّر الاسكتش» (مجاني، من غير كارت)

الميزة مقفولة من غير مفتاح، والتصميم اليدوي شغّال طول الوقت. المزوّد المجاني الموصى به: **Google Gemini (AI Studio)**.

1. افتح https://aistudio.google.com/api-keys وسجّل دخول بحساب Google.
2. وافق على الشروط واضغط **Create API key** (مش هيطلب كارت أو فلوس).
3. انسخ المفتاح وحطّه في السيرفر كمتغيّر بيئة اسمه `GEMINI_API_KEY` (على Railway: Variables ثم New Variable). الموديل الافتراضي `gemini-3.8-flash` ولو خلصت الحصة بيجرّب تلقائيًا `gemini-3.6-flash` ثم `gemini-3.5-flash-lite`.

تنبيه خصوصية: في الباقة المجانية جوجل ممكن تستخدم الصور في تحسين منتجاتها. متبعتش رسومات سرية. OpenAI لسه متاح كبديل مدفوع عن طريق `OPENAI_API_KEY`، وتقدر تجبر اختيار المزوّد بـ`VISION_PROVIDER=gemini` أو `openai`.

الرد مجرد **اقتراح**. بعد التحليل بتظهر شاشة مراجعة فيها نوع القطعة والمقاسات قابلة للتعديل، والمقاسات اللي مش مكتوبة على الرسمة بتتعلّم بلون برتقالي. لازم تأكّد إنك راجعت كل المقاسات قبل الإنشاء. البرنامج لا ينفّذ كود من الصورة أو من رد الذكاء الاصطناعي.

---

## English quick start

Use Python 3.10 in a fresh virtual environment, install `requirements.txt`, then run:

```bash
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Open **http://127.0.0.1:8000**. Full platform setup commands are above. The tested environment is Linux x86_64 / Python 3.10.12. Other platforms have not been tested; OCCT wheels may not exist for every platform/Python combination. This is a **local, single-user** app. Do not bind it to a public interface or deploy it as-is.

### What runs now

| Template | Geometry | Default external bounds (mm) |
|---|---|---|
| `plate` | Rectangular plate, four through-holes; `edge_offset` means hole centre to nearest edge | 80 × 50 × 6 |
| `bushing` | Hollow cylinder | 30 × 30 × 20 |
| `bracket` | L-bracket, upright at x=0, two vertical through-holes in base | 60 × 40 × 50 |
| `enclosure` | Rectangular open-top box, equal wall/floor thickness | 80 × 60 × 30 |

`bracket.height` includes the base thickness. Base hole centres are x=0.65 × length and y=0.25/0.75 × width. There are no holes in its upright. Hole diameters and placements are template constraints, not arbitrary CAD editing.

- build123d 0.10.0 on the OCCT kernel builds actual solids.
- FastAPI 0.115.12 serves a plain HTML/CSS/JS interface, no frontend build step.
- Uvicorn 0.34.2 runs the local server.
- Three.js 0.160.1 with STLLoader and OrbitControls is vendored under `app/static/vendor/`, including its MIT license.
- `requirements.lock.txt` pins the exact installed dependency snapshot. `requirements.txt` includes that snapshot. Browser-testing dependencies are separate.
- The server validates numeric ranges, hole/wall clearance, one-solid topology, positive analytic volume and expected bounding-box dimensions before export. This is a deterministic quality gate, **not an AI self-correction loop**. Invalid geometry is rejected, not silently changed.
- Generated files persist in `output/`. There is no automatic storage cleanup. You may set `CAD_OUTPUT_DIR` before starting the server to change that path.

### Project map

```text
app/
  main.py             Local API, generation/export, downloads
  templates.py        Four templates, parameter schema, checks
  vision.py           Disabled-by-default boundary + optional OpenAI adapter
  static/             No-build bilingual UI and bundled 3D viewer
examples/             Four default STEP/STL pairs and preview screenshots
requirements.txt      Includes exact tested lock
requirements.lock.txt Exact Python dependency snapshot
requirements-dev.txt  Optional Playwright browser smoke test
  tests/              Unit/API/round-trip and optional browser tests
```

### API

Interactive API docs: **http://127.0.0.1:8000/docs**.

- `GET /api/templates`: labels, dimensions, defaults, min/max.
- `GET /api/health`: server status and whether a server key exists. A key being present does not prove provider access.
- `POST /api/generate`: body `{"part_type":"bushing","dimensions":{"outer_diameter":30,"inner_diameter":12,"height":20}}`. Returns measured validation report plus STEP/STL download URLs.
- `GET /api/files/{job_id}/part.step` or `part.stl`: successful exports.
- `POST /api/interpret`: multipart file named `image`. Returns a proposal and `requires_confirmation: true`. Does not generate CAD. Calling this endpoint when a provider key is configured sends the image to that provider and may incur API charges, whether called from Analyze or another client.

### Sketch photo to model (v1)

Flow: upload a photo (PNG/JPEG/WebP, max 5 MB) → the vision model picks one of the 4 templates and reads the mm dimensions → a confirmation screen shows the editable part type and dimensions (unreadable ones are highlighted and filled with template defaults) → the user ticks "I checked every dimension" → the normal validated generation runs → the sketch is shown next to the 3D model. The model only returns data (a template id and numbers). No generated code is ever executed.

Environment variables (server side only):

| Variable | Meaning |
| --- | --- |
| `GEMINI_API_KEY` | Google AI Studio key. Free tier, no credit card. Enables vision with Gemini. |
| `GEMINI_MODEL` | Optional. Default `gemini-3.8-flash`. |
| `GEMINI_MODEL_FALLBACKS` | Optional comma list tried on 404/429/5xx. Default `gemini-3.6-flash,gemini-3.5-flash-lite`. |
| `OPENAI_API_KEY` / `OPENAI_VISION_MODEL` | Paid fallback provider (default model `gpt-4.1-mini`). |
| `VISION_PROVIDER` | Optional `gemini` or `openai`. If unset: Gemini when its key exists, else OpenAI. |
| `VISION_MAX_PER_IP_HOUR` / `VISION_MAX_PER_HOUR` | Rate limits on analyses (defaults 10 and 60) so a public URL cannot exhaust the quota. |

With no key the feature is disabled: `/api/interpret` answers 503, the UI says so, and manual CAD works. Status codes: 413 too large, 415 wrong type, 422 unreadable/unsupported sketch, 429 rate limited, 502 provider failure, 503 disabled.

The live providers have not been exercised with real credentials by the test suite (all tests mock HTTP). Reading quality needs a real-sketch evaluation. Free-tier Gemini prompts may be used by Google to improve its products.

The function boundary is `extract_part(image, mime_type)`; provider code is isolated in `_call_vision_provider()`.

### Verification

```bash
python -m unittest discover -s tests -v
```

The suite (test_cad.py and test_vision.py with fully mocked vision) covers all four API generations, STEP re-import/validity/volume, binary STL structure/bounds/mesh volume, scaled parameters, invalid dimensions, file-path restrictions, static assets, the disabled AI path, bad file headers and a mocked AI proposal. Default STEP/STL samples are included for direct inspection.

Optional browser smoke test:

```bash
python -m pip install -r requirements-dev.txt
python -m playwright install chromium
python tests/browser_smoke.py
```

If Chrome is already installed, set `CAD_CHROME_PATH` to its executable instead of downloading Chromium. The browser test uses port 8765, starts and stops its own server, blocks external requests, generates/previews all four parts, checks old downloads disappear after edits, checks mobile width, and saves screenshots to `examples/`. It was run successfully with installed Chrome, including an offline WebGL preview and zero uncaught JavaScript errors.

### Before turning this into a product

No authentication, user isolation, per-user storage, rate limiting, job queue, hard runtime/memory limits, robust upload decoding, persistence database, automatic file expiry or manufacturing certification is provided. OCCT work is serialized by a process-local lock; run one server worker. Downloads are unguessable job paths, not authenticated authorization. Production needs authenticated ownership checks and a sandboxed job system. API docs and storage must not be exposed publicly as-is.

Input dimensions are limited to 0.5–300 mm plus template-specific fit rules. STL tessellation is 0.05 mm linear / 0.1 rad angular tolerance. STL is a mesh, not an editable feature tree. STEP is editable geometry, not a native SolidWorks feature history. No fillets, threads, assemblies, arbitrary free-form reconstruction or automated engineering decisions are included.

Next useful step: collect a small labelled set of drawings for these exact four templates, evaluate dimension extraction against known truth, and only then add more templates and an explicit measurement-and-correction loop.
