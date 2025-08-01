from docxtpl import DocxTemplate
from io import BytesIO
import os

class DocxUtils:
    TEMPLATE_PATH = "Resume_Final.docx"

    @staticmethod
    def generate_docx(resume_data: dict, keywords: list = None) -> BytesIO:
        if not os.path.exists(DocxUtils.TEMPLATE_PATH):
            raise FileNotFoundError(f"❌ Template not found: {DocxUtils.TEMPLATE_PATH}")

        resume_data = resume_data.copy()
        resume_data.setdefault("education", [])
        resume_data.setdefault("skills", [])
        resume_data.setdefault("projects", [])
        resume_data.setdefault("experience", [])

        if "certification" in resume_data:
            resume_data["certifications"] = resume_data.pop("certification")
        resume_data.setdefault("certifications", [])

        context = {
            "candidate": resume_data,
            "keywords": keywords or []
        }

        # Load template as BytesIO
        with open(DocxUtils.TEMPLATE_PATH, "rb") as f:
            template_stream = BytesIO(f.read())

        tpl = DocxTemplate(template_stream)
        tpl.render(context)

        output = BytesIO()
        tpl.save(output)
        output.seek(0)

        return output

if __name__ == "__main__":
    import sys, json, os
    try:
        resume_json_str = os.environ.get("RESUME_JSON")
        if resume_json_str:
            resume_json = json.loads(resume_json_str)
        else:
            resume_json = json.load(sys.stdin)
        docx_stream = DocxUtils.generate_docx(resume_json)
        sys.stdout.buffer.write(docx_stream.read())

    except Exception as e:
        sys.stderr.write(f"Error in docx_utils CLI: {e}\n")
        sys.exit(1)
