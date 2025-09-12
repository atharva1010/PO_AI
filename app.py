from flask import Flask, request, jsonify
import pandas as pd
from rapidfuzz import process, fuzz

app = Flask(__name__)

# --- Load Data ---
df = pd.read_excel("data.xlsx")

# Columns: ["Party Name", "Area", "Material", "PO"]

# --- Dictionary of Known Words for Auto-correct ---
known_words = set()
for col in ["Party Name", "Area", "Material"]:
    for val in df[col].dropna().astype(str).tolist():
        for w in val.lower().split():
            known_words.add(w.strip())

# --- Helper: Auto-correct each word ---
def autocorrect_word(word):
    if not word.strip():
        return word
    match, score, _ = process.extractOne(word, known_words, scorer=fuzz.ratio)
    if score > 70:  # threshold for correction
        return match
    return word

def normalize_query(query):
    words = query.lower().split()
    corrected = [autocorrect_word(w) for w in words]
    return " ".join(corrected)

@app.route("/search", methods=["GET"])
def search():
    user_query = request.args.get("q", "").lower().strip()
    if not user_query:
        return jsonify({"error": "❌ Query missing"}), 400

    # Auto-correct the query
    corrected_query = normalize_query(user_query)

    # Try to match row where ALL words present
    results = []
    for _, row in df.iterrows():
        row_text = f"{row['Party Name']} {row['Area']} {row['Material']}".lower()
        if all(word in row_text for word in corrected_query.split()):
            results.append({
                "Party": row["Party Name"],
                "Area": row["Area"],
                "Material": row["Material"],
                "PO": row["PO"]
            })

    if results:
        return jsonify({"corrected_query": corrected_query, "results": results})
    else:
        return jsonify({"corrected_query": corrected_query, "message": "❌ Koi exact PO nahi mila."})

if __name__ == "__main__":
    app.run(debug=True)
