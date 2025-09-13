from flask import Flask, request, render_template, jsonify
import pandas as pd
from rapidfuzz import fuzz
import re
import openai
import os

app = Flask(__name__)

# === OpenAI API Key (ENV ya hardcoded) ===
openai.api_key = os.getenv("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") or ""

# === Load CSV ===
df = pd.read_csv("data/po_data.csv")

# Ensure column names are uppercase
df.columns = [col.strip().upper() for col in df.columns]

# Fill AREA blanks
df["AREA"] = df["AREA"].fillna("OTHER")


# --- Utility functions ---
def clean_text(text: str) -> str:
    """Uppercase, strip, remove extra spaces"""
    return re.sub(r"\s+", " ", str(text).upper().strip())


def openai_correct_query(user_query: str) -> str:
    """Use OpenAI to correct spelling or normalize"""
    if not openai.api_key:
        return user_query  # fallback if no key

    try:
        response = openai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are an expert in correcting noisy PO queries for wood purchase orders."},
                {"role": "user", "content": f"Correct and clean this query for PO search: {user_query}"},
            ],
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print("OpenAI error:", e)
        return user_query


def search_po(user_query: str):
    """Fuzzy search with stricter AREA match"""
    corrected_query = openai_correct_query(user_query)
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
            # Strict AREA check
            if fuzz.partial_ratio(q, row_area) >= 90:
                continue
            # PARTY/MATERIAL fuzzy check
            elif any(fuzz.partial_ratio(q, r) >= 75 for r in row_words):
                continue
            else:
                ok = False
                break

        if ok:
            matches.append(
                {
                    "PO": row["PO"],
                    "Party": row["PARTY"],
                    "Area": row["AREA"],
                    "Material": row["MATERIAL"],
                }
            )

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
