import PyPDF2
import requests
import os
from dataclasses import dataclass
from PIL import Image
import pytesseract
import pdf2image

# Configure Tesseract path
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

@dataclass
class Question:
    question_text: str
    answer: str = ""
    topic: str = ""
    difficulty: str = ""
    question_type: str = ""  # MC, LQ, etc.

class PDFQuestionExtractor:
    def __init__(self, airtable_api_key: str, airtable_base_id: str):
        self.airtable_key = airtable_api_key
        self.airtable_base = airtable_base_id
        self.airtable_table = "Questions"  # Your Airtable table name
        
    def extract_text_from_pdf(self, pdf_path: str) -> str:
        """Extract text from PDF file, fallback to OCR if no text found"""
        text = ""
        # Try PyPDF2 first
        with open(pdf_path, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            for page in pdf_reader.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
        # If no text found, use OCR
        if not text.strip():
            try:
                # Path to local Poppler installation
                poppler_path = os.path.join(os.path.dirname(__file__), "poppler", "poppler-24.08.0", "Library", "bin")
                images = pdf2image.convert_from_path(pdf_path, poppler_path=poppler_path)
                print(f"   Successfully converted PDF to {len(images)} images")
                
                # Check if Tesseract is available
                try:
                    # Test if tesseract is working
                    test_result = pytesseract.get_tesseract_version()
                    print(f"   Using Tesseract version: {test_result}")
                except Exception as tesseract_error:
                    print(f"   Tesseract not available: {tesseract_error}")
                    return "OCR_NOT_AVAILABLE: Tesseract is not installed. Please install Tesseract OCR to extract text from image-based PDFs."
                
                ocr_text = ""
                for i, img in enumerate(images, 1):
                    print(f"   Processing page {i}/{len(images)} with OCR...")
                    page_text = pytesseract.image_to_string(img)
                    ocr_text += page_text + "\n"
                print(f"   OCR completed. Extracted {len(ocr_text)} characters")
                text = ocr_text
            except Exception as e:
                print(f"OCR extraction failed: {e}")
                return f"OCR_FAILED: {str(e)}"
        return text

    def upload_raw_text_to_airtable(self, text: str) -> bool:
        url = f"https://api.airtable.com/v0/{self.airtable_base}/{self.airtable_table}"
        headers = {
            "Authorization": f"Bearer {self.airtable_key}",
            "Content-Type": "application/json"
        }
        record = {
            "fields": {
                "Raw Text": text,
            }
        }
        data = {"records": [record]}
        try:
            response = requests.post(url, headers=headers, json=data)
            response.raise_for_status()
            return True
        except requests.exceptions.RequestException as e:
            print(f"Error uploading raw text: {e}")
            return False

    def process_pdf(self, pdf_path: str) -> dict:
        print(f"Processing PDF: {pdf_path}")
        print("1. Extracting text from PDF...")
        text = self.extract_text_from_pdf(pdf_path)
        if not text.strip():
            return {"success": False, "error": "No text found in PDF"}
        print(f"   Extracted {len(text)} characters")
        print("Extracted text sample:", text[:1000])
        print("2. Uploading raw text to Airtable...")
        success = self.upload_raw_text_to_airtable(text)
        if success:
            return {"success": True, "message": "Successfully uploaded raw text to Airtable"}
        else:
            return {"success": False, "error": "Failed to upload to Airtable"}

# Usage Example
def main():
    AIRTABLE_API_KEY = "your-airtable-api-key"
    AIRTABLE_BASE_ID = "your-airtable-base-id"
    extractor = PDFQuestionExtractor(
        airtable_api_key=AIRTABLE_API_KEY,
        airtable_base_id=AIRTABLE_BASE_ID
    )
    pdf_path = "math_questions.pdf"  # Path to your PDF
    result = extractor.process_pdf(pdf_path)
    if result["success"]:
        print(f"✅ {result['message']}")
    else:
        print(f"❌ Error: {result['error']}")

if __name__ == "__main__":
    main()

# Required packages installation:
# pip install PyPDF2 requests pillow pytesseract pdf2image