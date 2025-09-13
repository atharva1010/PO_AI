from flask import Flask, request, render_template, jsonify
import pandas as pd
from rapidfuzz import fuzz
import re
import openai
import os

app = Flask(__name__)

# === OpenAI API Key ===
openai.api_key = os.getenv("OPENAI_API_KEY") or "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"  # apna key lagao

# === Load CSV ===
df = pd.read_csv("data/po_data.csv")
df.columns = [col.strip().upper() for col in df.columns]
df["AREA"] = df["AREA"].fillna("OTHER")

# === Alias mapping for common misheard words ===
ALIASES = {
    "SHIVA WINNER": "SHIVA VEENER",
    "VINAYAK PLY IND": "VINAYAK PLY IND P. LTD-UPS",
}

# --- Utility functions ---
def clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", str(text).upper().strip())

def openai_correct_query(user_query: str) -> str:
    """Correct spelling / normalize query using OpenAI"""
    try:
        response = openai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are an expert in wood purchase order CSV data."},
                {"role": "user", "content": f"Correct and normalize this query: {user_query}"},
            ],
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print("OpenAI error:", e)
        return user_query

def apply_aliases(query: str) -> str:
    for alias, real in ALIASES.items():
        query = query.replace(alias, real)
    return query

def search_po(user_query: str):
    corrected_query = openai_correct_query(user_query)
    corrected_query = apply_aliases(corrected_query)
    query_clean = clean_text(corrected_query)
    query_words = query_clean.split()

    matches = []
    for _, row in df.iterrows():
        row_area = clean_text(row["AREA"])
        row_text = f"{row['PARTY']} {row['MATERIAL']}"
        row_text_clean = clean_text(row_text)
        row_words = row_text_clean.split()

        ok = True
        for q in query_words:
            if fuzz.partial_ratio(q, row_area) >= 90:
                continue
            elif any(fuzz.partial_ratio(q, r) >= 75 for r in row_words):
                continue
            else:
                ok = False
                break
        if ok:
            matches.append({
                "PO": row["PO"],
                "Party": row["PARTY"],
                "Area": row["AREA"],
                "Material": row["MATERIAL"]
            })
    return matches

# --- Routes ---
@app.route("/", methods=["GET", "POST"])
def home():
    results = []
    query = ""
    if request.method == "POST":
        query = request.form.get("query", "").strip()
        if query:
            results = search_po(query)
    return render_template("index.html", query=query, results=results)

@app.route("/ask", methods=["POST"])
def ask():
    user_query = request.form.get("query", "").strip()
    if not user_query:
        return jsonify({"answer": "⚠️ Query empty!"})
    results = search_po(user_query)
    if not results:
        return jsonify({"answer": "❌ Koi exact PO nahi mila."})
    return jsonify({"answer": results})

if __name__ == "__main__":
    app.run(debug=True)
