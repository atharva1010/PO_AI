from flask import Flask, request, render_template, jsonify
import pandas as pd
from rapidfuzz import fuzz
import re
import openai
import os

app = Flask(__name__)

# === OpenAI API Key ===
openai.api_key = os.getenv("OPENAI_API_KEY") or "sk-your-key-here"

# === Load CSV (PO Data) ===
df = pd.read_csv("data/po_data.csv")
df.columns = [col.strip().upper() for col in df.columns]
df["AREA"] = df["AREA"].fillna("OTHER")

# --- Utility functions ---
def clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", str(text).upper().strip())

def search_po(user_query: str):
    """PO search in CSV"""
    query_clean = clean_text(user_query)
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

def openai_answer(query: str) -> str:
    """Fallback to OpenAI"""
    try:
        response = openai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a helpful assistant that answers general questions."},
                {"role": "user", "content": query},
            ],
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print("OpenAI error:", e)
        return "⚠️ OpenAI API error."

# --- Routes ---
@app.route("/", methods=["GET", "POST"])
def home():
    results = []
    answer = None
    query = ""

    if request.method == "POST":
        query = request.form.get("query", "").strip()
        if query:
            results = search_po(query)
            if not results:  # Agar PO nahi mila to OpenAI se poochho
                answer = openai_answer(query)

    return render_template("index.html", query=query, results=results, answer=answer)

@app.route("/ask", methods=["POST"])
def ask():
    user_query = request.form.get("query", "").strip()
    if not user_query:
        return jsonify({"answer": "⚠️ Query empty!"})

    results = search_po(user_query)
    if results:
        return jsonify({"answer": results})
    else:
        return jsonify({"answer": openai_answer(user_query)})

if __name__ == "__main__":
    app.run(debug=True)
