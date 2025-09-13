from flask import Flask, request, render_template, jsonify
import pandas as pd
from rapidfuzz import fuzz
import re
import openai
import os

app = Flask(__name__)

# === OpenAI API Key (ENV ya hardcoded) ===
openai.api_key = os.getenv("OPENAI_API_KEY") or "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"

# === Load CSV ===
df = pd.read_csv("data/po_data.csv")

# Ensure column names are uppercase
df.columns = [col.strip().upper() for col in df.columns]

# AREA blanks ko fill karo
df['AREA'] = df['AREA'].fillna('OTHER')

# --- Utility functions ---
def clean_text(text: str) -> str:
    """Uppercase, strip, remove extra spaces"""
    return re.sub(r'\s+', ' ', str(text).upper().strip())

def openai_correct_query(user_query: str) -> str:
    """Use OpenAI to correct spelling or normalize"""
    try:
        response = openai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are an expert in matching wood purchase order data."},
                {"role": "user", "content": f"Correct this query for PO search: {user_query}"}
            ]
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print("OpenAI error:", e)
        return user_query

def search_po(user_query: str):
    """Fuzzy strict search: all query words must match row"""
    corrected_query = openai_correct_query(user_query)
    query_clean = clean_text(corrected_query)
    query_words = query_clean.split()

    matches = []

    for _, row in df.iterrows():
        row_text = f"{row['PARTY']} {row['AREA']} {row['MATERIAL']}"
        row_text_clean = clean_text(row_text)
        row_words = row_text_clean.split()

        # Each query word must match at least one token in row (>=75 similarity)
        ok = True
        for q in query_words:
            if not any(fuzz.partial_ratio(q, r) >= 75 for r in row_words):
                ok = False
                break

        if ok:
            matches.append({
                "PO": row['PO'],
                "Party": row['PARTY'],
                "Area": row['AREA'],
                "Material": row['MATERIAL']
            })

    return matches

# --- Routes ---
@app.route("/")
def home():
    return render_template("index.html")

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
