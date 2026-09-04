import os
import sys
import zipfile
import shutil
import re
import time
import json
import threading
from concurrent.futures import ThreadPoolExecutor
from openai import OpenAI

# ------------ CONFIGURATION ------------
PRIMARY_MODEL = "google/gemini-3.8-flash"
FALLBACK_MODEL = "deepseek/deepseek-v4-flash"  # used automatically if PRIMARY_MODEL refuses/censors
TARGET_LANG = "Turkish"
INPUT_EPUB = "Your-Book-Title.epub"
MAX_WORKERS = 8       # Parallel threads
MAX_RETRIES = 3        # Retries per model on transient errors (timeouts, rate limits, etc.)
TEMP_FILE = "translation_progress.json"
# ---------------------------------------

api_key = os.environ.get("OPENROUTER_API_KEY")
if not api_key:
    print("❌ Error: OPENROUTER_API_KEY environment variable is not set.")
    print("Run: export OPENROUTER_API_KEY='your-key' before running this script.")
    sys.exit(1)

client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=api_key,
)

SYSTEM_PROMPT = f"""You are a professional literary translator.
Translate the following XHTML/NCX content from English to {TARGET_LANG}.
STRICT RULES:
1. Preserve all XHTML/XML tags, DOCTYPEs, classes, attributes (id, class, href, src) exactly.
2. Only translate the visible human-readable text inside the tags.
3. Return ONLY the raw XHTML content without markdown fences (no ```xml or ```xhtml)."""

# Thread-safe state
lock = threading.Lock()
completed_count = 0
total_count = 0
failed_files = []


class ContentFilterError(Exception):
    """Raised when the model refuses / censors instead of returning a translation."""
    pass


def load_progress(progress_file):
    if os.path.exists(progress_file):
        try:
            with open(progress_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_progress_atomic(progress_file, progress_data):
    """Atomic write to prevent corruption if Ctrl+C occurs mid-save."""
    with lock:
        tmp_file = progress_file + ".tmp"
        with open(tmp_file, "w", encoding="utf-8") as f:
            json.dump(progress_data, f, indent=2)
        os.replace(tmp_file, progress_file)


def extract_epub_if_needed(epub_path, extract_to):
    if not os.path.exists(extract_to):
        print(f"📦 Extracting '{epub_path}'...")
        with zipfile.ZipFile(epub_path, 'r') as zip_ref:
            zip_ref.extractall(extract_to)
    else:
        print(f"🔄 Resuming existing workspace '{extract_to}'...")


def create_epub(source_dir, output_epub):
    with zipfile.ZipFile(output_epub, 'w') as zip_out:
        mimetype_path = os.path.join(source_dir, 'mimetype')
        if os.path.exists(mimetype_path):
            zip_out.write(mimetype_path, 'mimetype', compress_type=zipfile.ZIP_STORED)
        for root, dirs, files in os.walk(source_dir):
            for file in files:
                if file in ('mimetype', TEMP_FILE) or file.endswith('.tmp'):
                    continue
                file_path = os.path.join(root, file)
                arcname = os.path.relpath(file_path, source_dir)
                zip_out.write(file_path, arcname, compress_type=zipfile.ZIP_DEFLATED)


def call_model(model, content):
    """Call one model once. Returns cleaned translated text or raises."""
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": content}
        ],
        max_tokens=32000,
        temperature=0.2,
    )

    # --- Detect a content-filter refusal rather than a real completion ---
    # OpenRouter/providers often signal a safety block by returning an empty
    # or null `choices` list, or a choice whose message.content is None,
    # instead of raising an HTTP error. That's what produced the
    # "'NoneType' object is not subscriptable" crash.
    if not response.choices:
        raise ContentFilterError(f"{model} returned no choices (likely content filter)")

    choice = response.choices[0]
    finish_reason = getattr(choice, "finish_reason", None)
    message_content = choice.message.content if choice.message else None

    if message_content is None:
        raise ContentFilterError(f"{model} returned empty content (finish_reason={finish_reason})")

    translated = message_content.strip()
    translated = re.sub(r"^```[a-zA-Z]*\n", "", translated)
    translated = re.sub(r"\n```$", "", translated)

    if not translated or len(translated) < 10:
        raise ValueError("Empty or truncated response.")

    return translated


