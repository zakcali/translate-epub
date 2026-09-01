# 📚 translate-epub

A fast, multithreaded CLI tool to translate English EPUB books to Turkish (or any language) using modern LLMs via OpenRouter (e.g., **Google Gemini 3.7 Flash**, **DeepSeek-V4 Flash**).

Unlike complex, brittle DOM scrapers or slow autonomous agents, `translate-epub` uses a streamlined, concurrent pipeline that translates full book chapters in parallel while strictly preserving XHTML/XML tags, CSS classes, inline styling, and metadata.

Two scripts are included:

| Script | Use when... |
| :--- | :--- |
| **`translate-epub.py`** | You just want fast, cheap, single-model translation. |
| **`translate-epub-fallback-model.py`** | You want resilience against a model refusing/censoring individual chapters — it automatically retries those files with a second model instead of leaving them permanently failed. |

---

## ✨ Features

- ⚡ **High-Speed Multithreading:** Translates up to 8+ chapters simultaneously, finishing an entire 300-page book in **under 1 minute**.
- 🛡️ **Strict Tag & Layout Preservation:** Keeps all XHTML tags (`<p>`, `<span>`, `<div>`, `<em>`), DOCTYPEs, namespaces, IDs, and CSS classes completely intact.
- 💾 **Resume / Checkpoint System:** Automatically logs progress to a local checkpoint. If interrupted (e.g., via `Ctrl+C` or network timeout), re-running the script immediately resumes where it left off without re-translating completed files.
- 🔒 **Atomic File Writes:** Writes translations to temporary files before atomically replacing them (`os.replace`), preventing corrupted or half-written chapters.
- 📦 **Standard EPUB Compliant:** Correctly packages the resulting `.epub` archive according to IDPF/W3C standards (storing uncompressed `mimetype` first) for full compatibility with Apple Books, Calibre, Kindle, and Thorium Reader.
- 📊 **Live Real-Time Progress Tracker:** Displays completed file percentages, elapsed per-chapter timings, and total duration.
- 🛟 **Automatic Model Fallback** *(fallback script only)*: If the primary model refuses or censors a chapter (common with sensitive nonfiction — mental illness, violence, medical, etc.), that file is instantly retried with a secondary model instead of being marked failed.
- 🚫 **Repackaging Safety Gate:** The final `.epub` is only assembled if every chapter is verified `COMPLETED` in the progress file — a partially translated book is never silently packaged.

---

## 🚀 Quick Start

### 1. Prerequisites

