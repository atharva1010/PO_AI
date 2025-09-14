import os
import json
import time
import sqlite3
import re
from typing import List, Optional, Tuple

from flask import Flask, request, render_template, jsonify
import pandas as pd
import numpy as np
from openai import OpenAI
from rapidfuzz import fuzz

# ---------- CONFIG ----------
OPENAI_KEY = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=OPENAI_KEY)

EMBED_MODEL = "text-embedding-3-small"
CHAT_MODEL = "gpt-4o-mini"

DB_PATH = os.path.join(os.path.dirname(__file__), "study_data.db")  # auto-create in root
PO_CSV = os.path.join(os.path.dirname(__file__), "data/po_data.csv")

# thresholds
EMBED_SIM_THRESHOLD = 0.78
PO_AREA_STRICT = 90
PO_WORD_FUZZY = 75

app = Flask(__name__, template_folder="templates")

# ---------- LOAD PO CSV ----------
if os.path.exists(PO_CSV):
    po_df = pd.read_csv(PO_CSV, dtype=str).fillna("")
    po_df.columns = [c.strip().upper() for c in po_df.columns]
else:
    po_df = pd.DataFrame(columns=["PO", "PARTY", "AREA", "MATERIAL"])
if "AREA" not in po_df.columns:
    po_df["AREA"] = "OTHER"

