import PyPDF2
import openai
import requests
import json
import re
from typing import List, Dict
import os
from dataclasses import dataclass
# Add OCR imports
from PIL import Image
import pytesseract
import pdf2image

@dataclass
class Question:
    question_text: str
    answer: str = ""
    topic: str = ""
    difficulty: str = ""
    question_type: str = ""  # MC, LQ, etc.

class PDFQuestionExtractor:
    def __init__(self, deepseek_api_key: str, airtable_api_key: str, airtable_base_id: str):
        self.deepseek_client = openai.OpenAI(api_key=deepseek_api_key, base_url="https://api.deepseek.com")
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
                images = pdf2image.convert_from_path(pdf_path)
                ocr_text = ""
                for img in images:
                    ocr_text += pytesseract.image_to_string(img) + "\n"
                text = ocr_text
            except Exception as e:
                print(f"OCR extraction failed: {e}")
        return text
    
    def parse_questions_with_ai(self, text: str) -> List[Question]:
        """Use DeepSeek to identify and structure questions from text"""
        
        system_prompt = """You are an expert at extracting math questions from text. 
        
        Analyze the provided text and extract individual math questions. For each question:
        1. Identify the complete question text (including any diagrams descriptions)
        2. Determine the answer if provided
        3. Classify the topic (e.g., Integration, Differentiation, Probability, etc.)
        4. Assess difficulty (Easy, Medium, Hard)
        5. Identify type (MC for multiple choice, LQ for long question)
        
        Return a JSON array of questions in this format:
        [
          {
            "question_text": "Complete question including all parts",
            "answer": "Answer if available, empty string if not",
            "topic": "Math topic category",
            "difficulty": "Easy/Medium/Hard",
            "question_type": "MC/LQ"
          }
        ]
        
        Only extract actual math questions, ignore headers, instructions, or non-question content."""
        
        try:
            response = self.deepseek_client.chat.completions.create(
                model="deepseek-chat",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Extract math questions from this text:\n\n{text}"}
                ],
                temperature=0.1,
                max_tokens=4000
            )
            
            questions_data = json.loads(response.choices[0].message.content)
            return [Question(**q) for q in questions_data]
            
        except Exception as e:
            print(f"Error parsing questions with DeepSeek: {e}")
            return []
    
    def upload_to_airtable(self, questions: List[Question]) -> bool:
        """Upload questions to Airtable database"""
        
        url = f"https://api.airtable.com/v0/{self.airtable_base}/{self.airtable_table}"
        headers = {
            "Authorization": f"Bearer {self.airtable_key}",
            "Content-Type": "application/json"
        }
        
        # Batch upload (max 10 records per request)
        batch_size = 10
        total_uploaded = 0
        
        for i in range(0, len(questions), batch_size):
            batch = questions[i:i + batch_size]
            
            records = []
            for question in batch:
                record = {
                    "fields": {
                        "Question Text": question.question_text,
                        "Answer": question.answer,
                        "Topic": question.topic,
                        "Difficulty": question.difficulty,
                        "Type": question.question_type,
                        "Source": "PDF Upload",
                        "Created": "2024-01-01"  # You can customize this
                    }
                }
                records.append(record)
            
            data = {"records": records}
            
            try:
                response = requests.post(url, headers=headers, json=data)
                response.raise_for_status()
                
                result = response.json()
                uploaded_count = len(result.get('records', []))
                total_uploaded += uploaded_count
                print(f"Uploaded batch {i//batch_size + 1}: {uploaded_count} questions")
                
            except requests.exceptions.RequestException as e:
                print(f"Error uploading batch {i//batch_size + 1}: {e}")
                continue
        
        print(f"Total questions uploaded: {total_uploaded}")
        return total_uploaded > 0
    
    def process_pdf(self, pdf_path: str) -> Dict:
        """Main function to process PDF and upload to Airtable"""
        
        print(f"Processing PDF: {pdf_path}")
        
        # Step 1: Extract text from PDF
        print("1. Extracting text from PDF...")
        text = self.extract_text_from_pdf(pdf_path)
        
        if not text.strip():
            return {"success": False, "error": "No text found in PDF"}
        
        print(f"   Extracted {len(text)} characters")
        print("Extracted text sample:", text[:1000])  # Print first 1000 characters
        
        # Step 2: Parse questions with AI
        print("2. Parsing questions with AI...")
        questions = self.parse_questions_with_ai(text)
        
        if not questions:
            return {"success": False, "error": "No questions found in text"}
        
        print(f"   Found {len(questions)} questions")
        
        # Step 3: Upload to Airtable
        print("3. Uploading to Airtable...")
        success = self.upload_to_airtable(questions)
        
        if success:
            return {
                "success": True, 
                "questions_count": len(questions),
                "message": f"Successfully uploaded {len(questions)} questions to Airtable"
            }
        else:
            return {"success": False, "error": "Failed to upload to Airtable"}

# Usage Example
def main():
    # Configuration
    DEEPSEEK_API_KEY = "sk-4f97f98a8dfc4ad2bf588d7482cb3757"
    AIRTABLE_API_KEY = "patoB1HXWjSRw5NKT.1b14cf94bdc2c2229ea9c65ee70c92a83c91427b6fcf37892d2c124558ac394f" 
    AIRTABLE_BASE_ID = "appYdYbwrRDnZzjFs"
    
    # Initialize extractor
    extractor = PDFQuestionExtractor(
        deepseek_api_key="sk-4f97f98a8dfc4ad2bf588d7482cb3757",
        airtable_api_key="patoB1HXWjSRw5NKT.1b14cf94bdc2c2229ea9c65ee70c92a83c91427b6fcf37892d2c124558ac394f",
        airtable_base_id="appYdYbwrRDnZzjFs"
    )
    
    # Process PDF
    pdf_path = "math_questions.pdf"  # Path to your PDF
    result = extractor.process_pdf(pdf_path)
    
    if result["success"]:
        print(f"✅ {result['message']}")
    else:
        print(f"❌ Error: {result['error']}")

if __name__ == "__main__":
    main()

# Required packages installation:
# pip install PyPDF2 openai requests