import os
import re
import sys
import uuid
import heapq
import tempfile
from collections import Counter
from flask import Blueprint, request, jsonify
from PIL import Image
import pytesseract
from PyPDF2 import PdfReader
from werkzeug.utils import secure_filename

# --- Windows-only: point pytesseract/pdf2image at their binaries directly ---
# This avoids needing to edit the system PATH. Harmless no-op on Mac/Linux,
# and skipped automatically if a PATH-based tesseract is already found.
# Adjust these two paths if you installed Tesseract/Poppler somewhere else.
if sys.platform == "win32":
    _tesseract_exe = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
    if os.path.exists(_tesseract_exe):
        pytesseract.pytesseract.tesseract_cmd = _tesseract_exe

    _poppler_bin = r"C:\poppler\Library\bin"
    if os.path.exists(_poppler_bin) and _poppler_bin not in os.environ.get("PATH", ""):
        os.environ["PATH"] += os.pathsep + _poppler_bin

extraction_bp = Blueprint("extraction", __name__)

ALLOWED_EXTENSIONS = {"pdf", "png", "jpg", "jpeg"}
MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024  # 10MB, matches the UI copy

# A page is considered "text-empty" (and therefore a candidate for OCR)
# if it has fewer than this many non-whitespace characters.
MIN_CHARS_FOR_NATIVE_TEXT = 20

# Common stopwords / non-name capitalized phrases that the old regex
# used to misfire on (e.g. "United States", "New York", sentence starts).
NAME_STOPWORDS = {
    "the", "and", "for", "with", "this", "that", "from", "into", "your",
    "united states", "new york", "los angeles", "san francisco",
    "monday", "tuesday", "wednesday", "thursday", "friday", "saturday",
    "sunday", "january", "february", "march", "april", "may", "june",
    "july", "august", "september", "october", "november", "december",
}

GENERIC_STOPWORDS = {
    "the", "a", "an", "and", "or", "but", "if", "then", "so", "of", "to",
    "in", "on", "at", "by", "for", "with", "as", "is", "are", "was",
    "were", "be", "been", "being", "it", "its", "this", "that", "these",
    "those", "from", "into", "such", "not", "no", "than", "too", "very",
    "can", "will", "would", "should", "could", "may", "might", "must",
    "shall", "have", "has", "had", "do", "does", "did", "we", "you",
    "they", "he", "she", "i", "our", "their", "his", "her", "them",
}

# Common words that start sentences but are essentially never the first
# word of a person's name - used to cut down on false-positive names like
# "Contact John" or "The United States" from the capitalized-words regex.
NON_NAME_LEAD_WORDS = GENERIC_STOPWORDS | {
    "contact", "please", "additional", "everyone", "meeting", "email",
    "however", "therefore", "overall", "finance", "attached", "enclosed",
    "regarding", "dear", "sincerely", "thank", "thanks", "note", "notice",
    "important", "warning", "summary", "section", "chapter", "figure",
    "table", "appendix", "page", "date", "subject", "re", "cc", "attn",
}


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def extract_text_from_image(image_path):
    """OCR a standalone image file."""
    try:
        return pytesseract.image_to_string(Image.open(image_path))
    except Exception as e:
        print(f"Error extracting text from image: {e}")
        return ""


def _ocr_pdf_page(pdf_path, page_number):
    """
    Rasterize a single PDF page and run OCR on it.
    Requires pdf2image (and the poppler system binary) to be installed.
    Returns "" if unavailable rather than raising, so PDFs with a mix of
    text and scanned pages still return whatever we *can* extract.
    """
    try:
        from pdf2image import convert_from_path
    except ImportError:
        print(
            "pdf2image is not installed - scanned/image-only PDF pages "
            "cannot be OCR'd. Run: pip install pdf2image (and install poppler)."
        )
        return ""

    try:
        images = convert_from_path(
            pdf_path, first_page=page_number, last_page=page_number, dpi=300
        )
        if not images:
            return ""
        return pytesseract.image_to_string(images[0])
    except Exception as e:
        print(f"Error OCR'ing PDF page {page_number}: {e}")
        return ""


def extract_text_from_pdf(pdf_path):
    """
    Extract text from a PDF, page by page. For pages where native text
    extraction yields little or nothing (typical of scanned documents),
    fall back to rasterizing the page and running OCR on it, so the tool
    behaves correctly for both digitally-authored and scanned PDFs.
    """
    text_parts = []
    ocr_pages = 0
    try:
        with open(pdf_path, "rb") as f:
            reader = PdfReader(f)
            for i, page in enumerate(reader.pages, start=1):
                page_text = ""
                try:
                    page_text = page.extract_text() or ""
                except Exception as e:
                    print(f"Error extracting native text from page {i}: {e}")

                if len(page_text.strip()) < MIN_CHARS_FOR_NATIVE_TEXT:
                    ocr_text = _ocr_pdf_page(pdf_path, i)
                    if len(ocr_text.strip()) > len(page_text.strip()):
                        page_text = ocr_text
                        ocr_pages += 1

                text_parts.append(page_text)
    except Exception as e:
        print(f"Error extracting text from PDF: {e}")

    if ocr_pages:
        print(f"OCR fallback used on {ocr_pages} page(s) of {os.path.basename(pdf_path)}")

    return "\n".join(text_parts)


