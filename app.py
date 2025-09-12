from flask import Flask, request, render_template, jsonify
import pandas as pd
from rapidfuzz import fuzz
import re

app = Flask(__name__)

# Load CSV
df = pd.read_csv("data/po_data.csv")

# Convert all string columns to lowercase for matching
df = df.apply(lambda col: col.str.lower() if col.dtype == 'object' else col)

# Function to clean query (remove extra spaces, lowercase, keep alphanumeric)
def clean_text(text):
    text = text.lower()
    text = re.sub(r'[^a-z0-9\s]', '', text)  # remove special chars except space
    return text.strip()

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/ask", methods=["POST"])
def ask():
    query = request.form.get("query", "")
    query_clean = clean_text(query)
    query_words = query_clean.split()

    matches = []

    for _, row in df.iterrows():
        # Concatenate row values for fuzzy matching
        row_text = " ".join([str(row['PARTY']), str(row.get('AREA', '')), str(row['MATERIAL'])]).lower()

        # Compute similarity score using rapidfuzz
        match_score = sum(fuzz.partial_ratio(q, row_text) for q in query_words) / len(query_words)

        if match_score >= 70:  # threshold
            matches.append({
                "PO": f"<b>{row['PO']}</b>",
                "Party": row['PARTY'],
                "SubArea": row.get('AREA', ''),
                "Material": row['MATERIAL']
            })

    if matches:
        return jsonify({"answer": matches})
    else:
        return jsonify({"answer": "Koi PO nahi mila, query check karein."})

if __name__ == "__main__":
    app.run(debug=True)
