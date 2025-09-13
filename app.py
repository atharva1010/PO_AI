from flask import Flask, render_template, request, jsonify
import pandas as pd
import os
import re
from rapidfuzz import process, fuzz
from openai import OpenAI

app = Flask(__name__)

# ✅ CSV load
CSV_FILE = "post_offices.csv"
if os.path.exists(CSV_FILE):
    df = pd.read_csv(CSV_FILE)
else:
    df = pd.DataFrame(columns=["Office Name", "Pincode", "District", "State"])

# ✅ OpenAI client
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY", "sk-your-key-here"))

# 🔍 CSV search
def search_po(query):
    results = []
    query = query.strip().lower()
    for col in ["Office Name", "Pincode", "District", "State"]:
        matches = process.extract(query, df[col].astype(str).str.lower().tolist(), limit=3, scorer=fuzz.WRatio)
        for match, score, idx in matches:
            if score > 70:
                row = df.iloc[idx].to_dict()
                results.append(row)
    return results

# 🤖 OpenAI answer
def ask_ai(query):
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a helpful assistant. Answer clearly and correctly."},
                {"role": "user", "content": query}
            ]
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"⚠️ AI Error: {str(e)}"

# 🏠 Home route
@app.route("/")
def index():
    return render_template("index.html")

# 📌 Search only in CSV
@app.route("/search", methods=["POST"])
def search():
    data = request.get_json()
    query = data.get("query", "").strip()
    if not query:
        return jsonify({"answer": "⚠️ Query empty!"})
    results = search_po(query)
    if not results:
        return jsonify({"answer": "❌ Koi PO nahi mila."})
    return jsonify({"answer": str(results)})

# 📌 Ask AI (general questions)
@app.route("/ask", methods=["POST"])
def ask():
    data = request.get_json()
    query = data.get("query", "").strip()
    if not query:
        return jsonify({"answer": "⚠️ Query empty!"})
    return jsonify({"answer": ask_ai(query)})

if __name__ == "__main__":
    app.run(debug=True)