def translate_single_file(file_path, work_dir, progress_file, progress_data):
    global completed_count
    fname = os.path.basename(file_path)
    rel_path = os.path.relpath(file_path, work_dir)

    # 1. Skip already finished files
    if progress_data.get(rel_path) == "COMPLETED":
        with lock:
            completed_count += 1
            percent = (completed_count / total_count) * 100
            print(f"[{completed_count:02d}/{total_count:02d}] ({percent:5.1f}%) [⏩] Already done: {fname}")
        return

    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()

    if not content.strip():
        with lock:
            completed_count += 1
            progress_data[rel_path] = "COMPLETED"
            save_progress_atomic(progress_file, progress_data)
            print(f"[{completed_count:02d}/{total_count:02d}] ({(completed_count/total_count)*100:5.1f}%) [–] Skipped blank: {fname}")
        return

    start_time = time.time()

    # Try the primary model first, then fall back to the secondary model if
    # the primary one refuses/censors. Transient errors (timeouts, rate
    # limits) get retried on the SAME model up to MAX_RETRIES before we give
    # up on it and move to the next one. A content-filter refusal skips
    # straight to the fallback model since retrying won't change anything.
    models_to_try = [PRIMARY_MODEL, FALLBACK_MODEL]
    translated = None
    used_model = None
    last_error = None

    for model in models_to_try:
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                translated = call_model(model, content)
                used_model = model
                break
            except ContentFilterError as e:
                last_error = e
                print(f"    ⚠️  {fname}: {model} refused/censored ({e}) — trying next model")
                break  # no point retrying the same model on a refusal
            except Exception as e:
                last_error = e
                if attempt < MAX_RETRIES:
                    time.sleep(2 * attempt)
                # else: fall through and try next model (if any)
        if translated is not None:
            break

    if translated is None:
        with lock:
            completed_count += 1
            failed_files.append(fname)
            print(f"[{completed_count:02d}/{total_count:02d}] [❌] Failed: {fname} ({last_error})")
        return

    # Atomic write for the translated file
    tmp_file = file_path + ".tmp"
    with open(tmp_file, 'w', encoding='utf-8') as f:
        f.write(translated)
    os.replace(tmp_file, file_path)

    # Save progress immediately, including which model actually did the translation
    progress_data[rel_path] = "COMPLETED"
    progress_data[rel_path + "__model"] = used_model
    save_progress_atomic(progress_file, progress_data)

    elapsed = time.time() - start_time
    with lock:
        completed_count += 1
        percent = (completed_count / total_count) * 100
        tag = "✓" if used_model == PRIMARY_MODEL else "⚡"
        note = "" if used_model == PRIMARY_MODEL else f" [fallback: {used_model}]"
        print(f"[{completed_count:02d}/{total_count:02d}] ({percent:5.1f}%) [{tag}] Finished: {fname:<35} ({elapsed:4.1f}s){note}")


def verify_all_completed(work_dir, progress_file, target_files):
    """
    Hard safety check before packaging: re-read the progress file from disk
    (not just the in-memory failed_files list) and confirm every target file
    is actually marked COMPLETED. Returns list of files that are NOT done.
    """
    progress_data = load_progress(progress_file)
    incomplete = []
    for fp in target_files:
        rel_path = os.path.relpath(fp, work_dir)
        if progress_data.get(rel_path) != "COMPLETED":
            incomplete.append(rel_path)
    return incomplete


def main():
    global total_count
    if not os.path.exists(INPUT_EPUB):
        print(f"❌ Error: File '{INPUT_EPUB}' not found.")
        sys.exit(1)

    base_name = os.path.splitext(INPUT_EPUB)[0]
    work_dir = "epub_quick_work"
    progress_file = os.path.join(work_dir, TEMP_FILE)
    output_epub = f"{base_name}-translated.epub"

    extract_epub_if_needed(INPUT_EPUB, work_dir)
    progress_data = load_progress(progress_file)

    target_files = []
    for root, dirs, files in os.walk(work_dir):
        for file in files:
            if file.lower().endswith(('.xhtml', '.html', '.ncx', '.htm')):
                target_files.append(os.path.join(root, file))

    total_count = len(target_files)
    print(f"🤖 Primary model:  {PRIMARY_MODEL}")
    print(f"🛟 Fallback model: {FALLBACK_MODEL} (used automatically on refusal/censorship)")
    print(f"🚀 Processing {total_count} files in parallel ({MAX_WORKERS} threads)...\n")

    total_start = time.time()

    try:
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            futures = [
                executor.submit(translate_single_file, fp, work_dir, progress_file, progress_data)
                for fp in target_files
            ]
            for f in futures:
                f.result()  # Propagate exceptions if needed

    except KeyboardInterrupt:
        print("\n\n🛑 Process stopped by user (Ctrl+C).")
        print("💾 All completed chapters are safely saved in progress.")
        print("💡 Run the script again whenever you want to resume.\n")
        sys.exit(0)

    total_time = time.time() - total_start

    # --- Hard safety gate: never package unless every file is verified COMPLETED ---
    incomplete = verify_all_completed(work_dir, progress_file, target_files)

    if failed_files or incomplete:
        if failed_files:
            print(f"\n⚠️ Finished with {len(failed_files)} failed file(s): {', '.join(failed_files)}")
        if incomplete:
            print(f"⚠️ {len(incomplete)} file(s) not marked COMPLETED in progress file: {', '.join(incomplete)}")
        print("🚫 Skipping epub packaging — fix/re-run for the remaining files first.")
        print("💡 Re-run the script to retry the remaining files (already-done files are skipped).")
    else:
        print(f"\n3. Packaging into '{output_epub}'...")
        create_epub(work_dir, output_epub)
        shutil.rmtree(work_dir)
        print(f"\n🎉 DONE! All {total_count} files completed in {total_time:.1f}s.")
        print(f"📁 Output File: {output_epub}")


if __name__ == "__main__":
    main()
