from flask import Flask, request, jsonify
import pandas as pd
from rapidfuzz import fuzz

app = Flask(__name__)

# Load CSV
df = pd.read_csv("data/po_data.csv", dtype=str)
df.fillna('', inplace=True)

# Translation & synonym dictionary
TRANSLATE_DICT = {
    # Materials
    "SUBHABHOOL": "SUBABOOL",
    "SUBABOOL": "SUBABOOL",
    "EUCALYPTUS": "EUCALYPTUS-LOPS-AND-TOPS",
    "UK LIPTIS": "EUCALYPTUS-LOPS-AND-TOPS",
    "POPLAR": "POPLAR-LOPS-AND-TOPS-2 INCH TO 12 INCH",
    "POPULAR": "POPLAR-LOPS-AND-TOPS-2 INCH TO 12 INCH",
    "FIREWOOD": "FIREWOOD-MUDDY",
    "FARRA": "FARRA-WOOD",
    # Parties
    "HARYANA TIMBER": "HARYANA TIMBERS",
    "MFK ENTERPRISES": "M.F.K.ENTERPRISES",
    "MARUTI TRADING": "MARUTI TRADING COMPANY -(UP)",
    "RUCHI": "RUCHI ENTERPRISES",
    "SHIVA GOODS": "SHIVA GOODS CARRIER PVT LTD",
    "SHIVA CARRIER": "SHIVA GOODS CARRIER PVT LTD",
    "SHIVA VEENER": "SHIVA VEENER (INDIA) PVT LTD",
    "SHIVA WINNER": "SHIVA VEENER (INDIA) PVT LTD",
    "VINAYAK": "VINAYAK TRADERS",
    "AK INDUSTRIES": "A.K. INDUSTRIES (09CPTPS6130P1ZT)",
    "DEV BHOOMI": "DEV BHOOMI ENTERPRISES",
    "SHRI VINAYAK": "SHRI VINAYAK PLY IND P. LTD-UPs",
    "KHAN": "KHAN TIMBER",
    "SHRI BALAJI": "SHRI BALAJI ENTERPRISES -(RAMPUR)",
    "KGN": "KGN TRADERS",
    "SHIVA TIMBER": "SHIVA TIMBER",
    "GHASEETA": "GHASEETA KHAN",
    "GANESHA": "GANESHA TRADERS",
    "SHAM": "SHAM ENTERPRISES",
    "BHAGAT": "BHAGAT WOOD CRAFTS",
    "CHAUDHARY": "CHAUDHARY TIMBER"
}

# Helper to translate user words
def translate_word(word):
    word_upper = word.upper()
    return TRANSLATE_DICT.get(word_upper, word_upper)

# Endpoint
@app.route("/ask", methods=["POST"])
def ask():
    user_text = request.json.get("text", "")
    user_words = [translate_word(w) for w in user_text.strip().split()]
    
    results = []
    for _, row in df.iterrows():
        row_text = f"{row['PARTY']} {row['AREA']} {row['MATERIAL']}"
        match_count = sum(1 for w in user_words if fuzz.partial_ratio(w, row_text) > 80)
        # Only include row if all words are matched with some fuzz
        if match_count == len(user_words):
            results.append({
                "PO": row["PO"],
                "PARTY": row["PARTY"],
                "AREA": row["AREA"],
                "MATERIAL": row["MATERIAL"]
            })
    
    if not results:
        return jsonify({"message": "❌ Koi exact PO nahi mila."})
    
    return jsonify(results)

if __name__ == "__main__":
    app.run(debug=True)
