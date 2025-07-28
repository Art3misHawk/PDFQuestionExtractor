from flask import Flask, request, jsonify
import os
from pdf_question_extractor import PDFQuestionExtractor

app = Flask(__name__)

@app.route("/", methods=["GET"])
def index():
    with open("deploy.html") as f:
        return f.read()

@app.route("/upload", methods=["POST"])
def upload():
    # Get form fields
    airtable_key = request.form.get("airtableKey")
    airtable_base = request.form.get("airtableBase")
    file = request.files.get("pdfFile")

    if not file or file.filename == "":
        return jsonify({"success": False, "error": "No PDF file uploaded."}), 400

    # Save uploaded file
    os.makedirs("uploads", exist_ok=True)
    filepath = os.path.join("uploads", file.filename)
    file.save(filepath)

    # Initialize extractor with provided keys
    extractor = PDFQuestionExtractor(
        airtable_api_key=airtable_key,
        airtable_base_id=airtable_base
    )

    # Process PDF
    result = extractor.process_pdf(filepath)
    os.remove(filepath)

    response = {
        "success": result.get("success", False),
        "message": result.get("message", ""),
        "error": result.get("error", "")
    }
    return jsonify(response)

@app.errorhandler(400)
@app.errorhandler(404)
@app.errorhandler(405)
@app.errorhandler(500)
def handle_error(e):
    return jsonify(success=False, error=str(e)), getattr(e, 'code', 500)

if __name__ == "__main__":
    app.run(debug=True)