# ---------- SQLITE helpers ----------
def init_db():
    """Create study_data.db automatically if not exists"""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS study (
      id INTEGER PRIMARY KEY,
      title TEXT,
      content TEXT,
      embedding TEXT,
      created_at REAL
    )
    """)
    conn.commit()
    conn.close()

def add_study_item(title: str, content: str, embedding: Optional[List[float]] = None):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    emb_json = json.dumps(embedding) if embedding is not None else None
    cur.execute("INSERT INTO study (title, content, embedding, created_at) VALUES (?, ?, ?, ?)",
                (title, content, emb_json, time.time()))
    conn.commit()
    conn.close()

def list_study_items(limit: int = 50):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT id, title, content, embedding, created_at FROM study ORDER BY created_at DESC LIMIT ?", (limit,))
    rows = cur.fetchall()
    conn.close()
    items = []
    for r in rows:
        emb = json.loads(r[3]) if r[3] else None
        items.append({"id": r[0], "title": r[1], "content": r[2], "embedding": emb, "created_at": r[4]})
    return items

# ---------- embeddings & similarity ----------
def get_embedding(text: str) -> List[float]:
    if not OPENAI_KEY:
        raise RuntimeError("OpenAI key not configured")
    resp = client.embeddings.create(model=EMBED_MODEL, input=text)
    return resp.data[0].embedding

def cosine_sim(a: np.ndarray, b: np.ndarray) -> float:
    if np.linalg.norm(a) == 0 or np.linalg.norm(b) == 0:
        return 0.0
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))

def find_best_study_matches(query: str, top_k: int = 3) -> List[Tuple[float, dict]]:
    items = list_study_items(5000)
    results = []
    try:
        q_emb = np.array(get_embedding(query), dtype=float)
    except Exception:
        for it in items:
            s = max(
                fuzz.partial_ratio(query.lower(), (it["title"] or "").lower())/100,
                fuzz.partial_ratio(query.lower(), (it["content"] or "").lower())/100
            )
            results.append((s, it))
        results.sort(key=lambda x: x[0], reverse=True)
        return results[:top_k]

    for it in items:
        if it["embedding"]:
            it_emb = np.array(it["embedding"], dtype=float)
            score = cosine_sim(q_emb, it_emb)
        else:
            score = max(
                fuzz.partial_ratio(query.lower(), (it["title"] or "").lower())/100,
                fuzz.partial_ratio(query.lower(), (it["content"] or "").lower())/100
            )
        results.append((score, it))
    results.sort(key=lambda x: x[0], reverse=True)
    return results[:top_k]

# ---------- PO search ----------
def clean_upper(s: str) -> str:
    return re.sub(r"\s+", " ", str(s or "").upper().strip())

def search_po_csv(user_query: str):
    q = clean_upper(user_query)
    q_words = q.split()
    matches = []
    for _, row in po_df.iterrows():
        row_area = clean_upper(row.get("AREA", ""))
        row_text = f"{row.get('PARTY','')} {row.get('MATERIAL','')}"
        row_text_clean = clean_upper(row_text)
        row_words = row_text_clean.split()
        ok = True
        for qw in q_words:
            if fuzz.partial_ratio(qw, row_area) >= PO_AREA_STRICT:
                continue
            if any(fuzz.partial_ratio(qw, rw) >= PO_WORD_FUZZY for rw in row_words):
                continue
            ok = False
            break
        if ok:
            matches.append({
                "PO": str(row.get("PO", "")).strip(),
                "Party": row.get("PARTY", ""),
                "Area": row.get("AREA", ""),
                "Material": row.get("MATERIAL", "")
            })
    return matches

# ---------- OpenAI chat fallback ----------
def openai_chat_answer(user_query: str, context_texts: Optional[List[str]] = None) -> str:
    if not OPENAI_KEY:
        return "OpenAI not configured. Please enable study data or set OPENAI_API_KEY."
    sys_prompt = "You are Tesa AI, a helpful, friendly tutor. Use study memory context first if provided. Answer concisely and clearly."
    if context_texts:
        user_prompt = "Context:\n" + "\n".join(context_texts) + "\n\nQuestion: " + user_query
    else:
        user_prompt = user_query
    try:
        resp = client.chat.completions.create(
            model=CHAT_MODEL,
            messages=[
                {"role": "system", "content": sys_prompt},
                {"role": "user", "content": user_prompt}
            ],
            max_tokens=450,
            temperature=0.2
        )
        return resp.choices[0].message.content.strip()
    except Exception as e:
        return f"AI error: {e}"

# ---------- INIT DB ----------
init_db()

# ---------- ROUTES ----------
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/study/add", methods=["POST"])
def study_add():
    data = request.json or {}
    title = (data.get("title") or "").strip()
    content = (data.get("content") or "").strip()
    if not content:
        return jsonify({"ok": False, "error": "content required"}), 400
    emb = None
    try:
        emb = get_embedding(content)
    except Exception as e:
        print("embedding error:", e)
    add_study_item(title or content[:80], content, emb)
    return jsonify({"ok": True})

@app.route("/study/list", methods=["GET"])
def study_list():
    items = list_study_items(50)
    for it in items:
        it.pop("embedding", None)
    return jsonify(items)

@app.route("/chat", methods=["POST"])
def chat():
    data = request.get_json() or {}
    user_msg = (data.get("message") or "").strip()
    mode = data.get("mode") or "po"
    if not user_msg:
        return jsonify({"error": "empty message"}), 400

    # ----- PO SEARCH -----
    if mode == "po":
        po_matches = search_po_csv(user_msg)
        if po_matches:
            return jsonify({"type": "po", "results": po_matches})
        mode = "study"

    # ----- STUDY SEARCH -----
    top_matches = find_best_study_matches(user_msg, top_k=3)

    if top_matches and top_matches[0][0] >= EMBED_SIM_THRESHOLD:
        score, item = top_matches[0]
        return jsonify({
            "type": "study",
            "source": "memory",
            "score": round(score, 3),
            "answer": item["content"]
        })

    # weak match → give context to AI
    context_texts = []
    for score, item in top_matches:
        if score >= 0.35:
            context_texts.append(f"{item['title']}: {item['content']}")

    answer = openai_chat_answer(user_msg, context_texts if context_texts else None)
    return jsonify({"type": "ai", "source": "openai", "answer": answer})

@app.route("/health")
def health():
    return jsonify({"ok": True})

# ---------- run ----------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
