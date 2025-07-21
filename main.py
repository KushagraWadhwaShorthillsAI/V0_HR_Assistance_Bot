import streamlit as st
import os
import json
import tempfile
from pathlib import Path
import asyncio
from datetime import datetime
import copy
from pdf_utils import PDFUtils  # Import the new class
from docx_utils import DocxUtils # Import the DocxUtils class
# Import your existing modules
from openai import AzureOpenAI
from llama_resume_parser import ResumeParser
from standardizer import ResumeStandardizer
from db_manager import ResumeDBManager
from OCR_resume_parser import ResumeParserwithOCR
from final_retriever import run_retriever, render_formatted_resume  # Retriever engine
from job_matcher import JobMatcher, JobDescriptionAnalyzer  # Import both classes from job_matcher
import streamlit.components.v1 as components
import uuid
import base64
import pandas as pd
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode

# Add this after imports, before any use

def add_row_number_column(df):
    df = df.copy()
    df.insert(0, '#', range(1, len(df) + 1))
    return df

# Set page configuration
st.set_page_config(
    page_title="HR Resume Bot",
    page_icon="📄",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for improved UI
st.markdown("""
<style>
.main {
    padding: 2rem;
}
.stButton button {
    width: 100%;
    border-radius: 8px;
    font-weight: 500;
    transition: all 0.3s ease;
}
.stButton button:hover {
    transform: translateY(-2px);
    box-shadow: 0 4px 12px rgba(0,0,0,0.15);
}
.card {
    background: linear-gradient(135deg, #f8f9fa 0%, #ffffff 100%);
    border-radius: 12px;
    padding: 24px;
    margin-bottom: 20px;
    border-left: 4px solid #0068c9;
    box-shadow: 0 2px 8px rgba(0,0,0,0.1);
}
.card:hover {
    box-shadow: 0 8px 25px rgba(0,0,0,0.15);
    transform: translateY(-2px);
    transition: all 0.3s ease;
}
.candidate-name {
    font-size: 22px;
    font-weight: 700;
    color: #0068c9;
    margin-bottom: 8px;
}
.contact-info {
    color: #555;
    margin: 12px 0;
    font-size: 14px;
}
.score-info {
    color: #666;
    font-size: 14px;
    margin-top: 12px;
    padding-top: 12px;
    border-top: 1px solid #e9ecef;
}
.accepted {
    color: #28a745;
    font-weight: 600;
}
.rejected {
    color: #dc3545;
    font-weight: 600;
}
.result-count {
    font-size: 20px;
    font-weight: 600;
    margin-bottom: 24px;
    color: #333;
}
.section-header {
    background: linear-gradient(90deg, #0068c9, #0056b3);
    color: white;
    padding: 12px 20px;
    border-radius: 8px;
    font-weight: 600;
    margin: 20px 0 16px 0;
    box-shadow: 0 2px 8px rgba(0,104,201,0.3);
}
.add-button {
    background: linear-gradient(45deg, #28a745, #20c997) !important;
    border: none !important;
    color: white !important;
    border-radius: 8px !important;
    padding: 8px 16px !important;
    font-weight: 500 !important;
}
.delete-button {
    background: linear-gradient(45deg, #dc3545, #e74c3c) !important;
    border: none !important;
    color: white !important;
    border-radius: 8px !important;
    padding: 8px 16px !important;
    font-weight: 500 !important;
}
.success-message {
    background: #d4edda;
    border: 1px solid #c3e6cb;
    color: #155724;
    padding: 12px;
    border-radius: 8px;
    margin: 8px 0;
}
.error-message {
    background: #f8d7da;
    border: 1px solid #f5c6cb;
    color: #721c24;
    padding: 12px;
    border-radius: 8px;
    margin: 8px 0;
}
.ag-theme-streamlit {
    border-radius: 8px;
    border: 1px solid #e9ecef;
    overflow: hidden;
}
.ag-header {
    background: linear-gradient(90deg, #f8f9fa, #ffffff);
    font-weight: 600;
}
.info-box {
    background: #e7f3ff;
    border: 1px solid #b3d9ff;
    color: #0056b3;
    padding: 16px;
    border-radius: 8px;
    margin: 16px 0;
    font-size: 14px;
}
.warning-box {
    background: #fff3cd;
    border: 1px solid #ffeaa7;
    color: #856404;
    padding: 16px;
    border-radius: 8px;
    margin: 16px 0;
    font-size: 14px;
}
</style>
""", unsafe_allow_html=True)

# Sidebar for app navigation and explanations
st.sidebar.title("HR Assistance Bot")
page = st.sidebar.selectbox("Navigate", [
    "Resume Search Engine",
    "JD-Resume Regeneration",
    "Database Management", 
], index=1)  # Set index=1 to make JD-Resume Regeneration the default

# Add explanatory text based on selected page
if page == "Resume Search Engine":
    st.sidebar.markdown("""
    """)
elif page == "JD-Resume Regeneration":
    st.sidebar.markdown("""
    ### 🎯 JD-Resume Regeneration
    This page allows you to:
    1. Input a job description
    2. Automatically extract relevant keywords
    3. Score and rank candidates based on their match
    4. View detailed matching analysis
    5. See only the most relevant candidates
    """)
elif page == "Upload & Process":
    st.sidebar.markdown("""
    ### 📤 Upload & Process
    This page allows you to:
    1. Upload multiple resume files (PDF/DOCX)
    2. Automatically process them through our pipeline:
       - Parse and extract content
       - Standardize the format
       - Store in database
    3. Preview processed resumes
    """)
elif page == "Database Management":
    st.sidebar.markdown("""
    ### 💾 Database Management
    This page enables you to:
    1. View all stored resumes
    2. Search resumes by specific fields
    3. View detailed resume information
    4. Manage the resume database
    """)

# Initialize session state for tracking job progress
if "processing_complete" not in st.session_state:
    st.session_state.processing_complete = False
if "standardizing_complete" not in st.session_state:
    st.session_state.standardizing_complete = False
if "db_upload_complete" not in st.session_state:
    st.session_state.db_upload_complete = False
if "processed_files" not in st.session_state:
    st.session_state.processed_files = []
if "standardized_files" not in st.session_state:
    st.session_state.standardized_files = []
if "uploaded_files" not in st.session_state:
    st.session_state.uploaded_files = []

# Initialize session state for job matcher
if "matcher" not in st.session_state:
    st.session_state.matcher = None
if "extracted_keywords" not in st.session_state:
    st.session_state.extracted_keywords = set()
if "job_matcher_results" not in st.session_state:
    st.session_state.job_matcher_results = []

# Initialize session state variables if they don't exist
if 'expander_open_single' not in st.session_state:
    st.session_state['expander_open_single'] = True
if 'summary_generation_requested' not in st.session_state:
    st.session_state['summary_generation_requested'] = False
if 'summary_generation_complete' not in st.session_state:
    st.session_state['summary_generation_complete'] = False

# After other session state initializations near the top of the script:
if 'aggrid_key_suffixes_bulk' not in st.session_state:
    st.session_state['aggrid_key_suffixes_bulk'] = {}
if 'aggrid_edu_single_key_suffix' not in st.session_state:
    st.session_state['aggrid_edu_single_key_suffix'] = 0
if 'aggrid_cert_single_key_suffix' not in st.session_state:
    st.session_state['aggrid_cert_single_key_suffix'] = 0
if 'aggrid_proj_single_key_suffix' not in st.session_state:
    st.session_state['aggrid_proj_single_key_suffix'] = 0
if 'aggrid_skill_single_key_suffix' not in st.session_state:
    st.session_state['aggrid_skill_single_key_suffix'] = 0
if 'resume_data' not in st.session_state:
    st.session_state.resume_data = None

def process_uploaded_files(uploaded_files):
    """Process uploaded resume files through the parser"""
    st.session_state.processing_complete = False
    st.session_state.standardizing_complete = False
    st.session_state.db_upload_complete = False
    st.session_state.processed_files = []

    st.write(f"Processing {len(uploaded_files)} files...")
    progress_bar = st.progress(0)
    status_text = st.empty()

    total_files = len(uploaded_files)
    processed_count = 0

    files_to_process = list(uploaded_files)

    for i, uploaded_file in enumerate(files_to_process):
        file_name = uploaded_file.name
        status_text.text(f"Processing {i+1}/{total_files}: {file_name}")

        temp_file_path = os.path.join(temp_dir, file_name)
        with open(temp_file_path, "wb") as f:
            f.write(uploaded_file.getbuffer())

        file_ext = Path(file_name).suffix.lower()
        parser = ResumeParser()  # Instantiate inside loop to avoid event loop issues

        if file_ext not in parser.SUPPORTED_EXTENSIONS:
            st.warning(f"Skipping {file_name}: Unsupported file type {file_ext}")
            continue

        try:
            parsed_resume = parser.parse_resume(temp_file_path)
            if parsed_resume:
                parsed_resume["timestamp"] = datetime.now().isoformat()
                parsed_resume["original_filename"] = file_name

                output_path = parsed_dir / f"{Path(file_name).stem}.json"
                with open(output_path, "w", encoding="utf-8") as f:
                    json.dump(parsed_resume, f, indent=2, ensure_ascii=False)

                st.session_state.processed_files.append(output_path)
                processed_count += 1
            else:
                st.warning(f"No content extracted from {file_name}")
        except Exception as e:
            st.error(f"Error parsing {file_name}: {str(e)}")

        progress_bar.progress((i + 1) / total_files)

    status_text.text(f"✅ Processed {processed_count}/{total_files} files")
    st.session_state.processing_complete = True
    
async def standardize_resumes():
    """Standardize the parsed resumes using ResumeStandardizer"""
    st.session_state.standardizing_complete = False
    st.session_state.standardized_files = []
    
    # Show status
    st.write(f"Standardizing {len(st.session_state.processed_files)} files...")
    
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    # Initialize the standardizer
    try:
        standardizer = ResumeStandardizer()
    except ValueError as e:
        st.error(f"Error initializing standardizer: {e}")
        return
    
    total_files = len(st.session_state.processed_files)
    standardized_count = 0
    
    # Create a copy of processed files list to prevent any potential issues with iteration
    files_to_standardize = list(st.session_state.processed_files)
    
    for i, file_path in enumerate(files_to_standardize):
        status_text.text(f"Standardizing {i+1}/{total_files}: {file_path.name}")
        
        # Modify the standardizer to use our temp paths
        output_path = standardized_dir / file_path.name
        
        if output_path.exists():
            st.session_state.standardized_files.append(output_path)
            standardized_count += 1
            progress_bar.progress((i + 1) / total_files)
            continue
        
        try:
            with open(file_path, encoding="utf-8") as f:
                raw = json.load(f)
            
            content = raw.get("content", "")
            links = raw.get("links", [])
            
            if not content.strip():
                st.warning(f"Empty content in {file_path.name}, skipping.")
                continue
            
            prompt = standardizer.make_standardizer_prompt(content, links)
            raw_response = await standardizer.call_azure_llm(prompt)
            
            # Log raw response
            raw_log_path = standardized_dir / f"{file_path.stem}_raw.md"
            with open(raw_log_path, "w", encoding="utf-8") as f:
                f.write(raw_response)
            
            cleaned_json = standardizer.clean_llm_response(raw_response)
            parsed_json = json.loads(cleaned_json)
            
            # Add timestamp, file source and original filename
            parsed_json["timestamp"] = datetime.now().isoformat()
            parsed_json["source_file"] = str(file_path)
            if "original_filename" in raw:
                parsed_json["original_filename"] = raw["original_filename"]
            
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(parsed_json, f, indent=2, ensure_ascii=False)
            
            st.session_state.standardized_files.append(output_path)
            standardized_count += 1
        except Exception as e:
            st.error(f"Error standardizing {file_path.name}: {str(e)}")
        
        # Update progress
        progress_bar.progress((i + 1) / total_files)
    
    status_text.text(f"✅ Standardized {standardized_count}/{total_files} files")
    st.session_state.standardizing_complete = True

def convert_objectid_to_str(obj):
    """Recursively turn any ObjectId into its string form."""
    if isinstance(obj, dict):
        return {k: convert_objectid_to_str(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [convert_objectid_to_str(i) for i in obj]
    # Match ObjectId by name to avoid importing bson here
    elif type(obj).__name__ == "ObjectId":
        return str(obj)
    else:
        return obj
    
def upload_to_mongodb():
    """Upload standardized resumes to MongoDB"""
    st.session_state.db_upload_complete = False
    
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    # Initialize DB manager
    try:
        db_manager = ResumeDBManager()
    except Exception as e:
        st.error(f"Error connecting to MongoDB: {e}")
        return
    
    total_files = len(st.session_state.standardized_files)
    uploaded_count = 0
    
    for i, file_path in enumerate(st.session_state.standardized_files):
        status_text.text(f"Uploading {i+1}/{total_files}: {file_path.name}")
        
        try:
            with open(file_path, encoding="utf-8") as f:
                resume_data = json.load(f)
            
            # Insert or update in MongoDB
            db_manager.insert_or_update_resume(resume_data)
            uploaded_count += 1
            st.session_state.uploaded_files.append(file_path.name)
        except Exception as e:
            st.error(f"Error uploading {file_path.name}: {e}")
        
        # Update progress
        progress_bar.progress((i + 1) / total_files)
    
    status_text.text(f"✅ Uploaded {uploaded_count}/{total_files} resumes to MongoDB")
    st.session_state.db_upload_complete = True

def validate_and_reprocess_resumes(uploaded_files):
    """Validate standardized resumes and reprocess if 'name' is missing."""
    st.write("🔍 Validating standardized resumes...")
    reprocessed_count = 0

    for file_path in st.session_state.standardized_files:
        try:
            with open(file_path, encoding="utf-8") as f:
                resume_data = json.load(f)

            # Check if 'name' is missing
            if not resume_data.get("name") or len(resume_data.get("name").split()[0]) < 2:
                st.warning(f"⚠️ Missing 'name' in {file_path.name}. Reprocessing...")
                reprocessed_count += 1

                # Find the original file in uploaded files
                original_file_name = file_path.stem  # Remove .json extension
                original_file = next(
                    (file for file in uploaded_files if Path(file.name).stem == original_file_name),
                    None
                )

                if not original_file:
                    st.error(f"❌ Original file for {file_path.name} not found in uploaded files.")
                    continue

                # Save the uploaded file temporarily
                temp_file_path = temp_dir / original_file.name
                with open(temp_file_path, "wb") as f:
                    f.write(original_file.getbuffer())

                # Re-parse the original file
                parser = ResumeParserwithOCR()
                parsed_resume = parser.parse_resume(temp_file_path)

                if parsed_resume:
                    # Save parsed data
                    parsed_output_path = parsed_dir / f"{original_file_name}.json"
                    parser.save_to_json(parsed_resume, parsed_output_path)

                    # Re-standardize the parsed data
                    standardizer = ResumeStandardizer()
                    content = parsed_resume.get("content", "")
                    links = parsed_resume.get("links", [])
                    prompt = standardizer.make_standardizer_prompt(content, links)
                    raw_response = asyncio.run(standardizer.call_azure_llm(prompt))
                    cleaned_json = standardizer.clean_llm_response(raw_response)
                    parsed_json = json.loads(cleaned_json)

                    # Add metadata
                    parsed_json["timestamp"] = datetime.now().isoformat()
                    parsed_json["source_file"] = str(temp_file_path)
                    parsed_json["original_filename"] = original_file.name

                    # Save re-standardized data
                    with open(file_path, "w", encoding="utf-8") as f:
                        json.dump(parsed_json, f, indent=2, ensure_ascii=False)

                    st.success(f"✅ Reprocessed and standardized: {file_path.name}")
                else:
                    st.error(f"❌ Failed to re-parse {original_file.name}")
        except Exception as e:
            st.error(f"Error validating {file_path.name}: {e}")

    st.write(f"🔄 Reprocessed {reprocessed_count} resumes with missing 'name'.")

# Create temp directories for processing
temp_dir = Path(tempfile.gettempdir()) / "resume_processor"
parsed_dir = temp_dir / "parsed"
standardized_dir = temp_dir / "standardized"
for directory in [parsed_dir, standardized_dir]:
    directory.mkdir(parents=True, exist_ok=True)

# -------------------
# Page: Boolean Search Engine
# -------------------
if page == "Resume Search Engine":
    # Prevent duplicate set_page_config calls in the retriever module
    original_spc = st.set_page_config
    st.set_page_config = lambda *args, **kwargs: None

    try:
        run_retriever()
    finally:
        st.set_page_config = original_spc

# -------------------
# Page: JD-Resume Regeneration
# -------------------
elif page == "JD-Resume Regeneration":
    st.title("🎯 JD-Resume Regeneration")
    st.markdown("""
    <div class="info-box">
    <h4>🚀 AI-Powered Resume Retailoring System</h4>
    Transform candidate resumes to perfectly match job requirements with our intelligent system:
    <ul>
        <li><strong>📊 Smart Analysis:</strong> Extract relevant keywords and requirements from job descriptions</li>
        <li><strong>🎯 Candidate Matching:</strong> Score and rank candidates based on compatibility</li>
        <li><strong>✨ Automatic Optimization:</strong> Retailor resumes with job-specific skills and project descriptions</li>
        <li><strong>📝 Interactive Editing:</strong> Fine-tune all sections with real-time preview</li>
        <li><strong>📄 Professional Output:</strong> Generate polished PDF and Word documents</li>
    </ul>
    </div>
    """, unsafe_allow_html=True)

    # Create two tabs for different search types
    tab1, tab2 = st.tabs(["🔍 Bulk Search ", "👤 Individual Retailor"])

    with tab1:
        st.markdown("### 🔍 Search Multiple Candidates")
        st.markdown("Enter a job description to find and evaluate multiple matching candidates.")

        job_description = st.text_area(
            "📝 Enter Job Description",
            height=200,
            placeholder="Paste the job description here.",
            key="bulk_jd"
        )

        if job_description and st.button("🔍 Find Matching Candidates", type="primary", key="bulk_search"):
            progress = st.progress(0)
            status = st.empty()
            with st.spinner("Analyzing and matching candidates…"):
                matcher = JobMatcher()
                st.session_state.matcher = matcher
                analyzer = JobDescriptionAnalyzer()
                kw = analyzer.extract_keywords(job_description)
                st.session_state.extracted_keywords = kw["keywords"]
                results = matcher.find_matching_candidates(
                    job_description,
                    progress_bar=progress,
                    status_text=status
                )
                st.session_state.job_matcher_results = results
            progress.empty()
            status.empty()

        if st.session_state.extracted_keywords:
            st.subheader("🔑 Extracted Keywords")
            st.write(", ".join(sorted(st.session_state.extracted_keywords)))

        if st.session_state.job_matcher_results:
            accepted = [c for c in st.session_state.job_matcher_results if c["status"] == "Accepted"]
            if accepted:
                st.success(f"✅ Found {len(accepted)} matching candidates")
                st.subheader("📋 Detailed Candidate Profiles")
                for cand in accepted:
                    resume_key = f'resume_data_{cand["mongo_id"]}'
                    view_mode_key = f'view_mode_{cand["mongo_id"]}'
                    if view_mode_key not in st.session_state:
                        st.session_state[view_mode_key] = 'original'
                    if resume_key not in st.session_state or not st.session_state[resume_key]:
                        st.session_state[resume_key] = copy.deepcopy(cand.get("resume", {}))
                        for field, default in [
                            ("education", []),
                            ("certifications", []),
                            ("projects", []),
                            ("skills", []),
                            ("name", ""),
                            ("title", ""),
                            ("summary", "")
                        ]:
                            st.session_state[resume_key].setdefault(field, default)
                    resume_data = st.session_state[resume_key]
                    with st.expander(f"👤 {cand['name']} - Score: {cand['score']}/100", expanded=False):
                        st.markdown(f"""
                        <div class="card">
                        <div class="candidate-name">{cand['name']}</div>
                        <div class="contact-info">
                            📧 {cand['email']} | 📱 {cand['phone']}
                        </div>
                        <div class="score-info">
                            Score: {cand['score']}/100 | 
                            Status: <span class="{cand['status'].lower()}">{cand['status']}</span>
                        </div>
                        </div>
                        """, unsafe_allow_html=True)

                        st.markdown("#### 📊 Matching Analysis")
                        st.markdown(cand["reason"])

                        col_vm1, col_vm2 = st.columns([1, 1])
                        with col_vm1:
                            if st.button("👁️ View Original Resume", key=f"view_orig_{cand['mongo_id']}"):
                                st.session_state[view_mode_key] = 'original'
                        with col_vm2:
                            if st.button("🔄 Retailor Resume", key=f"retailor_bulk_{cand['mongo_id']}"):
                                with st.spinner("Retailoring resume..."):
                                    safe_resume = convert_objectid_to_str(cand["resume"])
                                    matcher = st.session_state.get('matcher')
                                    if matcher:
                                        new_res = matcher.resume_retailor.retailor_resume(
                                            safe_resume,
                                            st.session_state.extracted_keywords,
                                            job_description
                                        )
                                        if new_res:
                                            st.success("Resume retailored successfully!")
                                            st.session_state[resume_key] = new_res
                                            st.session_state[f'pdf_ready_{cand["mongo_id"]}'] = False
                                            st.session_state[view_mode_key] = 'retailored'
                                    else:
                                        st.error("Error: Job matcher not initialized. Please try searching again.")

                        if st.session_state[view_mode_key] == 'original':
                            st.markdown("---")
                            st.markdown("### 📄 Original Resume (Read-Only)")
                            render_formatted_resume(cand["resume"])

                        elif st.session_state[view_mode_key] == 'retailored':
                            # --- Paste your entire existing editable UI code for the retailored resume here ---
                            # This includes all the editable fields, AgGrid tables, PDF/Word generation, etc.
                            # For example:
                            resume_data.setdefault("education", [])
                            resume_data.setdefault("certifications", [])
                            resume_data.setdefault("projects", [])
                            resume_data.setdefault("skills", [])
                            resume_data.setdefault("name", "")
                            resume_data.setdefault("title", "")
                            resume_data.setdefault("summary", "")

                            colA, colB = st.columns([1, 2])
                            with colA:
                                resume_data["name"] = st.text_input("Name", value=resume_data.get("name", ""), key=f"name_bulk_{cand['mongo_id']}")
                                resume_data["title"] = st.text_input("Title", value=resume_data.get("title", ""), key=f"title_bulk_{cand['mongo_id']}")
                            with colB:
                                resume_data["summary"] = st.text_area("Summary", value=resume_data.get("summary", ""), height=120, key=f"summary_bulk_{cand['mongo_id']}")
                            st.markdown("---")
            # ... (continue with the rest of your editable UI code for education, certifications, projects, skills, PDF/Word, etc.) ...

                            # Container to hold PDF preview
                            pdf_display_container = st.empty()
                            st.subheader("Edit Resume Fields")

                            # --- Education Section ---
                            st.markdown('<div class="section-header">🎓 Education</div>', unsafe_allow_html=True)
                            st.markdown('<div class="info-box">💡 <strong>Tip:</strong> Click on any cell to edit. Use checkboxes to select rows for deletion. Add new entries with the button below.</div>', unsafe_allow_html=True)
                            edu_list = resume_data["education"]
                            def normalize_edu(entry):
                                entry.setdefault("institution", "")
                                entry.setdefault("degree", "")
                                entry.setdefault("year", "")
                                return entry
                            edu_list = [normalize_edu(e) for e in edu_list]
                            if len(edu_list) == 0:
                                edu_df = pd.DataFrame(columns=["Degree", "Institution", "Year"])
                            else:
                                edu_df = pd.DataFrame(edu_list)
                                edu_df = edu_df.rename(columns={"institution": "Institution", "degree": "Degree", "year": "Year"})
                            gb_edu = GridOptionsBuilder.from_dataframe(edu_df)
                            gb_edu.configure_selection('multiple', use_checkbox=True)
                            for col in edu_df.columns:
                                gb_edu.configure_column(
                                    col, 
                                    editable=True, 
                                    cellStyle={"whiteSpace": "normal", "wordBreak": "break-word"}, 
                                    cellEditor="agTextAreaCellEditor",
                                    cellEditorParams={"maxLength": 500, "rows": 3, "cols": 50},
                                    tooltipField=col, 
                                    resizable=True, 
                                    flex=1
                                )
                            gb_edu.configure_grid_options(rowDragManaged=True, rowHeight=100)
                            gridOptions_edu = gb_edu.build()
                            # Initialize the nested dict structure if needed
                            if cand['mongo_id'] not in st.session_state.aggrid_key_suffixes_bulk:
                                st.session_state.aggrid_key_suffixes_bulk[cand['mongo_id']] = {}
                            edu_key_suffix = st.session_state.aggrid_key_suffixes_bulk.get(cand['mongo_id'], {}).get('edu', 0)
                            edu_response = AgGrid(
                                edu_df,
                                gridOptions=gridOptions_edu,
                                update_mode=GridUpdateMode.MODEL_CHANGED,
                                allow_unsafe_jscode=True,
                                theme="streamlit",
                                height=300,
                                fit_columns_on_grid_load=True,
                                key=f"aggrid_edu_bulk_{cand['mongo_id']}_{edu_key_suffix}"
                            )
                            # Sync current AG-Grid data with session state immediately
                            current_edu_data = pd.DataFrame(edu_response["data"])
                            # Check for deleted rows
                            selected_rows = edu_response['selected_rows']
                            if selected_rows is not None and not selected_rows.empty:
                                current_df = pd.DataFrame(edu_response["data"])
                                indices_to_drop = selected_rows.index.tolist()
                                remaining_df = current_df.drop(indices_to_drop)
                                # Convert back to session state format
                                new_education = []
                                for _, row in remaining_df.iterrows():
                                    institution = str(row['Institution']) if 'Institution' in row else ""
                                    degree = str(row['Degree']) if 'Degree' in row else ""
                                    year = str(row['Year']) if 'Year' in row else ""
                                    if institution.strip() or degree.strip() or year.strip():
                                        new_education.append({"institution": institution, "degree": degree, "year": year})
                                resume_data["education"] = new_education
                                st.session_state[f'resume_data_{cand["mongo_id"]}'] = copy.deepcopy(resume_data)
                                # Initialize the nested dict structure if needed
                                if cand['mongo_id'] not in st.session_state.aggrid_key_suffixes_bulk:
                                    st.session_state.aggrid_key_suffixes_bulk[cand['mongo_id']] = {}
                                if 'edu' not in st.session_state.aggrid_key_suffixes_bulk[cand['mongo_id']]:
                                    st.session_state.aggrid_key_suffixes_bulk[cand['mongo_id']]['edu'] = 0
                                st.session_state.aggrid_key_suffixes_bulk[cand['mongo_id']]['edu'] += 1
                                st.success(f"Deleted {len(indices_to_drop)} education entries.")
                                st.rerun()
                            else: # If no rows are deleted, sync any edits
                                current_education = []
                                for _, row in current_edu_data.iterrows():
                                    institution = str(row['Institution']) if 'Institution' in row else ""
                                    degree = str(row['Degree']) if 'Degree' in row else ""
                                    year = str(row['Year']) if 'Year' in row else ""
                                    if institution.strip() or degree.strip() or year.strip():
                                        current_education.append({"institution": institution, "degree": degree, "year": year})
                                resume_data["education"] = current_education
                                st.session_state[f'resume_data_{cand["mongo_id"]}'] = copy.deepcopy(resume_data)

                            if st.button("➕ Add Education", key=f"add_edu_bulk_{cand['mongo_id']}", type="secondary"):
                                resume_data["education"].append({"institution": "", "degree": "", "year": ""})
                                st.session_state[f'resume_data_{cand["mongo_id"]}'] = copy.deepcopy(resume_data)
                                # Increment key suffix to force AgGrid refresh
                                if cand['mongo_id'] not in st.session_state.aggrid_key_suffixes_bulk:
                                    st.session_state.aggrid_key_suffixes_bulk[cand['mongo_id']] = {}
                                if 'edu' not in st.session_state.aggrid_key_suffixes_bulk[cand['mongo_id']]:
                                    st.session_state.aggrid_key_suffixes_bulk[cand['mongo_id']]['edu'] = 0
                                st.session_state.aggrid_key_suffixes_bulk[cand['mongo_id']]['edu'] += 1
                                st.markdown('<div class="success-message">✅ Added new education entry! Click to edit and fill in details.</div>', unsafe_allow_html=True)
                                st.rerun()
                            st.markdown("---")

                            # --- Certifications Section ---
                            st.markdown('<div class="section-header">🏅 Certifications</div>', unsafe_allow_html=True)
                            st.markdown('<div class="info-box">💡 <strong>Tip:</strong> Add your professional certifications and credentials. Links are optional but helpful for verification.</div>', unsafe_allow_html=True)
                            cert_list = resume_data["certifications"]
                            def normalize_cert(entry):
                                if not isinstance(entry, dict):
                                    entry = {"title": str(entry)}
                                entry.setdefault("title", "")
                                entry.setdefault("issuer", "")
                                entry.setdefault("year", "")
                                entry.setdefault("link", "")
                                return entry
                            certs_fixed = [normalize_cert(c) for c in cert_list]
                            if len(certs_fixed) == 0:
                                cert_df = pd.DataFrame(columns=["Title", "Issuer", "Year", "link"])
                            else:
                                cert_df = pd.DataFrame(certs_fixed)
                                cert_df = cert_df.rename(columns={"title": "Title", "issuer": "Issuer", "year": "Year", "link": "link"})
                            gb_cert = GridOptionsBuilder.from_dataframe(cert_df)
                            gb_cert.configure_selection('multiple', use_checkbox=True)
                            for col in cert_df.columns:
                                gb_cert.configure_column(
                                    col, 
                                    editable=True, 
                                    cellStyle={"whiteSpace": "normal", "wordBreak": "break-word"}, 
                                    cellEditor="agTextAreaCellEditor",
                                    cellEditorParams={"maxLength": 500, "rows": 3, "cols": 50},
                                    tooltipField=col, 
                                    resizable=True, 
                                    flex=1
                                )
                            gb_cert.configure_grid_options(rowDragManaged=True, rowHeight=100)
                            gridOptions_cert = gb_cert.build()
                            # Initialize the nested dict structure if needed
                            if cand['mongo_id'] not in st.session_state.aggrid_key_suffixes_bulk:
                                st.session_state.aggrid_key_suffixes_bulk[cand['mongo_id']] = {}
                            cert_key_suffix = st.session_state.aggrid_key_suffixes_bulk.get(cand['mongo_id'], {}).get('cert', 0)
                            cert_response = AgGrid(
                                cert_df,
                                gridOptions=gridOptions_cert,
                                update_mode=GridUpdateMode.MODEL_CHANGED,
                                allow_unsafe_jscode=True,
                                theme="streamlit",
                                height=300,
                                fit_columns_on_grid_load=True,
                                key=f"aggrid_cert_bulk_{cand['mongo_id']}_{cert_key_suffix}"
                            )
                            # Sync current AG-Grid data with session state immediately
                            current_cert_data = pd.DataFrame(cert_response["data"])
                            # Check for deleted rows
                            selected_rows_cert = cert_response['selected_rows']
                            if selected_rows_cert is not None and not selected_rows_cert.empty:
                                current_df = pd.DataFrame(cert_response["data"])
                                indices_to_drop = selected_rows_cert.index.tolist()
                                remaining_df = current_df.drop(indices_to_drop)
                                # Convert back to session state format
                                new_certifications = []
                                for _, row in remaining_df.iterrows():
                                    title = str(row['Title']) if 'Title' in row else ""
                                    issuer = str(row['Issuer']) if 'Issuer' in row else ""
                                    year = str(row['Year']) if 'Year' in row else ""
                                    link = str(row['link']) if 'link' in row else ""
                                    if title.strip() or issuer.strip():
                                        new_certifications.append({"title": title, "issuer": issuer, "year": year, "link": link})
                                resume_data["certifications"] = new_certifications
                                st.session_state[f'resume_data_{cand["mongo_id"]}'] = copy.deepcopy(resume_data)
                                # Initialize the nested dict structure if needed
                                if cand['mongo_id'] not in st.session_state.aggrid_key_suffixes_bulk:
                                    st.session_state.aggrid_key_suffixes_bulk[cand['mongo_id']] = {}
                                if 'cert' not in st.session_state.aggrid_key_suffixes_bulk[cand['mongo_id']]:
                                    st.session_state.aggrid_key_suffixes_bulk[cand['mongo_id']]['cert'] = 0
                                st.session_state.aggrid_key_suffixes_bulk[cand['mongo_id']]['cert'] += 1
                                st.success("Deleted selected certifications.")
                                st.rerun()
                            else: # If no rows are deleted, sync any edits
                                current_certifications = []
                                for _, row in current_cert_data.iterrows():
                                    title = str(row['Title']) if 'Title' in row else ""
                                    issuer = str(row['Issuer']) if 'Issuer' in row else ""
                                    year = str(row['Year']) if 'Year' in row else ""
                                    link = str(row['link']) if 'link' in row else ""
                                    if title.strip() or issuer.strip():
                                        current_certifications.append({"title": title, "issuer": issuer, "year": year, "link": link})
                                resume_data["certifications"] = current_certifications
                                st.session_state[f'resume_data_{cand["mongo_id"]}'] = copy.deepcopy(resume_data)
                            
                            if st.button("➕ Add Certification", key=f"add_cert_bulk_{cand['mongo_id']}"):
                                resume_data["certifications"].append({"title": "", "issuer": "", "year": "", "link": ""})
                                st.session_state[f'resume_data_{cand["mongo_id"]}'] = copy.deepcopy(resume_data)
                                # Increment key suffix to force AgGrid refresh
                                if cand['mongo_id'] not in st.session_state.aggrid_key_suffixes_bulk:
                                    st.session_state.aggrid_key_suffixes_bulk[cand['mongo_id']] = {}
                                if 'cert' not in st.session_state.aggrid_key_suffixes_bulk[cand['mongo_id']]:
                                    st.session_state.aggrid_key_suffixes_bulk[cand['mongo_id']]['cert'] = 0
                                st.session_state.aggrid_key_suffixes_bulk[cand['mongo_id']]['cert'] += 1
                                st.success("Added new certification entry.")
                                st.rerun()
                            st.markdown("---")

                            # --- Projects Section ---
                            st.markdown('<div class="section-header">💼 Projects</div>', unsafe_allow_html=True)
                            st.markdown('<div class="info-box">💡 <strong>Tip:</strong> Project descriptions are automatically optimized for the job. You can edit them to better match your experience.</div>', unsafe_allow_html=True)
                            proj_list = resume_data["projects"]
                            def normalize_proj(entry):
                                entry.setdefault("title", "")
                                entry.setdefault("description", "")
                                entry.setdefault("link", "")
                                return entry
                            proj_list = [normalize_proj(p) for p in proj_list]
                            # Don't modify the description - keep it as is from retailoring
                            if len(proj_list) == 0:
                                proj_df = pd.DataFrame(columns=["Title", "Description", "link"])
                            else:
                                proj_df = pd.DataFrame(proj_list)
                                proj_df = proj_df.rename(columns={"title": "Title", "description": "Description", "link": "link"})
                            gb_proj = GridOptionsBuilder.from_dataframe(proj_df)
                            gb_proj.configure_selection('multiple', use_checkbox=True)
                            for col in proj_df.columns:
                                if col == "Description":
                                    gb_proj.configure_column(
                                        col, 
                                        editable=True, 
                                        cellStyle={"whiteSpace": "pre-line", "wordBreak": "break-word"}, 
                                        cellEditor="agLargeTextCellEditor",
                                        cellEditorParams={"maxLength": 2000, "rows": 8, "cols": 80},
                                        tooltipField=col, 
                                        resizable=True, 
                                        flex=2, 
                                        minWidth=600
                                    )
                                else:
                                    gb_proj.configure_column(
                                        col, 
                                        editable=True, 
                                        cellStyle={"whiteSpace": "normal", "wordBreak": "break-word"}, 
                                        cellEditor="agTextAreaCellEditor",
                                        cellEditorParams={"maxLength": 500, "rows": 2, "cols": 50},
                                        tooltipField=col, 
                                        resizable=True, 
                                        flex=1
                                    )
                            gb_proj.configure_grid_options(rowDragManaged=True, rowHeight=200)
                            gridOptions_proj = gb_proj.build()
                            # Initialize the nested dict structure if needed
                            if cand['mongo_id'] not in st.session_state.aggrid_key_suffixes_bulk:
                                st.session_state.aggrid_key_suffixes_bulk[cand['mongo_id']] = {}
                            proj_key_suffix = st.session_state.aggrid_key_suffixes_bulk.get(cand['mongo_id'], {}).get('proj', 0)
                            proj_response = AgGrid(
                                proj_df,
                                gridOptions=gridOptions_proj,
                                update_mode=GridUpdateMode.MODEL_CHANGED,
                                allow_unsafe_jscode=True,
                                theme="streamlit",
                                height=400,
                                fit_columns_on_grid_load=True,
                                key=f"aggrid_proj_bulk_{cand['mongo_id']}_{proj_key_suffix}"
                            )
                            # Sync current AG-Grid data with session state immediately
                            current_proj_data = pd.DataFrame(proj_response["data"])
                            # Check for deleted rows
                            selected_rows_proj = proj_response['selected_rows']
                            if selected_rows_proj is not None and not selected_rows_proj.empty:
                                current_df = pd.DataFrame(proj_response["data"])
                                indices_to_drop = selected_rows_proj.index.tolist()
                                remaining_df = current_df.drop(indices_to_drop)
                                # Convert back to session state format
                                new_projects = []
                                for _, row in remaining_df.iterrows():
                                    title = str(row['Title']) if 'Title' in row else ""
                                    description = str(row['Description']) if 'Description' in row else ""
                                    link = str(row['link']) if 'link' in row else ""
                                    if title.strip() or description.strip():
                                        new_projects.append({"title": title, "description": description, "link": link})
                                resume_data["projects"] = new_projects
                                st.session_state[f'resume_data_{cand["mongo_id"]}'] = copy.deepcopy(resume_data)
                                # Initialize the nested dict structure if needed
                                if cand['mongo_id'] not in st.session_state.aggrid_key_suffixes_bulk:
                                    st.session_state.aggrid_key_suffixes_bulk[cand['mongo_id']] = {}
                                if 'proj' not in st.session_state.aggrid_key_suffixes_bulk[cand['mongo_id']]:
                                    st.session_state.aggrid_key_suffixes_bulk[cand['mongo_id']]['proj'] = 0
                                st.session_state.aggrid_key_suffixes_bulk[cand['mongo_id']]['proj'] += 1
                                st.success("Deleted selected projects.")
                                st.rerun()
                            else: # If no rows are deleted, sync any edits
                                current_projects = []
                                for _, row in current_proj_data.iterrows():
                                    title = str(row['Title']) if 'Title' in row else ""
                                    description = str(row['Description']) if 'Description' in row else ""
                                    link = str(row['link']) if 'link' in row else ""
                                    if title.strip() or description.strip():
                                        current_projects.append({"title": title, "description": description, "link": link})
                                resume_data["projects"] = current_projects
                                st.session_state[f'resume_data_{cand["mongo_id"]}'] = copy.deepcopy(resume_data)

                            if st.button("➕ Add Project", key=f"add_proj_bulk_{cand['mongo_id']}"):
                                resume_data["projects"].append({"title": "", "description": "", "link": ""})
                                st.session_state[f'resume_data_{cand["mongo_id"]}'] = copy.deepcopy(resume_data)
                                # Increment key suffix to force AgGrid refresh
                                if cand['mongo_id'] not in st.session_state.aggrid_key_suffixes_bulk:
                                    st.session_state.aggrid_key_suffixes_bulk[cand['mongo_id']] = {}
                                if 'proj' not in st.session_state.aggrid_key_suffixes_bulk[cand['mongo_id']]:
                                    st.session_state.aggrid_key_suffixes_bulk[cand['mongo_id']]['proj'] = 0
                                st.session_state.aggrid_key_suffixes_bulk[cand['mongo_id']]['proj'] += 1
                                st.success("Added new project entry.")
                                st.rerun()
                            st.markdown("---")

                            # --- Skills Section ---
                            st.markdown('<div class="section-header">🛠️ Skills</div>', unsafe_allow_html=True)
                            st.markdown('<div class="info-box">💡 <strong>Tip:</strong> Skills are balanced between your original expertise and job requirements. Add or remove as needed.</div>', unsafe_allow_html=True)
                            skill_list = resume_data["skills"]
                            if len(skill_list) == 0:
                                skill_df = pd.DataFrame(columns=["Skill"])
                            else:
                                skill_df = pd.DataFrame({"Skill": [str(s) if not isinstance(s, str) else s for s in skill_list]})
                            gb_skill = GridOptionsBuilder.from_dataframe(skill_df)
                            gb_skill.configure_selection('multiple', use_checkbox=True)
                            for col in skill_df.columns:
                                gb_skill.configure_column(
                                    col, 
                                    editable=True, 
                                    cellEditor="agTextCellEditor",
                                    cellEditorParams={"maxLength": 100},
                                    resizable=True, 
                                    flex=1
                                )
                            gb_skill.configure_grid_options(rowDragManaged=True, rowHeight=25)
                            gridOptions_skill = gb_skill.build()
                            # Initialize the nested dict structure if needed
                            if cand['mongo_id'] not in st.session_state.aggrid_key_suffixes_bulk:
                                st.session_state.aggrid_key_suffixes_bulk[cand['mongo_id']] = {}
                            skill_key_suffix = st.session_state.aggrid_key_suffixes_bulk.get(cand['mongo_id'], {}).get('skill', 0)
                            skill_response = AgGrid(
                                skill_df,
                                gridOptions=gridOptions_skill,
                                update_mode=GridUpdateMode.MODEL_CHANGED,
                                allow_unsafe_jscode=True,
                                theme="streamlit",
                                height=300,
                                fit_columns_on_grid_load=True,
                                key=f"aggrid_skill_bulk_{cand['mongo_id']}_{skill_key_suffix}"
                            )
                            # Sync current AG-Grid data with session state immediately
                            current_skill_data = pd.DataFrame(skill_response["data"])
                            # Check for deleted rows
                            selected_rows_skill = skill_response['selected_rows']
                            if selected_rows_skill is not None and not selected_rows_skill.empty:
                                current_df = pd.DataFrame(skill_response["data"])
                                indices_to_drop = selected_rows_skill.index.tolist()
                                remaining_df = current_df.drop(indices_to_drop)
                                # Convert back to session state format
                                new_skills = [str(row['Skill']).strip() for _, row in remaining_df.iterrows() if 'Skill' in row and str(row['Skill']).strip()]
                                resume_data["skills"] = new_skills
                                st.session_state[f'resume_data_{cand["mongo_id"]}'] = copy.deepcopy(resume_data)
                                # Initialize the nested dict structure if needed
                                if cand['mongo_id'] not in st.session_state.aggrid_key_suffixes_bulk:
                                    st.session_state.aggrid_key_suffixes_bulk[cand['mongo_id']] = {}
                                if 'skill' not in st.session_state.aggrid_key_suffixes_bulk[cand['mongo_id']]:
                                    st.session_state.aggrid_key_suffixes_bulk[cand['mongo_id']]['skill'] = 0
                                st.session_state.aggrid_key_suffixes_bulk[cand['mongo_id']]['skill'] += 1
                                st.success("Deleted selected skills.")
                                st.rerun()
                            else: # If no rows are deleted, sync any edits
                                current_skills = [str(row['Skill']).strip() for _, row in current_skill_data.iterrows() if 'Skill' in row and str(row['Skill']).strip()]
                                resume_data["skills"] = current_skills
                                st.session_state[f'resume_data_{cand["mongo_id"]}'] = copy.deepcopy(resume_data)

                            if st.button("➕ Add Skill", key=f"add_skill_bulk_{cand['mongo_id']}"):
                                resume_data["skills"].append("")
                                st.session_state[f'resume_data_{cand["mongo_id"]}'] = copy.deepcopy(resume_data)
                                # Increment key suffix to force AgGrid refresh
                                if cand['mongo_id'] not in st.session_state.aggrid_key_suffixes_bulk:
                                    st.session_state.aggrid_key_suffixes_bulk[cand['mongo_id']] = {}
                                if 'skill' not in st.session_state.aggrid_key_suffixes_bulk[cand['mongo_id']]:
                                    st.session_state.aggrid_key_suffixes_bulk[cand['mongo_id']]['skill'] = 0
                                st.session_state.aggrid_key_suffixes_bulk[cand['mongo_id']]['skill'] += 1
                                st.success("Added new skill entry.")
                                st.rerun()
                            st.markdown("---")

                            # Generate PDF button
                            if st.button("🔄 Update and Generate New PDF", key=f"update_pdf_bulk_{cand['mongo_id']}"):
                                # Create a fresh copy of data to sync
                                synced_data = copy.deepcopy(st.session_state[f'resume_data_{cand["mongo_id"]}'])

                                # Sync simple text inputs
                                synced_data["name"] = resume_data["name"]
                                synced_data["title"] = resume_data["title"]
                                synced_data["summary"] = resume_data["summary"]

                                # Sync Education from AgGrid
                                edu_df = pd.DataFrame(edu_response["data"])
                                synced_education = []
                                for _, row in edu_df.iterrows():
                                    institution = str(row['Institution']) if 'Institution' in row else ""
                                    degree = str(row['Degree']) if 'Degree' in row else ""
                                    year = str(row['Year']) if 'Year' in row else ""
                                    if institution.strip() or degree.strip() or year.strip():
                                        synced_education.append({"institution": institution, "degree": degree, "year": year})
                                synced_data["education"] = synced_education
                                
                                # Sync Certifications from AgGrid
                                cert_df = pd.DataFrame(cert_response["data"])
                                synced_certifications = []
                                for _, row in cert_df.iterrows():
                                    title = str(row['Title']) if 'Title' in row else ""
                                    issuer = str(row['Issuer']) if 'Issuer' in row else ""
                                    year = str(row['Year']) if 'Year' in row else ""
                                    link = str(row['link']) if 'link' in row else ""
                                    if title.strip() or issuer.strip():
                                        synced_certifications.append({"title": title, "issuer": issuer, "year": year, "link": link})
                                synced_data["certifications"] = synced_certifications
                                
                                # Sync Projects from AgGrid
                                proj_df = pd.DataFrame(proj_response["data"])
                                synced_projects = []
                                for _, row in proj_df.iterrows():
                                    title = str(row['Title']) if 'Title' in row else ""
                                    description = str(row['Description']) if 'Description' in row else ""
                                    link = str(row['link']) if 'link' in row else ""
                                    if title.strip() or description.strip():
                                        synced_projects.append({"title": title, "description": description, "link": link})
                                synced_data["projects"] = synced_projects

                                # Sync Skills from AgGrid
                                skill_df = pd.DataFrame(skill_response["data"])
                                synced_skills = [str(row['Skill']).strip() for _, row in skill_df.iterrows() if 'Skill' in row and str(row['Skill']).strip()]
                                synced_data["skills"] = synced_skills
                                
                                # Update session state with the fully synchronized data
                                st.session_state[f'resume_data_{cand["mongo_id"]}'] = copy.deepcopy(synced_data)
                                st.session_state[f'pdf_ready_{cand["mongo_id"]}'] = True

                                with st.spinner("Generating PDF..."):
                                    keywords = st.session_state.get('extracted_keywords', None)
                                    pdf_file, html_out = PDFUtils.generate_pdf(synced_data, keywords=keywords)
                                    pdf_b64 = PDFUtils.get_base64_pdf(pdf_file)
                                    st.session_state[f'generated_pdf_{cand["mongo_id"]}'] = pdf_file
                                    st.session_state[f'generated_pdf_b64_{cand["mongo_id"]}'] = pdf_b64
                                    st.success("PDF generated successfully!")
                                    st.rerun()

                            # --- PDF Preview Section for bulk candidates (Outside button click) ---
                            if st.session_state.get(f'pdf_ready_{cand["mongo_id"]}', False):
                                st.markdown("### 📄 Generated PDF Preview")
                                pdf_b64 = st.session_state[f'generated_pdf_b64_{cand["mongo_id"]}']
                                st.info("If the PDF is not viewable above, your browser may not support embedded PDF viewing.")
                                link_id = f"open_pdf_link_{uuid.uuid4().hex}"
                                components.html(f"""
                                    <a id="{link_id}" style="margin:10px 0;display:inline-block;padding:8px 16px;font-size:16px;border-radius:5px;background:#0068c9;color:white;text-decoration:none;border:none;cursor:pointer;">
                                        🔗 Click here to open the PDF in a new tab
                                    </a>
                                    <script>
                                    const b64Data = "{pdf_b64}";
                                    const byteCharacters = atob(b64Data);
                                    const byteNumbers = new Array(byteCharacters.length);
                                    for (let i = 0; i < byteCharacters.length; i++) {{
                                        byteNumbers[i] = byteCharacters.charCodeAt(i);
                                    }}
                                    const byteArray = new Uint8Array(byteNumbers);
                                    const blob = new Blob([byteArray], {{type: "application/pdf"}});
                                    const blobUrl = URL.createObjectURL(blob);
                                    const link = document.getElementById("{link_id}");
                                    link.href = blobUrl;
                                    link.target = "_blank";
                                    link.rel = "noopener noreferrer";
                                    link.onclick = function() {{
                                        setTimeout(function(){{URL.revokeObjectURL(blobUrl)}}, 10000);
                                    }};
                                    </script>
                                """, height=80)
                                st.download_button(
                                    "📄 Download PDF",
                                    data=st.session_state[f'generated_pdf_{cand["mongo_id"]}'],
                                    file_name=f"{resume_data.get('name', 'resume').replace(' ', '_')}.pdf",
                                    mime="application/pdf",
                                    key=f"download_pdf_bulk_{cand['mongo_id']}"
                                )
                                keywords = st.session_state.get('extracted_keywords', None)
                                word_file = DocxUtils.generate_docx(resume_data, keywords=keywords)
                                st.download_button(
                                    "📝 Download Word",
                                    data=word_file,
                                    file_name=f"{resume_data.get('name', 'resume').replace(' ', '_')}.docx",
                                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                                    key=f"download_word_bulk_{cand['mongo_id']}"
                                )

                                # Add Pitch Summary Generation
                            
                            st.markdown("### 📝 Candidate Pitch Summary")
                            col1, col2 = st.columns([1, 8])
                            with col1:
                                if st.button("✨ Generate Summary", key=f"generate_summary_bulk_{cand['mongo_id']}", use_container_width=True):
                                    with st.spinner("Generating candidate summary..."):
                                        summary_prompt = (
                                            f"You are an expert HR professional. You MUST infer and assign a professional job title for the candidate based on the job description and their experience/skills. Do not leave the title blank. If unsure, use the most relevant title from the job description. Then, write a detailed, information-rich, single-paragraph professional summary (8-10 sentences) to introduce the following candidate to a client for a job opportunity. The summary should be written in third person, using formal and business-appropriate language, and should avoid any informal, overly enthusiastic, or emotional expressions. The summary must be comprehensive and cover the candidate's technical expertise, relevant experience, key achievements, major projects, technologies and frameworks used, leadership, teamwork, impact, and educational background as they pertain to the job description. Be specific about programming languages, frameworks, tools, and platforms the candidate has worked with. Mention any certifications or notable accomplishments. The summary should reflect high ethical standards and professionalism, and should not include any bullet points, excitement, or casual language. Use only facts from the provided information and do not invent or exaggerate. The summary should be suitable for inclusion in a formal client communication and should be at least 8-10 sentences long.\n\nReturn your response as a JSON object with two fields: 'title' and 'summary'.\n\nCandidate Information:\nName: {resume_data.get('name', '')}\nTitle: {resume_data.get('title', '')}\nSummary: {resume_data.get('summary', '')}\nSkills: {', '.join(resume_data.get('skills', []))}\n\nProjects:\n{json.dumps(resume_data.get('projects', []), indent=2)}\n\nEducation:\n{json.dumps(resume_data.get('education', []), indent=2)}\n\nJob Description:\n{job_description}"
                                        )
                                        try:
                                            client = AzureOpenAI(
                                                api_key=st.secrets["azure_openai"]["api_key"],
                                                api_version=st.secrets["azure_openai"]["api_version"],
                                                azure_endpoint=st.secrets["azure_openai"]["endpoint"]
                                            )
                                            response = client.chat.completions.create(
                                                model=st.secrets["azure_openai"]["deployment"],
                                                messages=[
                                                    {"role": "system", "content": "You are an expert HR professional who writes compelling candidate summaries."},
                                                    {"role": "user", "content": summary_prompt}
                                                ],
                                                temperature=0.7,
                                                response_format={"type": "json_object"}
                                            )
                                            result = response.choices[0].message.content.strip()
                                            try:
                                                result_json = json.loads(result)
                                                title = result_json.get("title", "").strip()
                                                if not title:
                                                    title = job_description.split("\n")[0].split("-")[0].split(":")[0].split(".")[0].strip()
                                                    if not title:
                                                        title = "Candidate"
                                                resume_data["title"] = title
                                                st.session_state[f'candidate_summary_bulk_{cand["mongo_id"]}'] = result_json.get("summary", "")
                                            except Exception as e:
                                                st.session_state[f'candidate_summary_bulk_{cand["mongo_id"]}'] = result
                                        except Exception as e:
                                            st.error(f"Error generating summary: {str(e)}")
                                        st.rerun()
                            with col2:
                                summary = st.session_state.get(f"candidate_summary_bulk_{cand['mongo_id']}", "")
                                summary = st.text_area(
                                    "Edit the summary as needed",
                                    value=summary,
                                    height=400,
                                    key=f"summary_edit_bulk_{cand['mongo_id']}"
                                )
                                components.html(f'''
                                    <textarea id="copyText_bulk_{cand['mongo_id']}" style="position:absolute;left:-9999px;">{summary}</textarea>
                                    <button style="margin-top:10px;padding:8px 16px;font-size:16px;border-radius:5px;background:#0068c9;color:white;border:none;cursor:pointer;"
                                            nclick="var copyText = document.getElementById('copyText_bulk_{cand['mongo_id']}'); copyText.style.display='block'; copyText.select(); document.execCommand('copy'); copyText.style.display='none'; alert('Copied!');">
                                        📋 Copy Summary
                                    </button>
                                ''', height=60)

        elif job_description:
            st.info("👆 Click 'Find Matching Candidates' to start.")
        else:
            st.info("👆 Enter a job description to begin matching.")

    with tab2:
        st.markdown("### 👤 Search & Retailor for a Specific Candidate")
        st.markdown("Find a specific candidate and retailor their resume for a particular job.")
        
        col1, col2 = st.columns([1, 3])
        with col1:
            search_field = st.selectbox("Search by", ["Name", "Employee ID"], index=1)
        with col2:
            label = f"Enter candidate {search_field}" if search_field == "Name" else "Enter candidate Employee ID"
            search_value = st.text_input(label)

        # Always show job description input and search button
        job_description_single = st.text_area(
            "Enter Job Description for This Candidate", 
            height=150, 
            key="single_jd",
            placeholder="Paste the job description here."
        )

        if st.button("Find & Retailor for This Candidate", type="primary", key="single_search"):
            if not search_value:
                st.warning("Please enter both candidate info.")
            else:
                from db_manager import ResumeDBManager
                db_manager = ResumeDBManager()
                # Build the query based on the selected search field
                if search_field == "Name":
                    query = {"name": {"$regex": f"^{search_value}$", "$options": "i"}}
                elif search_field == "Employee ID":
                    query = {"employee_id": {"$regex": f"^{search_value}$", "$options": "i"}}
                else:
                    query = {search_field.lower(): {"$regex": f"^{search_value}$", "$options": "i"}}
                results = db_manager.find(query)
                if not results:
                    st.error("No candidate found with that info.")
                else:
                    # If multiple, let user pick
                    if len(results) > 1:
                        st.warning("Multiple candidates found. Please select the correct one.")
                        options = [
                            f"{c.get('name', 'Unknown')} | {c.get('email', 'No email')} | {c.get('phone', 'No phone')}"
                            for c in results
                        ]
                        selected = st.selectbox("Select Candidate", options)
                        idx = options.index(selected)
                        candidate = results[idx]
                    else:
                        candidate = results[0]
                    
                    st.success(f"Found candidate: {candidate.get('name', 'Unknown')}")
                    analyzer = JobDescriptionAnalyzer()
                    keywords = analyzer.extract_keywords(job_description_single)
                    # Store keywords in session state for PDF generation
                    st.session_state.extracted_keywords = keywords["keywords"]
                    matcher = JobMatcher()
                    
                    with st.spinner("🔄 Retailoring resume..."):
                        retailored = matcher.resume_retailor.retailor_resume(
                            convert_objectid_to_str(candidate),
                            keywords["keywords"],
                            job_description_single
                        )
                    
                    if retailored:
                        # Initialize session state for resume data with all required fields
                        st.session_state.resume_data = retailored
                        st.session_state.resume_data.setdefault("education", [])
                        st.session_state.resume_data.setdefault("projects", [])
                        st.session_state.resume_data.setdefault("skills", [])
                        st.session_state.resume_data.setdefault("certifications", [])
                        st.session_state.resume_data.setdefault("name", "")
                        st.session_state.resume_data.setdefault("title", "")
                        st.session_state.resume_data.setdefault("summary", "")
                        st.session_state.pdf_ready_single = False

        # Only initialize expander_open_single if not present
        if 'expander_open_single' not in st.session_state:
            st.session_state['expander_open_single'] = True
        with st.expander("👤 Candidate Details", expanded=st.session_state['expander_open_single']):
            resume_data = st.session_state.resume_data
            if resume_data is not None:
                # Basic Info Section
                colA, colB = st.columns([1, 2])
                with colA:
                    resume_data["name"] = st.text_input("Name", value=resume_data.get("name", ""))
                    resume_data["title"] = st.text_input("Title", value=resume_data.get("title", ""))
                with colB:
                    resume_data["summary"] = st.text_area("Summary", value=resume_data.get("summary", ""), height=120)

                st.markdown("---")

                # --- Education Section ---
                st.markdown('<div class="section-header">🎓 Education</div>', unsafe_allow_html=True)
                st.markdown('<div class="info-box">💡 <strong>Tip:</strong> Click on any cell to edit. Use checkboxes to select rows for deletion. Add new entries with the button below.</div>', unsafe_allow_html=True)
                edu_list = resume_data["education"]
                def normalize_edu(entry):
                    entry.setdefault("institution", "")
                    entry.setdefault("degree", "")
                    entry.setdefault("year", "")
                    return entry
                edu_list = [normalize_edu(e) for e in edu_list]
                if len(edu_list) == 0:
                    edu_df = pd.DataFrame(columns=["Degree", "Institution", "Year"])
                else:
                    edu_df = pd.DataFrame(edu_list)
                    edu_df = edu_df.rename(columns={"institution": "Institution", "degree": "Degree", "year": "Year"})
                gb_edu = GridOptionsBuilder.from_dataframe(edu_df)
                gb_edu.configure_selection('multiple', use_checkbox=True)
                for col in edu_df.columns:
                    gb_edu.configure_column(
                        col, 
                        editable=True, 
                        cellStyle={"whiteSpace": "normal", "wordBreak": "break-word"}, 
                        cellEditor="agTextAreaCellEditor",
                        cellEditorParams={"maxLength": 500, "rows": 3, "cols": 50},
                        tooltipField=col, 
                        resizable=True, 
                        flex=1
                    )
                gb_edu.configure_grid_options(rowDragManaged=True, rowHeight=100)
                gridOptions_edu = gb_edu.build()
                edu_key_suffix = st.session_state.get('aggrid_edu_single_key_suffix', 0)
                edu_response = AgGrid(
                    edu_df,
                    gridOptions=gridOptions_edu,
                    update_mode=GridUpdateMode.MODEL_CHANGED,
                    allow_unsafe_jscode=True,
                    theme="streamlit",
                    height=300,
                    fit_columns_on_grid_load=True,
                    key=f"aggrid_edu_single_{edu_key_suffix}"
                )
                # Get current data from AG-Grid and sync with session state immediately
                current_edu_data = pd.DataFrame(edu_response["data"])
                # Check for deleted rows
                selected_rows = edu_response['selected_rows']
                if selected_rows is not None and not selected_rows.empty:
                    current_df = pd.DataFrame(edu_response["data"])
                    indices_to_drop = selected_rows.index.tolist()
                    remaining_df = current_df.drop(indices_to_drop)
                    
                    # Convert back to session state format
                    new_education = []
                    for _, row in remaining_df.iterrows():
                        institution = str(row['Institution']) if 'Institution' in row else ""
                        degree = str(row['Degree']) if 'Degree' in row else ""
                        year = str(row['Year']) if 'Year' in row else ""
                        if institution.strip() or degree.strip() or year.strip():
                            new_education.append({
                                "institution": institution,
                                "degree": degree,
                                "year": year
                            })
                    resume_data["education"] = new_education
                    st.session_state.resume_data = copy.deepcopy(resume_data)
                    st.session_state['aggrid_edu_single_key_suffix'] = edu_key_suffix + 1
                    st.success(f"Deleted {len(indices_to_drop)} education entries.")
                    st.rerun()
                else: # If no rows are deleted, sync any edits
                    current_education = []
                    for _, row in current_edu_data.iterrows():
                        institution = str(row['Institution']) if 'Institution' in row else ""
                        degree = str(row['Degree']) if 'Degree' in row else ""
                        year = str(row['Year']) if 'Year' in row else ""
                        if institution.strip() or degree.strip() or year.strip():
                            current_education.append({
                                "institution": institution,
                                "degree": degree,
                                "year": year
                            })
                    resume_data["education"] = current_education
                    st.session_state.resume_data = copy.deepcopy(resume_data)
                
                if st.button("➕ Add Education", key="add_edu_single", type="secondary"):
                    resume_data["education"].append({"institution": "", "degree": "", "year": ""})
                    st.session_state.resume_data = copy.deepcopy(resume_data)
                    # Increment key suffix to force AgGrid refresh
                    st.session_state['aggrid_edu_single_key_suffix'] = st.session_state.get('aggrid_edu_single_key_suffix', 0) + 1
                    st.markdown('<div class="success-message">✅ Added new education entry! Click to edit and fill in details.</div>', unsafe_allow_html=True)
                    st.rerun()
                st.markdown("---")

                # --- Certifications Section ---
                st.markdown('<div class="section-header">🏅 Certifications</div>', unsafe_allow_html=True)
                st.markdown('<div class="info-box">💡 <strong>Tip:</strong> Add your professional certifications and credentials. Links are optional but helpful for verification.</div>', unsafe_allow_html=True)
                cert_list = resume_data["certifications"]
                def normalize_cert(entry):
                    if not isinstance(entry, dict):
                        entry = {"title": str(entry)}
                    entry.setdefault("title", "")
                    entry.setdefault("issuer", "")
                    entry.setdefault("year", "")
                    entry.setdefault("link", "")
                    return entry
                certs_fixed = [normalize_cert(c) for c in cert_list]
                if len(certs_fixed) == 0:
                    cert_df = pd.DataFrame(columns=["Title", "Issuer", "Year", "link"])
                else:
                    cert_df = pd.DataFrame(certs_fixed)
                    cert_df = cert_df.rename(columns={"title": "Title", "issuer": "Issuer", "year": "Year", "link": "link"})
                gb_cert = GridOptionsBuilder.from_dataframe(cert_df)
                gb_cert.configure_selection('multiple', use_checkbox=True)
                for col in cert_df.columns:
                    gb_cert.configure_column(
                        col, 
                        editable=True, 
                        cellStyle={"whiteSpace": "normal", "wordBreak": "break-word"}, 
                        cellEditor="agTextAreaCellEditor",
                        cellEditorParams={"maxLength": 500, "rows": 3, "cols": 50},
                        tooltipField=col, 
                        resizable=True, 
                        flex=1
                    )
                gb_cert.configure_grid_options(rowDragManaged=True, rowHeight=100)
                gridOptions_cert = gb_cert.build()
                cert_key_suffix = st.session_state.get('aggrid_cert_single_key_suffix', 0)
                cert_response = AgGrid(
                    cert_df,
                    gridOptions=gridOptions_cert,
                    update_mode=GridUpdateMode.MODEL_CHANGED,
                    allow_unsafe_jscode=True,
                    theme="streamlit",
                    height=300,
                    fit_columns_on_grid_load=True,
                    key=f"aggrid_cert_single_{cert_key_suffix}"
                )
                # Sync current AG-Grid data with session state
                current_cert_data = pd.DataFrame(cert_response["data"])
                # Check for deleted rows
                selected_rows_cert = cert_response['selected_rows']
                if selected_rows_cert is not None and not selected_rows_cert.empty:
                    current_df = pd.DataFrame(cert_response["data"])
                    indices_to_drop = selected_rows_cert.index.tolist()
                    remaining_df = current_df.drop(indices_to_drop)
                    # Convert back to session state format
                    new_certifications = []
                    for _, row in remaining_df.iterrows():
                        title = str(row['Title']) if 'Title' in row else ""
                        issuer = str(row['Issuer']) if 'Issuer' in row else ""
                        year = str(row['Year']) if 'Year' in row else ""
                        link = str(row['link']) if 'link' in row else ""
                        if title.strip() or issuer.strip():
                            new_certifications.append({
                                "title": title,
                                "issuer": issuer,
                                "year": year,
                                "link": link
                            })
                    resume_data["certifications"] = new_certifications
                    st.session_state.resume_data = copy.deepcopy(resume_data)
                    st.session_state['aggrid_cert_single_key_suffix'] = cert_key_suffix + 1
                    st.success("Deleted selected certifications.")
                    st.rerun()
                else: # If no rows are deleted, sync any edits
                    current_certifications = []
                    for _, row in current_cert_data.iterrows():
                        title = str(row['Title']) if 'Title' in row else ""
                        issuer = str(row['Issuer']) if 'Issuer' in row else ""
                        year = str(row['Year']) if 'Year' in row else ""
                        link = str(row['link']) if 'link' in row else ""
                        if title.strip() or issuer.strip():
                            current_certifications.append({
                                "title": title,
                                "issuer": issuer,
                                "year": year,
                                "link": link
                            })
                    resume_data["certifications"] = current_certifications
                    st.session_state.resume_data = copy.deepcopy(resume_data)
                
                if st.button("➕ Add Certification", key="add_cert_single"):
                    resume_data["certifications"].append({"title": "", "issuer": "", "year": "", "link": ""})
                    st.session_state.resume_data = copy.deepcopy(resume_data)
                    # Increment key suffix to force AgGrid refresh
                    st.session_state['aggrid_cert_single_key_suffix'] = st.session_state.get('aggrid_cert_single_key_suffix', 0) + 1
                    st.success("Added new certification entry.")
                    st.rerun()
                st.markdown("---")

                # --- Projects Section ---
                st.markdown('<div class="section-header">💼 Projects</div>', unsafe_allow_html=True)
                st.markdown('<div class="info-box">💡 <strong>Tip:</strong> Project descriptions are automatically optimized for the job. You can edit them to better match your experience.</div>', unsafe_allow_html=True)
                proj_list = resume_data["projects"]
                def normalize_proj(entry):
                    entry.setdefault("title", "")
                    entry.setdefault("description", "")
                    entry.setdefault("link", "")
                    return entry
                proj_list = [normalize_proj(p) for p in proj_list]
                # Don't modify the description - keep it as is from retailoring
                if len(proj_list) == 0:
                    proj_df = pd.DataFrame(columns=["Title", "Description", "link"])
                else:
                    proj_df = pd.DataFrame(proj_list)
                    proj_df = proj_df.rename(columns={"title": "Title", "description": "Description", "link": "link"})
                gb_proj = GridOptionsBuilder.from_dataframe(proj_df)
                gb_proj.configure_selection('multiple', use_checkbox=True)
                for col in proj_df.columns:
                    if col == "Description":
                        gb_proj.configure_column(
                            col, 
                            editable=True, 
                            cellStyle={"whiteSpace": "pre-line", "wordBreak": "break-word"}, 
                            cellEditor="agLargeTextCellEditor",
                            cellEditorParams={"maxLength": 2000, "rows": 8, "cols": 80},
                            tooltipField=col, 
                            resizable=True, 
                            flex=2, 
                            minWidth=600
                        )
                    else:
                        gb_proj.configure_column(
                            col, 
                            editable=True, 
                            cellStyle={"whiteSpace": "normal", "wordBreak": "break-word"}, 
                            cellEditor="agTextAreaCellEditor",
                            cellEditorParams={"maxLength": 500, "rows": 2, "cols": 50},
                            tooltipField=col, 
                            resizable=True, 
                            flex=1
                        )
                gb_proj.configure_grid_options(rowDragManaged=True, rowHeight=200)
                gridOptions_proj = gb_proj.build()
                proj_key_suffix = st.session_state.get('aggrid_proj_single_key_suffix', 0)
                proj_response = AgGrid(
                    proj_df,
                    gridOptions=gridOptions_proj,
                    update_mode=GridUpdateMode.MODEL_CHANGED,
                    allow_unsafe_jscode=True,
                    theme="streamlit",
                    height=400,
                    fit_columns_on_grid_load=True,
                    key=f"aggrid_proj_single_{proj_key_suffix}"
                )
                # Sync current AG-Grid data with session state
                current_proj_data = pd.DataFrame(proj_response["data"])
                # Check for deleted rows
                selected_rows_proj = proj_response['selected_rows']
                if selected_rows_proj is not None and not selected_rows_proj.empty:
                    current_df = pd.DataFrame(proj_response["data"])
                    indices_to_drop = selected_rows_proj.index.tolist()
                    remaining_df = current_df.drop(indices_to_drop)
                    # Convert back to session state format
                    new_projects = []
                    for _, row in remaining_df.iterrows():
                        title = str(row['Title']) if 'Title' in row else ""
                        description = str(row['Description']) if 'Description' in row else ""
                        link = str(row['link']) if 'link' in row else ""
                        if title.strip() or description.strip():
                            new_projects.append({
                                "title": title,
                                "description": description,
                                "link": link
                            })
                    resume_data["projects"] = new_projects
                    st.session_state.resume_data = copy.deepcopy(resume_data)
                    st.session_state['aggrid_proj_single_key_suffix'] = proj_key_suffix + 1
                    st.success("Deleted selected projects.")
                    st.rerun()
                else: # If no rows are deleted, sync any edits
                    current_projects = []
                    for _, row in current_proj_data.iterrows():
                        title = str(row['Title']) if 'Title' in row else ""
                        description = str(row['Description']) if 'Description' in row else ""
                        link = str(row['link']) if 'link' in row else ""
                        if title.strip() or description.strip():
                            current_projects.append({
                                "title": title,
                                "description": description,
                                "link": link
                            })
                    resume_data["projects"] = current_projects
                    st.session_state.resume_data = copy.deepcopy(resume_data)
                
                if st.button("➕ Add Project", key="add_proj_single"):
                    resume_data["projects"].append({"title": "", "description": "", "link": ""})
                    st.session_state.resume_data = copy.deepcopy(resume_data)
                    # Increment key suffix to force AgGrid refresh
                    st.session_state['aggrid_proj_single_key_suffix'] = st.session_state.get('aggrid_proj_single_key_suffix', 0) + 1
                    st.success("Added new project entry.")
                    st.rerun()
                st.markdown("---")

                # --- Skills Section ---
                st.markdown('<div class="section-header">🛠️ Skills</div>', unsafe_allow_html=True)
                st.markdown('<div class="info-box">💡 <strong>Tip:</strong> Skills are balanced between your original expertise and job requirements. Add or remove as needed.</div>', unsafe_allow_html=True)
                skill_list = resume_data["skills"]
                if len(skill_list) == 0:
                    skill_df = pd.DataFrame(columns=["Skill"])
                else:
                    skill_df = pd.DataFrame({"Skill": [str(s) if not isinstance(s, str) else s for s in skill_list]})
                gb_skill = GridOptionsBuilder.from_dataframe(skill_df)
                gb_skill.configure_selection('multiple', use_checkbox=True)
                for col in skill_df.columns:
                    gb_skill.configure_column(
                        col, 
                        editable=True, 
                        cellEditor="agTextCellEditor",
                        cellEditorParams={"maxLength": 100},
                        resizable=True, 
                        flex=1
                    )
                gb_skill.configure_grid_options(rowDragManaged=True, rowHeight=25)
                gridOptions_skill = gb_skill.build()
                skill_key_suffix = st.session_state.get('aggrid_skill_single_key_suffix', 0)
                skill_response = AgGrid(
                    skill_df,
                    gridOptions=gridOptions_skill,
                    update_mode=GridUpdateMode.MODEL_CHANGED,
                    allow_unsafe_jscode=True,
                    theme="streamlit",
                    height=300,
                    fit_columns_on_grid_load=True,
                    key=f"aggrid_skill_single_{skill_key_suffix}"
                )
                # Sync current AG-Grid data with session state
                current_skill_data = pd.DataFrame(skill_response["data"])
                # Check for deleted rows
                selected_rows_skill = skill_response['selected_rows']
                if selected_rows_skill is not None and not selected_rows_skill.empty:
                    current_df = pd.DataFrame(skill_response["data"])
                    indices_to_drop = selected_rows_skill.index.tolist()
                    remaining_df = current_df.drop(indices_to_drop)
                    # Convert back to session state format
                    new_skills = [str(row['Skill']).strip() for _, row in remaining_df.iterrows() if 'Skill' in row and str(row['Skill']).strip()]
                    resume_data["skills"] = new_skills
                    st.session_state.resume_data = copy.deepcopy(resume_data)
                    st.session_state['aggrid_skill_single_key_suffix'] = skill_key_suffix + 1
                    st.success("Deleted selected skills.")
                    st.rerun()
                else: # If no rows are deleted, sync any edits
                    current_skills = [str(row['Skill']).strip() for _, row in current_skill_data.iterrows() if 'Skill' in row and str(row['Skill']).strip()]
                    resume_data["skills"] = current_skills
                    st.session_state.resume_data = copy.deepcopy(resume_data)
                
                if st.button("➕ Add Skill", key="add_skill_single"):
                    resume_data["skills"].append("")
                    st.session_state.resume_data = copy.deepcopy(resume_data)
                    # Increment key suffix to force AgGrid refresh
                    st.session_state['aggrid_skill_single_key_suffix'] = st.session_state.get('aggrid_skill_single_key_suffix', 0) + 1
                    st.success("Added new skill entry.")
                    st.rerun()
                st.markdown("---")
                

                # Generate PDF button
                if st.button("🔄 Update and Generate New PDF", key="update_pdf_single"):
                    # Create a fresh copy of data to sync
                    synced_data = copy.deepcopy(st.session_state.resume_data)
                    
                    # Sync simple text inputs
                    synced_data["name"] = resume_data["name"]
                    synced_data["title"] = resume_data["title"]
                    synced_data["summary"] = resume_data["summary"]

                    # Sync Education from AgGrid
                    edu_df = pd.DataFrame(edu_response["data"])
                    synced_education = []
                    for _, row in edu_df.iterrows():
                        institution = str(row['Institution']) if 'Institution' in row else ""
                        degree = str(row['Degree']) if 'Degree' in row else ""
                        year = str(row['Year']) if 'Year' in row else ""
                        if institution.strip() or degree.strip() or year.strip():
                            synced_education.append({"institution": institution, "degree": degree, "year": year})
                    synced_data["education"] = synced_education
                    
                    # Sync Certifications from AgGrid
                    cert_df = pd.DataFrame(cert_response["data"])
                    synced_certifications = []
                    for _, row in cert_df.iterrows():
                        title = str(row['Title']) if 'Title' in row else ""
                        issuer = str(row['Issuer']) if 'Issuer' in row else ""
                        year = str(row['Year']) if 'Year' in row else ""
                        link = str(row['link']) if 'link' in row else ""
                        if title.strip() or issuer.strip():
                            synced_certifications.append({"title": title, "issuer": issuer, "year": year, "link": link})
                    synced_data["certifications"] = synced_certifications
                    
                    # Sync Projects from AgGrid
                    proj_df = pd.DataFrame(proj_response["data"])
                    synced_projects = []
                    for _, row in proj_df.iterrows():
                        title = str(row['Title']) if 'Title' in row else ""
                        description = str(row['Description']) if 'Description' in row else ""
                        link = str(row['link']) if 'link' in row else ""
                        if title.strip() or description.strip():
                            synced_projects.append({"title": title, "description": description, "link": link})
                    synced_data["projects"] = synced_projects

                    # Sync Skills from AgGrid
                    skill_df = pd.DataFrame(skill_response["data"])
                    synced_skills = [str(row['Skill']).strip() for _, row in skill_df.iterrows() if 'Skill' in row and str(row['Skill']).strip()]
                    synced_data["skills"] = synced_skills
                    
                    # Update session state with the fully synchronized data
                    st.session_state.resume_data = copy.deepcopy(synced_data)
                    st.session_state['expander_open_single'] = True
                    st.session_state['summary_generation_complete'] = False
                    st.session_state['summary_generation_requested'] = False
                    
                    with st.spinner("Generating PDF..."):
                        keywords = st.session_state.get('extracted_keywords', None)
                        # Use the freshly synced data for PDF generation
                        pdf_file, html_out = PDFUtils.generate_pdf(synced_data, keywords=keywords)
                        pdf_b64 = PDFUtils.get_base64_pdf(pdf_file)
                        st.session_state.generated_pdf = pdf_file
                        st.session_state.generated_pdf_b64 = pdf_b64
                        st.session_state.pdf_ready_single = True
                        st.success("PDF generated successfully!")
                        st.rerun()

                # --- PDF Preview Section (Outside button click for persistent display) ---
                if st.session_state.get("pdf_ready_single", False):
                    st.markdown("### 📄 Generated PDF Preview")
                    pdf_b64 = st.session_state.generated_pdf_b64
                    st.info("If the PDF is not viewable above, your browser may not support embedded PDF viewing.")
                    link_id = f"open_pdf_link_{uuid.uuid4().hex}"
                    components.html(f"""
                        <a id="{link_id}" style="margin:10px 0;display:inline-block;padding:8px 16px;font-size:16px;border-radius:5px;background:#0068c9;color:white;text-decoration:none;border:none;cursor:pointer;">
                            🔗 Click here to open the PDF in a new tab
                        </a>
                        <script>
                        const b64Data = "{pdf_b64}";
                        const byteCharacters = atob(b64Data);
                        const byteNumbers = new Array(byteCharacters.length);
                        for (let i = 0; i < byteCharacters.length; i++) {{
                            byteNumbers[i] = byteCharacters.charCodeAt(i);
                        }}
                        const byteArray = new Uint8Array(byteNumbers);
                        const blob = new Blob([byteArray], {{type: "application/pdf"}});
                        const blobUrl = URL.createObjectURL(blob);
                        const link = document.getElementById("{link_id}");
                        link.href = blobUrl;
                        link.target = "_blank";
                        link.rel = "noopener noreferrer";
                        link.onclick = function() {{
                            setTimeout(function(){{URL.revokeObjectURL(blobUrl)}}, 10000);
                        }};
                        </script>
                    """, height=80)
                    st.download_button(
                        "📄 Download PDF",
                        data=st.session_state.generated_pdf,
                        file_name=f"{st.session_state.resume_data.get('name', 'resume').replace(' ', '_')}.pdf",
                        mime="application/pdf",
                        key="pdf_download_single"
                    )
                    keywords = st.session_state.get('extracted_keywords', None)
                    word_file = DocxUtils.generate_docx(st.session_state.resume_data, keywords=keywords)
                    st.download_button(
                        "📝 Download Word",
                        data=word_file,
                        file_name=f"{st.session_state.resume_data.get('name', 'resume').replace(' ', '_')}.docx",
                        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                        key="word_download_single"
                    )

                # Candidate Pitch Summary
                st.markdown("### 📝 Candidate Pitch Summary")
                col1, col2 = st.columns([1, 8])
                with col1:
                    if st.button("✨ Generate Summary", key="generate_summary_single", use_container_width=True):
                        st.session_state['expander_open_single'] = True  # Keep expander open after summary generation
                        with st.spinner("Generating candidate summary..."):
                            summary_prompt = (
                                    f"You are an expert HR professional. You MUST infer and assign a professional job title for the candidate based on the job description and their experience/skills. Do not leave the title blank. If unsure, use the most relevant title from the job description. Then, write a detailed, information-rich, single-paragraph professional summary (8-10 sentences) to introduce the following candidate to a client for a job opportunity. The summary should be written in third person, using formal and business-appropriate language, and should avoid any informal, overly enthusiastic, or emotional expressions. The summary must be comprehensive and cover the candidate's technical expertise, relevant experience, key achievements, major projects, technologies and frameworks used, leadership, teamwork, impact, and educational background as they pertain to the job description. Be specific about programming languages, frameworks, tools, and platforms the candidate has worked with. Mention any certifications or notable accomplishments. The summary should reflect high ethical standards and professionalism, and should not include any bullet points, excitement, or casual language. Use only facts from the provided information and do not invent or exaggerate. The summary should be suitable for inclusion in a formal client communication and should be at least 8-10 sentences long.\n\nReturn your response as a JSON object with two fields: 'title' and 'summary'.\n\nCandidate Information:\nName: {st.session_state.resume_data.get('name', '')}\nTitle: {st.session_state.resume_data.get('title', '')}\nSummary: {st.session_state.resume_data.get('summary', '')}\nSkills: {', '.join(st.session_state.resume_data.get('skills', []))}\n\nProjects:\n{json.dumps(st.session_state.resume_data.get('projects', []), indent=2)}\n\nEducation:\n{json.dumps(st.session_state.resume_data.get('education', []), indent=2)}\n\nJob Description:\n{job_description_single}"
                            )
                            try:
                                client = AzureOpenAI(
                                    api_key=st.secrets["azure_openai"]["api_key"],
                                    api_version=st.secrets["azure_openai"]["api_version"],
                                    azure_endpoint=st.secrets["azure_openai"]["endpoint"]
                                )
                                response = client.chat.completions.create(
                                    model=st.secrets["azure_openai"]["deployment"],
                                    messages=[
                                        {"role": "system", "content": "You are an expert HR professional who writes compelling candidate summaries."},
                                        {"role": "user", "content": summary_prompt}
                                    ],
                                    temperature=0.7,
                                    response_format={"type": "json_object"}
                                )
                                result = response.choices[0].message.content.strip()
                                try:
                                    result_json = json.loads(result)
                                    title = result_json.get("title", "").strip()
                                    if not title:
                                        title = job_description_single.split("\n")[0].split("-")[0].split(":")[0].split(".")[0].strip()
                                        if not title:
                                            title = "Candidate"
                                    st.session_state.resume_data["title"] = title
                                    st.session_state.candidate_summary_single = result_json.get("summary", "")
                                except Exception as e:
                                    st.session_state.candidate_summary_single = result
                            except Exception as e:
                                st.error(f"Error generating summary: {str(e)}")
                with col2:
                    summary = st.session_state.get("candidate_summary_single", "")
                    summary = st.text_area(
                        "Edit the summary as needed",
                        value=summary,
                        height=400,
                        key="summary_edit_single"
                    )
                    components.html(f'''
                        <textarea id="copyText_single" style="position:absolute;left:-9999px;">{summary}</textarea>
                        <button style="margin-top:10px;padding:8px 16px;font-size:16px;border-radius:5px;background:#0068c9;color:white;border:none;cursor:pointer;"
                            onclick="var copyText = document.getElementById('copyText_single'); copyText.style.display='block'; copyText.select(); document.execCommand('copy'); copyText.style.display='none'; alert('Copied!');">
                            📋 Copy Summary
                        </button>
                    ''', height=60)
            else:
                st.info("No candidate selected or retailored yet. Please search and retailor a candidate to edit details.")


elif page == "Database Management":
    st.title("💾 Resume Database Management")
    
    st.markdown("""
    ### Manage Resumes with Ease
    Use the tabs below to either upload and process new resumes or manage existing resumes in the database.
    """)

    # Create tabs for Upload & Process and Database Operations
    upload_tab, db_ops_tab = st.tabs(["📄 Upload & Process", "🔍 Database Operations"])

    # --- Upload & Process Tab ---
    with upload_tab:
        st.markdown("""
        #### Streamlined Resume Processing
        Upload a single PDF or DOC resume and let our AI-powered pipeline handle the rest. The system will automatically:
        1. Extract and parse content from your resume
        2. Standardize the information into a consistent format
        3. Store the processed data in our database

        **Supported formats:** PDF, DOC  
        **Note:** Employee ID is required.
        """)

        # --- Add Employee ID input box ---
        employee_id = st.text_input("Enter Employee ID (required)", key="employee_id_input")

        uploaded_file = st.file_uploader(
            "📤 Upload Resume File (PDF or DOC)", 
            type=["pdf", "doc"], 
            accept_multiple_files=False,
            key="resume_uploader",
            help="Upload a single resume file"
        )
        # Combined processing button
        if uploaded_file:
            if not employee_id.strip():
                st.warning("Please enter an Employee ID before processing.")
            else:
                if st.button("🚀 Process Resume", type="primary", use_container_width=True):
                    with st.spinner("Processing resume..."):
                        # Step 1: Parse
                        process_uploaded_files([uploaded_file])
                        st.success("✅ Parsing complete!")

                        # Step 2: Standardize
                        asyncio.run(standardize_resumes())
                        st.success("✅ Standardization complete!")

                        # Step 3: Validate and reprocess if necessary
                        validate_and_reprocess_resumes([uploaded_file])

                        # Step 4: Upload to MongoDB (inject Employee ID before upload)
                        # --- Inject Employee ID into each standardized file ---
                        for file_path in st.session_state.standardized_files:
                            try:
                                with open(file_path, "r+", encoding="utf-8") as f:
                                    data = json.load(f)
                                    data["employee_id"] = employee_id.strip()
                                    f.seek(0)
                                    json.dump(data, f, indent=2, ensure_ascii=False)
                                    f.truncate()
                            except Exception as e:
                                st.error(f"Error adding Employee ID to {file_path.name}: {e}")
                        upload_to_mongodb()
                        st.success("✅ Database upload complete!")
        else:
            st.info("👆 Please upload a PDF resume file to begin processing")

        # Display processing status
        st.subheader("📊 Processing Status")
        status_col1, status_col2, status_col3 = st.columns(3)
        with status_col1:
            if st.session_state.processing_complete:
                st.success(f"✅ Parsed {len(st.session_state.processed_files)} file(s)")
            else:
                st.info("⏳ Waiting for parsing...")
        with status_col2:
            if st.session_state.standardizing_complete:
                st.success(f"✅ Standardized {len(st.session_state.standardized_files)} file(s)")
            elif st.session_state.processing_complete:
                st.info("⏳ Ready to standardize")
            else:
                st.info("⏳ Waiting for parsing...")
        with status_col3:
            if st.session_state.db_upload_complete:
                st.success(f"✅ Uploaded {len(st.session_state.uploaded_files)} file(s) to MongoDB")
            elif st.session_state.standardizing_complete:
                st.info("⏳ Ready to upload to MongoDB")
            else:
                st.info("⏳ Waiting for standardization...")

        # Display file preview if processed
        if st.session_state.standardized_files:
            st.subheader("👀 Preview Processed Resume")
            selected_file = st.selectbox(
                "Select a resume to preview", 
                options=[f.name for f in st.session_state.standardized_files]
            )
            if selected_file:
                file_path = standardized_dir / selected_file
                with open(file_path, "r", encoding="utf-8") as f:
                    resume_data = json.load(f)
                st.markdown("---")
                # Show Employee ID in the preview
                st.info(f"**Employee ID:** {resume_data.get('employee_id', 'N/A')}")
                render_formatted_resume(resume_data)

    # --- Database Operations Tab ---
    with db_ops_tab:
        st.markdown("""
        #### Database Operations
        
        **Available Operations:**
        1. **View All Resumes:** See complete list of candidates in database
        2. **Search Candidates By:** Name, Employee ID, Location, or College/University
        3. **Update Resume Information:** Edit basic details and contact information
        4. **Delete Resumes:** Remove unwanted entries
        """)

        try:
            db_manager = ResumeDBManager()
            query_type = st.radio("Select Query Type", ["View All Resumes", "Search by Field"])
            
            # Initialize session states
            if "current_view_mode" not in st.session_state:
                st.session_state.current_view_mode = "list"  # list, view, edit, delete
            if "selected_resume_id" not in st.session_state:
                st.session_state.selected_resume_id = None
            if "current_edit_data" not in st.session_state:
                st.session_state.current_edit_data = None
            if "last_selected_resume_id" not in st.session_state:
                st.session_state.last_selected_resume_id = None
            
            if query_type == "View All Resumes":
                if "all_resumes_results" not in st.session_state:
                    st.session_state.all_resumes_results = []
                
                if st.button("📥 Fetch All Resumes", use_container_width=True) or st.session_state.all_resumes_results:
                    with st.spinner("Fetching resumes..."):
                        if not st.session_state.all_resumes_results:
                            st.session_state.all_resumes_results = db_manager.find({})
                        results = st.session_state.all_resumes_results
                        st.success(f"Found {len(results)} resumes")
                        
                        if results:
                            # Show summary table
                            resume_data = []
                            for res in results:
                                resume_data.append({
                                    "Employee ID": res.get("employee_id", "N/A"),
                                    "Name": res.get("name", "N/A"),
                                    "Email": res.get("email", "N/A"),
                                    "Skills": ", ".join(res.get("skills", [])[:3]) + ("..." if len(res.get("skills", [])) > 3 else "")
                                })
                            st.dataframe(resume_data, use_container_width=True)
                            
                            # Create resume options
                            resume_options = []
                            resume_id_map = {}
                            for res in results:
                                display_text = f"{res.get('name', 'Unknown')} - {res.get('email', 'No email')}"
                                resume_options.append(display_text)
                                resume_id_map[display_text] = str(res["_id"])
                            
                            selected_resume_option = st.selectbox(
                                "Select resume to view details", 
                                options=resume_options if resume_options else ["No resumes found"],
                                key="resume_selector"
                            )
                            
                            if selected_resume_option and "No resumes found" not in selected_resume_option:
                                selected_resume_id = resume_id_map.get(selected_resume_option)
                                selected_resume = next((res for res in results if str(res["_id"]) == selected_resume_id), None)
                                
                                # Check if user switched to a different resume
                                if st.session_state.last_selected_resume_id != selected_resume_id:
                                    # Reset view mode and edit data when switching resumes
                                    st.session_state.current_view_mode = "list"
                                    st.session_state.current_edit_data = None
                                    st.session_state.last_selected_resume_id = selected_resume_id
                                
                                if selected_resume:
                                    st.markdown("---")
                                    
                                    # Action buttons - always show these
                                    col1, col2, col3 = st.columns(3)
                                    with col1:
                                        if st.button("👁️ View Details", key="view_btn", use_container_width=True):
                                            st.session_state.current_view_mode = "view"
                                            st.session_state.selected_resume_id = selected_resume_id
                                    with col2:
                                        if st.button("✏️ Edit Resume", key="edit_btn", use_container_width=True):
                                            st.session_state.current_view_mode = "edit"
                                            st.session_state.selected_resume_id = selected_resume_id
                                            st.session_state.current_edit_data = selected_resume.copy()
                                    with col3:
                                        if st.button("🗑️ Delete Resume", key="delete_btn", use_container_width=True):
                                            st.session_state.current_view_mode = "delete"
                                            st.session_state.selected_resume_id = selected_resume_id
                                    
                                    # Display content based on current mode
                                    if st.session_state.current_view_mode == "edit" and st.session_state.current_edit_data:
                                        st.subheader("✏️ Edit Resume")
                                        
                                        with st.form("edit_resume_form"):
                                            st.markdown("### Basic Information")
                                            col1, col2 = st.columns(2)
                                            
                                            with col1:
                                                edited_name = st.text_input("Name", 
                                                    value=st.session_state.current_edit_data.get("name", ""))
                                                edited_email = st.text_input("Email", 
                                                    value=st.session_state.current_edit_data.get("email", ""))
                                                edited_phone = st.text_input("Phone", 
                                                    value=st.session_state.current_edit_data.get("phone", ""))
                                            
                                            with col2:
                                                edited_employee_id = st.text_input("Employee ID", 
                                                    value=st.session_state.current_edit_data.get("employee_id", ""))
                                                edited_location = st.text_input("Location", 
                                                    value=st.session_state.current_edit_data.get("location", ""))
                                            
                                            st.markdown("### Skills")
                                            current_skills = st.session_state.current_edit_data.get("skills", [])
                                            skills_text = ", ".join(current_skills) if isinstance(current_skills, list) else str(current_skills)
                                            edited_skills = st.text_area("Skills (comma-separated)", 
                                                value=skills_text,
                                                help="Enter skills separated by commas")
                                            
                                            # Form buttons
                                            col1, col2 = st.columns(2)
                                            with col1:
                                                if st.form_submit_button("💾 Save Changes", type="primary", use_container_width=True):
                                                    try:
                                                        updated_data = {
                                                            "name": edited_name,
                                                            "email": edited_email,
                                                            "phone": edited_phone,
                                                            "employee_id": edited_employee_id,
                                                            "location": edited_location,
                                                            "skills": [skill.strip() for skill in edited_skills.split(",") if skill.strip()]
                                                        }
                                                        result = db_manager.collection.update_one(
                                                            {"employee_id": selected_resume.get("employee_id")},
                                                            {"$set": updated_data}
                                                        )
                                                        
                                                        if result.modified_count > 0:
                                                            st.success("✅ Resume updated successfully!")
                                                            # Reset states and refresh data
                                                            st.session_state.current_view_mode = "list"
                                                            st.session_state.current_edit_data = None
                                                            st.session_state.all_resumes_results = db_manager.find({})
                                                            st.rerun()
                                                        else:
                                                            st.warning("No changes were made to the resume.")
                                                            
                                                    except Exception as e:
                                                        st.error(f"Error updating resume: {e}")
                                            
                                            with col2:
                                                if st.form_submit_button("❌ Cancel", use_container_width=True):
                                                    st.session_state.current_view_mode = "list"
                                                    st.session_state.current_edit_data = None
                                                    st.rerun()
                                    
                                    elif st.session_state.current_view_mode == "view":
                                        # Display resume details
                                        st.subheader("📄 Resume Details")
                                        
                                        # Basic Information
                                        st.markdown("### 👤 Basic Information")
                                        col1, col2 = st.columns(2)
                                        with col1:
                                            st.write(f"**Name:** {selected_resume.get('name', 'N/A')}")
                                            st.write(f"**Email:** {selected_resume.get('email', 'N/A')}")
                                            st.write(f"**Phone:** {selected_resume.get('phone', 'N/A')}")
                                        with col2:
                                            st.write(f"**Employee ID:** {selected_resume.get('employee_id', 'N/A')}")
                                            st.write(f"**Location:** {selected_resume.get('location', 'N/A')}")
                                        
                                        # Skills
                                        st.markdown("### 🛠️ Skills")
                                        skills = selected_resume.get('skills', [])
                                        if skills:
                                            if isinstance(skills, list):
                                                st.write(", ".join(skills))
                                            else:
                                                st.write(str(skills))
                                        else:
                                            st.write("No skills listed")
                                        
                                        # Education
                                        st.markdown("### 🎓 Education")
                                        education = selected_resume.get('education', [])
                                        if education:
                                            if isinstance(education, list):
                                                for edu in education:
                                                    st.write(f"**{edu.get('degree', 'N/A')}** from {edu.get('institution', 'N/A')}")
                                                    if edu.get('graduation_year'):
                                                        st.write(f"Graduated: {edu.get('graduation_year')}")
                                                    if edu.get('gpa'):
                                                        st.write(f"GPA: {edu.get('gpa')}")
                                            else:
                                                st.write(f"**{education.get('degree', 'N/A')}** from {education.get('institution', 'N/A')}")
                                        else:
                                            st.write("No education information")
                                        
                                        # Experience
                                        st.markdown("### 💼 Experience")
                                        experience = selected_resume.get('experience', [])
                                        if experience:
                                            if isinstance(experience, list):
                                                for exp in experience:
                                                    st.write(f"{exp.get('company', 'N/A')}")
                                                    if exp.get('duration'):
                                                        st.write(f"Duration: {exp.get('duration')}")
                                                    if exp.get('description'):
                                                        st.write(f"Description: {exp.get('description')}")
                                            else:
                                                st.write(f"**{experience.get('job_title', 'N/A')}** at {experience.get('company', 'N/A')}")
                                        else:
                                            st.write("No experience information")
                                        
                                        # Back button
                                        if st.button("← Back to List", key="back_to_list"):
                                            st.session_state.current_view_mode = "list"
                                            st.rerun()
                                    
                                    elif st.session_state.current_view_mode == "delete":
                                        st.error("⚠️ Are you sure you want to delete this resume? This action cannot be undone.")
                                        st.write(f"**Resume:** {selected_resume.get('name', 'Unknown')} - {selected_resume.get('email', 'No email')}")
                                        
                                        col1, col2 = st.columns(2)
                                        with col1:
                                            if st.button("Yes, Delete", key="confirm_delete", type="primary"):
                                                try:
                                                    db_manager.delete_resume({"employee_id": selected_resume.get("employee_id")})
                                                    st.success(f"✅ Deleted resume: {selected_resume.get('name', 'Unknown')}")
                                                    # Reset and refresh
                                                    st.session_state.current_view_mode = "list"
                                                    st.session_state.all_resumes_results = db_manager.find({})
                                                    st.rerun()
                                                except Exception as e:
                                                    st.error(f"Error deleting resume: {e}")
                                        with col2:
                                            if st.button("Cancel", key="cancel_delete"):
                                                st.session_state.current_view_mode = "list"
                                                st.rerun()
            
            elif query_type == "Search by Field":
                col1, col2 = st.columns(2)
                with col1:
                    search_field = st.selectbox(
                        "Search Field", 
                        ["Name", "Employee_ID", "Location", "College"]
                    )
                with col2:
                    search_value = st.text_input("Search Value")
                
                if st.button("🔍 Search", use_container_width=True):
                    if search_value:
                        query = {}
                        if search_field == "Name":
                            query = {"name": {"$regex": search_value, "$options": "i"}}
                        elif search_field == "Employee_ID":
                            query = {"employee_id": {"$regex": search_value, "$options": "i"}}
                        elif search_field == "Location":
                            query = {"location": {"$regex": search_value, "$options": "i"}}
                        elif search_field == "College":
                            search_field_db = "education.institution"
                            # Special institutes handling
                            special_institutes = {
                                "iit": ["IIT", "Indian Institute of Technology", "Indian Inst of Technology", 
                                       "Indian Inst. of Technology", "Indian Institute Technology", "Indian Inst Technology"],
                                "iim": ["IIM", "Indian Institute of Management", "Indian Inst of Management", 
                                       "Indian Inst. of Management", "Indian Institute Management", "Indian Inst Management"],
                                "iiit": ["IIIT", "Indian Institute of Information Technology", "Indian Inst of Information Technology", 
                                        "Indian Inst. of Information Technology", "Indian Institute Information Technology", "Indian Inst Information Technology"],
                                "nit": ["NIT", "National Institute of Technology", "National Inst of Technology", 
                                       "National Inst. of Technology", "National Institute Technology", "National Inst Technology"]
                            }
                            
                            search_val_norm = search_value.strip().lower()
                            matched = None
                            for key, variants in special_institutes.items():
                                if any(search_val_norm == v.lower() for v in variants):
                                    matched = key
                                    break

                            if matched:
                                regex_parts = []
                                for variant in special_institutes[matched]:
                                    if variant.upper() == matched.upper():
                                        regex_parts.append(rf"(^|\s){variant}(\s|$)")
                                    else:
                                        regex_parts.append(variant)
                                regex_pattern = "(" + "|".join(regex_parts) + ")"
                                query = {search_field_db: {"$regex": regex_pattern, "$options": "i"}}
                            else:
                                query = {search_field_db: {"$regex": f"(^|\\s){search_value}(\\s|$)", "$options": "i"}}
                        
                        with st.spinner("Searching..."):
                            results = db_manager.find(query)
                            if results:
                                st.success(f"Found {len(results)} matching resumes")
                                search_options = []
                                st.session_state.search_results = results
                                for res in results:
                                    display_text = f"{res.get('name', 'Unknown')} - {res.get('email', 'No email')}"
                                    search_options.append(display_text)
                                st.session_state.search_options = search_options
                            else:
                                st.warning("No matching resumes found")
                                st.session_state.search_results = []
                                st.session_state.search_options = []
                    else:
                        st.warning("Please enter a search value")
                
                # Display search results
                if "search_options" in st.session_state and st.session_state.search_options:
                    selected_search_result = st.selectbox(
                        "Select resume to view details", 
                        options=st.session_state.search_options,
                        key="search_selector"
                    )
                    
                    if selected_search_result:
                        # Find the selected resume from search results
                        selected_resume = None
                        for res in st.session_state.search_results:
                            display_text = f"{res.get('name', 'Unknown')} - {res.get('email', 'No email')}"
                            if display_text == selected_search_result:
                                selected_resume = res
                                break
                        
                        if selected_resume:
                            st.markdown("---")
                            
                            # Similar view/edit/delete functionality for search results
                            col1, col2, col3 = st.columns(3)
                            with col1:
                                if st.button("👁️ View Details", key="search_view_btn", use_container_width=True):
                                    st.session_state.current_view_mode = "view"
                                    st.session_state.selected_resume_id = str(selected_resume["_id"])
                            with col2:
                                if st.button("✏️ Edit Resume", key="search_edit_btn", use_container_width=True):
                                    st.session_state.current_view_mode = "edit"
                                    st.session_state.selected_resume_id = selected_resume.get("employee_id")  # Use employee_id
                                    st.session_state.current_edit_data = selected_resume.copy()
                            with col3:
                                if st.button("🗑️ Delete Resume", key="search_delete_btn", use_container_width=True):
                                    st.session_state.current_view_mode = "delete"
                                    st.session_state.selected_resume_id = selected_resume.get("employee_id")  # Use employee_id
                            
                            # Display based on mode
                            if st.session_state.current_view_mode == "view":
                                # Same view logic as above
                                st.subheader("📄 Resume Details")
                                
                                # Basic Information
                                st.markdown("### 👤 Basic Information")
                                col1, col2 = st.columns(2)
                                with col1:
                                    st.write(f"**Name:** {selected_resume.get('name', 'N/A')}")
                                    st.write(f"**Email:** {selected_resume.get('email', 'N/A')}")
                                    st.write(f"**Phone:** {selected_resume.get('phone', 'N/A')}")
                                with col2:
                                    st.write(f"**Employee ID:** {selected_resume.get('employee_id', 'N/A')}")
                                    st.write(f"**Location:** {selected_resume.get('location', 'N/A')}")
                                
                                # Skills
                                st.markdown("### 🛠️ Skills")
                                skills = selected_resume.get('skills', [])
                                if skills:
                                    if isinstance(skills, list):
                                        st.write(", ".join(skills))
                                    else:
                                        st.write(str(skills))
                                else:
                                    st.write("No skills listed")
                                
                                if st.button("← Back to Search", key="back_to_search"):
                                    st.session_state.current_view_mode = "list"
                                    st.rerun()

        except Exception as e:
            st.error(f"Error connecting to database: {e}")

def job_matcher_page():
    st.title("JD-Resume Regeneration")
    
    # Initialize session state variables
    if 'job_matcher_results' not in st.session_state:
        st.session_state.job_matcher_results = []
    if 'extracted_keywords' not in st.session_state:
        st.session_state.extracted_keywords = set()
    
    # Job description input
    job_description = st.text_area("Enter Job Description", height=200)
    
    if st.button("Find Matching Candidates"):
        if not job_description.strip():
            st.error("Please enter a job description")
            return
            
        # Create progress bar and status text
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        # Find matching candidates
        matcher = JobMatcher()
        st.session_state.job_matcher_results = matcher.find_matching_candidates(
            job_description, 
            progress_bar=progress_bar,
            status_text=status_text
        )
        
        # Clear progress indicators
        progress_bar.empty()
        status_text.empty()
    
    # Display results if available
    if st.session_state.job_matcher_results:
        st.write("### Matching Candidates")
        
        # Create a table for all candidates
        candidates_data = []
        for candidate in st.session_state.job_matcher_results:
            candidates_data.append({
                "Name": candidate["name"],
                "Score": f"{candidate['score']}%",
                "Status": candidate["status"],
                "Phone": candidate["phone"],
                "Email": candidate["email"]
            })
        
        # Display the table
        st.dataframe(candidates_data)
        
        # Display detailed candidate cards
        st.write("### Candidate Details")
        for candidate in st.session_state.job_matcher_results:
            with st.expander(f"{candidate['name']} - Score: {candidate['score']}%"):
                # Contact information
                st.write(f"**Phone:** {candidate['phone']}")
                st.write(f"**Email:** {candidate['email']}")
                
                # Create two columns for buttons
                col1, col2 = st.columns(2)
                
                with col1:
                    if st.button("📊 View Matching Analysis", key=f"analysis_{candidate['mongo_id']}"):
                        st.write("**Matching Analysis:**")
                        st.write(candidate['reason'])
                
                with col2:
                    if st.button("🔄 Retailor Resume", key=f"retailor_{candidate['mongo_id']}"):
                        with st.spinner("Retailoring resume..."):
                            safe_resume = convert_objectid_to_str(candidate["resume"])
                            # Get matcher from session state
                            matcher = st.session_state.get('matcher')
                            if not matcher:
                                st.error("Error: Job matcher not initialized. Please try searching again.")
                                return
                            new_res = matcher.resume_retailor.retailor_resume(
                            safe_resume,
                            st.session_state.extracted_keywords
                        )
                            if new_res:
                                st.success("Resume retailored successfully!")
                                # Create a downloadable JSON file
                                json_str = json.dumps(new_res, indent=2)
                                st.download_button(
                                    label="📥 Download Retailored Resume",
                                    data=json_str,
                                    file_name=f"retailored_resume_{candidate['name'].replace(' ', '_')}.json",
                                    mime="application/json",
                                    key=f"download_{candidate['mongo_id']}"
                                )
                                # Show the retailored resume
                                st.write("### Retailored Resume")
                                st.json(new_res)
                
                # Show full resume button
                if st.button("📄 View Full Resume", key=f"view_{candidate['mongo_id']}"):
                    st.json(candidate['resume'])    
