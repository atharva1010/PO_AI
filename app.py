# app.py
import os
import json
import sqlite3
import time
import re
from typing import List, Tuple, Optional

from flask import Flask, request, render_template, jsonify
import pandas as pd
import numpy as np
import openai
from rapidfuzz import fuzz

# ---------- CONFIG ----------
OPENAI_KEY = os.getenv("OPENAI_API_KEY")  # set this in environment
openai.api_key = OPENAI_KEY

EMBED_MODEL = "text-embedding-3-small"   # embedding model
CHAT_MODEL = "gpt-4o-mini"               # chat model for human-like answers
DB_PATH = "study_data.db"
PO_CSV = "data/po_data.csv"              # your PO CSV path

# thresholds
EMBED_SIM_THRESHOLD = 0.78   # if similarity >= this, use stored answer
PO_AREA_STRICT = 90
PO_WORD_FUZZY = 75

# ---------- FLASK ----------
app = Flask(__name__, template_folder="templates")

# ---------- LOAD PO CSV ----------
if os.path.exists(PO_CSV):
    po_df = pd.read_csv(PO_CSV, dtype=str).fillna("")
    # Normalize column names (client expects: PO, PARTY, AREA, MATERIAL)
    po_df.columns = [c.strip().upper() for c in po_df.columns]
else:
    po_df = pd.DataFrame(columns=["PO", "PARTY", "AREA", "MATERIAL"])

# Ensure AREA exists
if "AREA" not in po_df.columns:
    po_df["AREA"] = "OTHER"

