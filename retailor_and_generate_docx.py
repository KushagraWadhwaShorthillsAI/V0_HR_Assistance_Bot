import os
import sys
import json
import re
from pymongo import MongoClient
from dotenv import load_dotenv
from job_matcher import JobDescriptionAnalyzer, ResumeRetailor
from docx_utils import DocxUtils

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI")
DB_NAME = os.getenv("DB_NAME")
COLLECTION_NAME = os.getenv("COLLECTION_NAME")

AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY")
AZURE_OPENAI_API_VERSION = os.getenv("AZURE_OPENAI_API_VERSION")
AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")

if not all([MONGO_URI, DB_NAME, COLLECTION_NAME, AZURE_OPENAI_API_KEY, AZURE_OPENAI_API_VERSION, AZURE_OPENAI_ENDPOINT]):
    print("❌ Please set all required environment variables in your shell or .env file.")
    sys.exit(1)

def get_resume_by_employee_id(employee_id):
    client = MongoClient(MONGO_URI)
    db = client[DB_NAME]
    collection = db[COLLECTION_NAME]
    resume = collection.find_one({"employee_id": employee_id})
    if not resume:
        print(f"❌ No resume found for employee_id: {employee_id}")
        sys.exit(1)
    return resume

def split_into_sentences(text):
    sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', text) if s.strip()]
    return sentences

def preprocess_projects(resume_data):
    for project in resume_data.get("projects", []):
        description = project.get("description", "")
        project["bullets"] = split_into_sentences(description)


def main():
    if len(sys.argv) < 2:
        print("Usage: python retailor_and_generate_docx.py <employee_id> [job_description_file.txt]")
        sys.exit(1)

    employee_id = sys.argv[1]

    # Fetch resume
    resume = get_resume_by_employee_id(employee_id)
    import datetime
    output_json_filename = f"resume_raw_{employee_id}_{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}.json"
    with open(output_json_filename, "w", encoding="utf-8") as f:
        json.dump(resume, f, ensure_ascii=False, indent=4)
    print(f"📄 Raw resume JSON saved to: {output_json_filename}")
    # Retailor resume if JD provided
    if len(sys.argv) >= 3:
        job_description_file = sys.argv[2]
        with open(job_description_file, "r", encoding="utf-8") as f:
            job_description = f.read()
        analyzer = JobDescriptionAnalyzer()
        keywords_result = analyzer.extract_keywords(job_description)
        keywords = keywords_result["keywords"]
        retailor = ResumeRetailor()
        retailored_resume = retailor.retailor_resume(resume, keywords, job_description)
    else:
        retailored_resume = resume
        keywords = None

    # Preprocess projects: split bullets into sentences
    preprocess_projects(retailored_resume)

    # Generate DOCX
    docx_file = DocxUtils.generate_docx(retailored_resume, keywords=keywords)
    output_filename = f"{retailored_resume.get('name', 'resume').replace(' ', '_')}_{employee_id}.docx"
    with open(output_filename, "wb") as f:
        f.write(docx_file.getbuffer())
    
    
    print(f"✅ DOCX generated: {output_filename}")

if __name__ == "__main__":
    main()