- Python 3.10+ (or [uv](https://github.com/astral-sh/uv))
- An [OpenRouter API key](https://openrouter.ai/) (or any OpenAI-compatible endpoint)

### 2. Installation

Clone the repository:
```bash
git clone https://github.com/zakcali/translate-epub.git
cd translate-epub
```

Install dependencies:
```bash
# Using pip
pip install openai

# Or instantly with uv (recommended)
uv pip install openai
```

### 3. Set Your API Key

Export your OpenRouter key in your terminal session:
```bash
export OPENROUTER_API_KEY="sk-or-v1-your-key-here"
```

*(Tip: Add this line to your `~/.zshrc` or `~/.bashrc` to make it permanent).*

---

## 📖 Usage

### Option A — `translate-epub.py` (single model)

1. Place your target `.epub` file into the project directory (or configure the filename inside the script).
2. Edit configuration parameters at the top of the script if needed:

```python
# ------------ CONFIGURATION ------------
MODEL = "google/gemini-3.7-flash"  # or "deepseek/deepseek-v4-flash"
TARGET_LANG = "Turkish"
INPUT_EPUB = "Your-Book-Title.epub"
MAX_WORKERS = 8  # Parallel translation threads
MAX_RETRIES = 3  # Retry attempts per chapter
# ---------------------------------------
```

3. Run the translation:
```bash
# With standard Python
python3 translate-epub.py

# Or with uv
uv run translate-epub.py
```

### Option B — `translate-epub-fallback-model.py` (with automatic fallback)

Same setup, but with two models configured instead of one:

```python
# ------------ CONFIGURATION ------------
PRIMARY_MODEL = "google/gemini-3.7-flash"
FALLBACK_MODEL = "deepseek/deepseek-v4-flash"  # used automatically if PRIMARY_MODEL refuses/censors
TARGET_LANG = "Turkish"
INPUT_EPUB = "Your-Book-Title.epub"
MAX_WORKERS = 8   # Parallel threads
MAX_RETRIES = 3    # Retries per model on transient errors (timeouts, rate limits, etc.)
# ---------------------------------------
```

Run it the same way:
```bash
python3 translate-epub-fallback-model.py
# or
uv run translate-epub-fallback-model.py
```

**How the fallback logic decides what to retry:**
- A **refusal/censorship** (the model returns empty or null content) skips straight to `FALLBACK_MODEL` — no wasted retries on a model that already declined.
- A **transient error** (timeout, rate limit, network blip) retries the *same* model up to `MAX_RETRIES` times with backoff before moving to the fallback model.
- The progress file records which model actually translated each chapter, so you can audit afterward which files needed the fallback.

---

## 🖥️ Example Terminal Output

```text
📦 Extracting 'your favourite book.epub'...
🤖 Primary model:  google/gemini-3.7-flash
🛟 Fallback model: deepseek/deepseek-v4-flash (used automatically on refusal/censorship)
🚀 Processing 25 files in parallel (8 threads)...

[01/25] (  4.0%) [✓] Finished: title.xhtml                         ( 6.6s)
[02/25] (  8.0%) [✓] Finished: preface.xhtml                       ( 8.3s)
[03/25] ( 12.0%) [✓] Finished: about-this-book.xhtml               (12.6s)
[04/25] ( 16.0%) [✓] Finished: foreword.xhtml                      (13.2s)
[05/25] ( 20.0%) [✓] Finished: toc.ncx                             (54.7s)
[06/25] ( 24.0%) [⚡] Finished: chapter-6.xhtml                     (98.5s) [fallback: deepseek/deepseek-v4-flash]
[07/25] ( 28.0%) [✓] Finished: chapter-4.xhtml                     (114.0s)
...
[25/25] (100.0%) [✓] Finished: chapter-7.xhtml                     (136.6s)

3. Packaging into 'your favourite book-translated.epub'...

🎉 DONE! All 25 files completed in 151.2s.
📁 Output File: your favourite book-translated.epub
```

---

## ⚙️ Supported Models & Cost Estimates

You can choose any model available on OpenRouter by changing the `MODEL` (or `PRIMARY_MODEL` / `FALLBACK_MODEL`) setting:

| Model | Speed | Cost Per Book (~100k words) | Recommended For |
| :--- | :--- | :--- | :--- |
| **`google/gemini-3.7-flash`** | ⚡ Ultra-fast (~200 tps) | **~$0.35 – $1.00** | **Production & high-fluency reading** |
| **`deepseek/deepseek-v4-flash`** | 🚀 Fast | **~$0.04 – $0.08** | **Ultra-budget batch processing, and as a fallback for content Gemini declines to translate** |

---

## 🛠️ How It Works

1. **Extraction:** Unpacks the EPUB archive into a local temporary workspace (`epub_quick_work`).
2. **Detection:** Identifies all `.xhtml`, `.html`, `.htm`, and `.ncx` navigation files recursively.
3. **Concurrent Translation:** Spawns a `ThreadPoolExecutor` worker pool. Each thread:
   - Reads the raw XHTML structure.
   - Prompts the LLM with strict instructions to preserve all XML/HTML tags and attributes.
   - *(Fallback script only)* If the model refuses or returns empty content, immediately retries the same chapter with the fallback model.
   - Atomically saves the translated file to disk.
   - Records the file status (and, in the fallback script, which model translated it) in `translation_progress.json`.
4. **Validation & Packaging:** Re-verifies every target file is marked `COMPLETED` in the progress file before repacking into a clean, standard `-translated.epub` file. If any chapter is missing, failed, or unverified, packaging is skipped so a partial book is never shipped — just re-run the script to pick up the remaining files.

---

## 📄 License

This project is licensed under the [MIT License](LICENSE).