# ---------- SQLITE HELPERS ----------
def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
    CREATE TABLE IF NOT EXISTS study (
        id INTEGER PRIMARY KEY,
        title TEXT,
        content TEXT,
        embedding TEXT,   -- JSON list of floats
        created_at REAL
    )
    """)
    conn.commit()
    conn.close()

def add_study_item(title: str, content: str, embedding: Optional[List[float]] = None):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    emb_json = json.dumps(embedding) if embedding is not None else None
    c.execute(
        "INSERT INTO study (title, content, embedding, created_at) VALUES (?, ?, ?, ?)",
        (title, content, emb_json, time.time())
    )
    conn.commit()
    conn.close()

def get_all_study_items():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id, title, content, embedding FROM study")
    rows = c.fetchall()
    conn.close()
    items = []
    for r in rows:
        emb = json.loads(r[3]) if r[3] else None
        items.append({"id": r[0], "title": r[1], "content": r[2], "embedding": emb})
    return items

# ---------- EMBEDDING & SIMILARITY ----------
def get_embedding(text: str) -> List[float]:
    """Create embedding using OpenAI. Raises if key missing or error."""
    if not OPENAI_KEY:
        raise RuntimeError("OpenAI key missing")
    resp = openai.Embedding.create(model=EMBED_MODEL, input=text)
    return resp["data"][0]["embedding"]

def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    if np.linalg.norm(a) == 0 or np.linalg.norm(b) == 0:
        return 0.0
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))

def find_best_study_matches(query: str, top_k: int = 3) -> List[Tuple[float, dict]]:
    """Return list of (score, item) sorted desc."""
    items = get_all_study_items()
    results = []
    try:
        q_emb = np.array(get_embedding(query), dtype=float)
    except Exception:
        # embedding failing — fallback to text fuzzy (use content/title)
        for it in items:
            score = max(
                fuzz.partial_ratio(query.lower(), (it["title"] or "").lower())/100,
                fuzz.partial_ratio(query.lower(), (it["content"] or "").lower())/100
            )
            results.append((score, it))
        results.sort(key=lambda x: x[0], reverse=True)
        return results[:top_k]

    for it in items:
        if it["embedding"]:
            it_emb = np.array(it["embedding"], dtype=float)
            score = cosine_similarity(q_emb, it_emb)
            results.append((score, it))
        else:
            # fallback text fuzzy
            score = max(
                fuzz.partial_ratio(query.lower(), (it["title"] or "").lower())/100,
                fuzz.partial_ratio(query.lower(), (it["content"] or "").lower())/100
            )
            results.append((score, it))
    results.sort(key=lambda x: x[0], reverse=True)
    return results[:top_k]

# ---------- PO SEARCH ----------
def clean_text_upper(s: str) -> str:
    return re.sub(r"\s+", " ", str(s or "").upper().strip())

def search_po_csv(user_query: str):
    q = clean_text_upper(user_query)
    q_words = q.split()
    matches = []
    # iterate rows
    for _, row in po_df.iterrows():
        row_area = clean_text_upper(row.get("AREA", ""))
        row_text = f"{row.get('PARTY','')} {row.get('MATERIAL','')}"
        row_text_clean = clean_text_upper(row_text)
        row_words = row_text_clean.split()
        ok = True
        for qw in q_words:
            # strict area match if area-like word
            if fuzz.partial_ratio(qw, row_area) >= PO_AREA_STRICT:
                continue
            if any(fuzz.partial_ratio(qw, rw) >= PO_WORD_FUZZY for rw in row_words):
                continue
            ok = False
            break
        if ok:
            matches.append({
                "PO": str(row.get("PO","")).strip(),
                "Party": row.get("PARTY",""),
                "Area": row.get("AREA",""),
                "Material": row.get("MATERIAL","")
            })
    return matches

# ---------- OPENAI CHAT fallback ----------
def openai_chat_answer(system_prompt: str, user_prompt: str) -> str:
    if not OPENAI_KEY:
        return "I cannot reach the AI right now (no API key)."
    try:
        resp = openai.ChatCompletion.create(
            model=CHAT_MODEL,
            messages=[
                {"role":"system", "content": system_prompt},
                {"role":"user", "content": user_prompt}
            ],
            max_tokens=400,
            temperature=0.2
        )
        return resp.choices[0].message.content.strip()
    except Exception as e:
        return f"AI error: {e}"

# ---------- INIT ----------
init_db()

# ---------- ROUTES ----------

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/study/add", methods=["POST"])
def study_add():
    """Add new study item (title & content). UI will call this to teach the bot."""
    data = request.json or {}
    title = data.get("title", "").strip()
    content = data.get("content", "").strip()
    if not content:
        return jsonify({"ok": False, "error": "Content required"}), 400
    emb = None
    try:
        emb = get_embedding(content)
    except Exception as e:
        # embedding may fail if no key/quota — still store text
        print("embedding error:", e)
    add_study_item(title or content[:80], content, emb)
    return jsonify({"ok": True})

@app.route("/chat", methods=["POST"])
def chat():
    """
    Main chat endpoint used by the frontend.
    Accepts JSON: { message: "...", mode: "po" | "study" }
    """
    data = request.get_json() or {}
    user_msg = (data.get("message") or "").strip()
    mode = data.get("mode") or "po"   # default PO mode
    if not user_msg:
        return jsonify({"error": "Empty message"}), 400

    # 1) If mode == po: first attempt PO search
    if mode == "po":
        po_matches = search_po_csv(user_msg)
        if po_matches:
            # return only PO list (UI will speak last 4 digits)
            return jsonify({"type":"po", "results": po_matches})

        # if no PO: fall through to try study/AI
        mode = "study"

    # 2) Study mode: check study DB for similarity
    top_matches = find_best_study_matches(user_msg, top_k=3)
    if top_matches and top_matches[0][0] >= EMBED_SIM_THRESHOLD:
        # high confidence -> return stored answer (content)
        score, item = top_matches[0]
        return jsonify({"type":"study", "source":"stored", "score":score, "answer": item["content"]})

    # 3) If low confidence or no items, ask OpenAI (with optional context of top matches)
    context_texts = []
    for score, item in top_matches:
        if score >= 0.35:
            context_texts.append(f"KNOWN: {item['title']} — {item['content']}")
    system_prompt = "You are a helpful, friendly tutor. Answer concisely and clearly using the available context first. If context does not cover the question, answer normally."
    user_prompt = ("Context:\n" + "\n".join(context_texts) + "\n\nQuestion: " + user_msg) if context_texts else user_msg
    answer = openai_chat_answer(system_prompt, user_prompt)
    return jsonify({"type":"ai", "source":"openai", "answer": answer})

# small utility endpoint to list study items (for admin)
@app.route("/study/list", methods=["GET"])
def study_list():
    return jsonify(get_all_study_items())

# health
@app.route("/health", methods=["GET"])
def health():
    return jsonify({"ok": True})

# ---------- MAIN ----------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
