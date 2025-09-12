from flask import Flask, request, render_template, jsonify
import pandas as pd
from rapidfuzz import fuzz
import re
import openai
import os

app = Flask(__name__)

# === OpenAI API Key ===
# Security tip: better is to use environment variable
openai.api_key = os.getenv("OPENAI_API_KEY") or "YOUR_OPENAI_API_KEY_HERE"

# === Load CSV ===
df = pd.read_csv("data/po_data.csv")

# Ensure column names are uppercase and consistent
df.columns = [col.upper() for col in df.columns]

# Fill AREA blanks if any
df['AREA'] = df['AREA'].fillna('OTHER')

def clean_text(text):
    """Lowercase, strip, remove extra spaces"""
    return re.sub(r'\s+', ' ', str(text).upper().strip())

def fuzzy_match_score(query_words, row_words):
    """Return average best match score for query vs row"""
    scores = []
    for q in query_words:
        max_score = max([fuzz.partial_ratio(q, r) for r in row_words])
        scores.append(max_score)
    return sum(scores)/len(scores) if scores else 0

def openai_correct_query(user_query):
    """Optional: Use OpenAI to correct spelling or translate"""
    try:
        response = openai.ChatCompletion.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are an expert in wood POs and CSV data matching."},
                {"role": "user", "content": f"Correct and normalize this query for PO search: {user_query}"}
            ]
        )
        corrected = response.choices[0].message.content
        return corrected
    except Exception as e:
        print("OpenAI error:", e)
        return user_query

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/ask", methods=["POST"])
def ask():
    user_query = request.form.get("query", "")
    if not user_query:
        return jsonify({"answer": "Query empty!"})

    # 1. Optional: Correct spelling / normalize via OpenAI
    corrected_query = openai_correct_query(user_query)
    query_clean = clean_text(corrected_query)
    query_words = query_clean.split()

    matches = []

    for _, row in df.iterrows():
        row_text = f"{row['PARTY']} {row['AREA']} {row['MATERIAL']}"
        row_text_clean = clean_text(row_text)
        row_words = row_text_clean.split()

        # Check if all query words exist in row (fuzzy match >=70)
        word_scores = [max([fuzz.partial_ratio(q, r) for r in row_words]) for q in query_words]
        if all(score >= 70 for score in word_scores):
            matches.append({
                "PO": f"<b>{row['PO']}</b>",
                "Party": row['PARTY'],
                "Area": row['AREA'],
                "Material": row['MATERIAL']
            })

    if matches:
        return jsonify({"answer": matches})
    else:
        return jsonify({"answer": "❌ Koi exact PO nahi mila."})

if __name__ == "__main__":
    app.run(debug=True)