def _dedupe_preserve_order(items):
    seen = set()
    ordered = []
    for item in items:
        key = item.strip()
        if key and key.lower() not in seen:
            seen.add(key.lower())
            ordered.append(key)
    return ordered


def extract_entities(text):
    """
    Pull out names, dates, addresses, emails, and phone numbers.
    Regex-based NER is inherently approximate, so we apply extra
    filtering (stopword lists, overlap checks against dates/addresses)
    to cut down on the false positives the original implementation had.
    """
    # Emails - very low false-positive rate, safe to extract directly.
    emails = re.findall(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", text)

    # Phone numbers - covers common US/intl formats like (555) 123-4567,
    # 555-123-4567, +1 555 123 4567.
    phone_pattern = r"(?:\+?\d{1,2}[\s.-]?)?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}\b"
    phones = re.findall(phone_pattern, text)

    date_patterns = [
        r"\b\d{1,2}/\d{1,2}/\d{2,4}\b",
        r"\b\d{4}-\d{2}-\d{2}\b",
        r"\b(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|"
        r"Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|"
        r"Dec(?:ember)?)\s+\d{1,2}(?:st|nd|rd|th)?,?\s+\d{4}\b",
    ]
    dates = []
    for pattern in date_patterns:
        dates.extend(re.findall(pattern, text))

    # NOTE: address/name matching intentionally uses "[ \t]" rather than the
    # generic "\s" for inter-word gaps. "\s" also matches newlines, which
    # caused entities to wrongly merge across separate lines of extracted
    # PDF text (e.g. "John Doe\nDate" being read as one name).
    address_pattern = (
        r"\d+[ \t]+[A-Za-z0-9][A-Za-z0-9 \t]*?[ \t]+(?:Street|St|Avenue|Ave|Road|Rd|Boulevard|Blvd|"
        r"Lane|Ln|Drive|Dr|Court|Ct|Place|Pl|Square|Sq|Terrace|Ter|Way|Parkway|"
        r"Pkwy|Circle|Cir|Highway|Hwy|Route|Rt)\.?\b(?:,[ \t]*[A-Za-z \t]+)?"
        r"(?:,[ \t]*[A-Z]{2})?[ \t]*\d{5}(?:-\d{4})?"
    )
    addresses = re.findall(address_pattern, text)

    # Names: two-or-more capitalized words in a row, e.g. "John Doe".
    # Filter out matches that are really dates/addresses/known phrases,
    # and single-letter "words" that are usually OCR noise or initials
    # picked up mid-sentence.
    raw_name_candidates = re.findall(r"\b[A-Z][a-z]+(?:[ \t]+[A-Z][a-z]+){1,3}\b", text)
    address_and_date_text = " ".join(addresses + dates)
    names = []
    for candidate in raw_name_candidates:
        lowered = candidate.lower()
        if lowered in NAME_STOPWORDS:
            continue
        if candidate in address_and_date_text:
            continue
        words = candidate.split()
        # Skip if every word is a common stopword-ish fragment (unlikely name)
        if all(w.lower() in NAME_STOPWORDS for w in words):
            continue
        # Skip if it looks like a sentence fragment rather than a name
        # (leading word is a common non-name word, e.g. "Contact John").
        if words[0].lower() in NON_NAME_LEAD_WORDS:
            continue
        names.append(candidate)

    return {
        "names": _dedupe_preserve_order(names),
        "dates": _dedupe_preserve_order(dates),
        "addresses": _dedupe_preserve_order(addresses),
        "emails": _dedupe_preserve_order(emails),
        "phones": _dedupe_preserve_order(phones),
    }


def _extract_markdown_tables(text):
    """Fallback table extraction for markdown-style '|' tables (e.g. from OCR output)."""
    tables = []
    lines = text.split("\n")
    i = 0
    while i < len(lines) - 1:
        line, next_line = lines[i], lines[i + 1]
        if "|" in line and re.match(r"^[\s|:-]+$", next_line) and "-" in next_line:
            headers = [h.strip() for h in line.split("|") if h.strip()]
            rows = []
            j = i + 2
            while j < len(lines) and "|" in lines[j]:
                row_data = [d.strip() for d in lines[j].split("|") if d.strip()]
                if len(row_data) == len(headers):
                    rows.append(row_data)
                    j += 1
                else:
                    break
            if headers and rows:
                tables.append({"headers": headers, "rows": rows})
            i = j
        else:
            i += 1
    return tables


def extract_tables_from_pdf(pdf_path, fallback_text):
    """
    Prefer real layout-aware table extraction via pdfplumber, which works on
    the actual PDF geometry (rows/columns/borders) rather than guessing from
    plain text - this is the fix for real-world PDFs, which almost never
    contain markdown-style '|' tables. Falls back to the markdown-table
    heuristic (useful for OCR'd text) if pdfplumber isn't installed or finds
    nothing.
    """
    try:
        import pdfplumber
    except ImportError:
        print(
            "pdfplumber is not installed - falling back to markdown-style "
            "table detection. Run: pip install pdfplumber for accurate "
            "table extraction from real PDF layouts."
        )
        return _extract_markdown_tables(fallback_text)

    tables = []
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                for raw_table in page.extract_tables():
                    if not raw_table or len(raw_table) < 2:
                        continue
                    headers = [(c or "").strip() for c in raw_table[0]]
                    rows = [
                        [(c or "").strip() for c in row]
                        for row in raw_table[1:]
                        if any((c or "").strip() for c in row)
                    ]
                    if any(headers) and rows:
                        tables.append({"headers": headers, "rows": rows})
    except Exception as e:
        print(f"Error extracting tables with pdfplumber: {e}")

    return tables if tables else _extract_markdown_tables(fallback_text)


def summarize_text(text, max_points=5):
    """
    Lightweight extractive summarizer (word-frequency scoring, no external
    ML dependencies required). Splits the text into sentences, scores each
    one by the normalized frequency of its content words, and returns the
    top-scoring sentences as a list of clean, standalone key points -
    ordered as they appeared in the original document (not by score), so
    the summary still reads coherently.
    """
    text = text.strip()
    if not text:
        return []

    sentences = re.split(r"(?<=[.!?])\s+(?=[A-Z0-9])", text)
    # Collapse internal whitespace/newlines (PDF text often has line breaks
    # mid-sentence) so each point reads as one clean line.
    sentences = [re.sub(r"\s+", " ", s).strip() for s in sentences]
    sentences = [s for s in sentences if len(s) > 1]

    if len(sentences) <= max_points:
        return sentences

    words = re.findall(r"[A-Za-z']+", text.lower())
    words = [w for w in words if w not in GENERIC_STOPWORDS and len(w) > 2]
    if not words:
        return sentences[:max_points]

    freq = Counter(words)
    max_freq = max(freq.values())
    for w in freq:
        freq[w] /= max_freq

    scores = []
    for idx, sentence in enumerate(sentences):
        sentence_words = re.findall(r"[A-Za-z']+", sentence.lower())
        if not sentence_words:
            continue
        score = sum(freq.get(w, 0) for w in sentence_words) / len(sentence_words)
        # Small boost for early sentences - titles/intros tend to be summary-worthy.
        if idx < 3:
            score *= 1.15
        scores.append((score, idx, sentence))

    top = heapq.nlargest(max_points, scores, key=lambda x: x[0])
    key_points = [s for _, _, s in sorted(top, key=lambda x: x[1])]
    return key_points


@extraction_bp.route("/extract", methods=["POST"])
def extract_data():
    if "file" not in request.files:
        return jsonify({"error": "No file part"}), 400

    file = request.files["file"]
    if file.filename == "":
        return jsonify({"error": "No selected file"}), 400

    if not allowed_file(file.filename):
        return jsonify({"error": "Unsupported file type"}), 400

    # Enforce the 10MB limit the UI advertises (Flask's MAX_CONTENT_LENGTH,
    # set in main.py, also guards this - this is a friendlier explicit check).
    file.seek(0, os.SEEK_END)
    size = file.tell()
    file.seek(0)
    if size > MAX_FILE_SIZE_BYTES:
        return jsonify({"error": "File exceeds the 10MB limit"}), 400

    # Extension is read from the ORIGINAL filename (already validated by
    # allowed_file above), not the sanitized one: secure_filename() can
    # strip unicode/symbol-only basenames down to something with no dot at
    # all (e.g. "???.pdf" -> "pdf"), which would otherwise crash the
    # rsplit(".", 1)[1] below with an IndexError.
    file_extension = file.filename.rsplit(".", 1)[1].lower()
    safe_name = secure_filename(file.filename) or f"upload.{file_extension}"
    if "." not in safe_name:
        safe_name = f"{safe_name}.{file_extension}"
    temp_path = os.path.join(tempfile.gettempdir(), f"{uuid.uuid4().hex}_{safe_name}")
    file.save(temp_path)

    try:
        if file_extension in ("png", "jpg", "jpeg"):
            raw_text = extract_text_from_image(temp_path)
            tables = _extract_markdown_tables(raw_text)
        else:  # pdf
            raw_text = extract_text_from_pdf(temp_path)
            tables = extract_tables_from_pdf(temp_path, raw_text)

        entities = extract_entities(raw_text)
        key_points = summarize_text(raw_text)

        return jsonify({
            "raw_text": raw_text,
            "key_points": key_points,
            "entities": entities,
            "tables": tables,
            "word_count": len(raw_text.split()),
        })
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)
