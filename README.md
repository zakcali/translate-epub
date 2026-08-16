# 📚 translate-epub

A fast, multithreaded CLI tool to translate English EPUB books to Turkish (or any language) using modern LLMs via OpenRouter (e.g., **Google Gemini 3.7 Flash**, **DeepSeek-V4 Flash**).

Unlike complex, brittle DOM scrapers or slow autonomous agents, `translate-epub` uses a streamlined, concurrent pipeline that translates full book chapters in parallel while strictly preserving XHTML/XML tags, CSS classes, inline styling, and metadata.

---

## ✨ Features

- ⚡ **High-Speed Multithreading:** Translates up to 8+ chapters simultaneously, finishing an entire 300-page book in **under 1 minute**.
- 🛡️ **Strict Tag & Layout Preservation:** Keeps all XHTML tags (`<p>`, `<span>`, `<div>`, `<em>`), DOCTYPEs, namespaces, IDs, and CSS classes completely intact.
- 💾 **Resume / Checkpoint System:** Automatically logs progress to a local checkpoint. If interrupted (e.g., via `Ctrl+C` or network timeout), re-running the script immediately resumes where it left off without re-translating completed files.
- 🔒 **Atomic File Writes:** Writes translations to temporary files before atomically replacing them (`os.replace`), preventing corrupted or half-written chapters.
- 📦 **Standard EPUB Compliant:** Correctly packages the resulting `.epub` archive according to IDPF/W3C standards (storing uncompressed `mimetype` first) for full compatibility with Apple Books, Calibre, Kindle, and Thorium Reader.
- 📊 **Live Real-Time Progress Tracker:** Displays completed file percentages, elapsed per-chapter timings, and total duration.

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

1. Place your target `.epub` file into the project directory (or configure the filename inside the script).
2. Edit configuration parameters at the top of `translate_epub.py` if needed:

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
python3 translate_epub.py

# Or with uv
uv run translate_epub.py
```

---

## 🖥️ Example Terminal Output

```text
📦 Extracting 'Sutskevers List-Foundational ideas of modern AI.epub'...
🤖 Model: google/gemini-3.7-flash
🚀 Processing 25 files in parallel (8 threads)...

[01/25] (  4.0%) [✓] Finished: title.xhtml                         ( 6.6s)
[02/25] (  8.0%) [✓] Finished: preface.xhtml                       ( 8.3s)
[03/25] ( 12.0%) [✓] Finished: about-this-book.xhtml               (12.6s)
[04/25] ( 16.0%) [✓] Finished: foreword.xhtml                      (13.2s)
[05/25] ( 20.0%) [✓] Finished: toc.ncx                             (54.7s)
[06/25] ( 24.0%) [✓] Finished: chapter-6.xhtml                     (98.5s)
[07/25] ( 28.0%) [✓] Finished: chapter-4.xhtml                     (114.0s)
...
[25/25] (100.0%) [✓] Finished: chapter-7.xhtml                     (136.6s)

3. Packaging into 'Sutskevers List-Foundational ideas of modern AI-translated.epub'...

🎉 DONE! All 25 files translated successfully in 41.2s.
📁 Output File: Sutskevers List-Foundational ideas of modern AI-translated.epub
```

---

## ⚙️ Supported Models & Cost Estimates

You can choose any model available on OpenRouter by changing the `MODEL` setting:

| Model | Speed | Cost Per Book (~100k words) | Recommended For |
| :--- | :--- | :--- | :--- |
| **`google/gemini-3.7-flash`** | ⚡ Ultra-fast (~200 tps) | **~$0.15 – $0.35** | **Production & high-fluency reading** |
| **`deepseek/deepseek-v4-flash`** | 🚀 Fast | **~$0.04 – $0.08** | **Ultra-budget batch processing** |
| **`google/gemini-2.0-flash`** | ⚡ Ultra-fast | **~$0.08 – $0.12** | **Great balance of speed and cost** |

---

## 🛠️ How It Works

1. **Extraction:** Unpacks the EPUB archive into a local temporary workspace (`epub_quick_work`).
2. **Detection:** Identifies all `.xhtml`, `.html`, and `toc.ncx` navigation files recursively.
3. **Concurrent Translation:** Spawns a `ThreadPoolExecutor` worker pool. Each thread:
   - Reads the raw XHTML structure.
   - Prompts the LLM with strict instructions to preserve all XML/HTML tags and attributes.
   - Atomically saves the translated file to disk.
   - Records the file status in `.translation_progress.json`.
4. **Validation & Packaging:** Verifies that all files were completed without corruption and repacks them into a clean, standard `-translated.epub` file.

---

## 📄 License

This project is licensed under the [MIT License](LICENSE).
