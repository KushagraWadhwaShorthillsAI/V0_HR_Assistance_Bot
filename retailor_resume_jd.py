#!/usr/bin/env python3
"""
Resume Retailor with Job Description Keywords
This script retailors resumes using keywords that are present in the resume's keywords attribute.
It enhances both project titles and descriptions using the job description keywords.
"""

import json
import re
import random
from typing import List, Dict, Set, Tuple
from openai import AzureOpenAI
import streamlit as st

class ResumeRetailorWithJD:
    def __init__(self, azure_config: Dict[str, str]):
        """
        Initialize the resume retailor with Azure OpenAI configuration.
        
        Args:
            azure_config: Dictionary containing Azure OpenAI configuration
                - api_key: Azure OpenAI API key
                - api_version: API version
                - endpoint: Azure endpoint
                - deployment: Model deployment name
        """
        self.client = AzureOpenAI(
            api_key=azure_config["api_key"],
            api_version=azure_config["api_version"],
            azure_endpoint=azure_config["endpoint"]
        )
        self.deployment = azure_config["deployment"]
    
    def convert_objectid_to_str(self, obj):
        """Convert ObjectId to string for JSON serialization."""
        if isinstance(obj, dict):
            return {k: self.convert_objectid_to_str(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self.convert_objectid_to_str(i) for i in obj]
        elif hasattr(obj, '__class__') and obj.__class__.__name__ == "ObjectId":
            return str(obj)
        else:
            return obj
    
    def extract_all_projects(self, resume: Dict) -> list:
        """Extract ALL projects from both 'projects' and 'experience' sections."""
        all_projects = []
        
        # Process original projects
        for proj in resume.get('projects', []):
            proj_copy = proj.copy()
            proj_copy['source'] = 'projects'
            all_projects.append(proj_copy)
        
        # Process experience descriptions and extract as projects
        for exp in resume.get('experience', []):
            exp_project = {
                'title': exp.get('title', exp.get('position', 'Professional Experience')),
                'description': exp.get('description', ''),
                'technologies': exp.get('technologies', []) if 'technologies' in exp else [],
                'company': exp.get('company', ''),
                'duration': exp.get('duration', ''),
                'source': 'experience'
            }
            all_projects.append(exp_project)
        
        return all_projects
    
    def _extract_main_technology(self, description: str, technologies: list) -> str:
        """Helper method to extract the main technology from project info."""
        # First check the technologies list
        if technologies:
            return technologies[0].title()
        
        # Then check the description for common technologies
        description_lower = description.lower()
        common_techs = [
            'n8n', 'python', 'javascript', 'react', 'node', 'nodejs', 'java', 'aws', 
            'mongodb', 'mysql', 'postgresql', 'docker', 'kubernetes', 'tensorflow', 
            'flask', 'django', 'angular', 'vue', 'spring', 'express', 'redis', 
            'elasticsearch', 'jenkins', 'git', 'llm', 'openai', 'chatgpt', 'gpt', 
            'azure', 'firebase', 'stripe', 'oauth', 'jwt', 'restapi', 'graphql', 
            'websocket', 'microservices', 'serverless', 'lambda', 'html', 'css', 
            'bootstrap', 'tailwind', 'nextjs', 'nuxtjs', 'svelte', 'php', 'laravel', 
            'symfony', 'ruby', 'rails', 'go', 'rust', 'swift', 'kotlin', 'flutter', 
            'dart', 'unity', 'unreal', 'blender'
        ]
        
        for tech in common_techs:
            if tech in description_lower:
                # Special case for n8n to keep it uppercase
                return 'n8n' if tech == 'n8n' else tech.title()
        
        return ""
    
    @staticmethod
    def _normalize_title(text):
        """Normalize text for strict comparison: lowercase, remove whitespace and punctuation."""
        import string
        return ''.join(c for c in text.lower() if c not in string.whitespace + string.punctuation)
    
    def universal_enhance_project_title(self, project: Dict) -> str:
        """
        UNIVERSAL function that ALWAYS enhances project titles to be skill-focused and impactful.
        Works regardless of whether JD is provided or not. Guaranteed to produce a different title.
        """
        original_title = project.get('title', '').strip()
        description = project.get('description', '')
        technologies = project.get('technologies', [])
        
        # If no original title, create a basic one
        if not original_title:
            original_title = "Technical Project"
        
        prompt = f"""You are an expert at creating impactful, skill-focused project titles. Your job is to rewrite this project title to be more professional, attention-grabbing, and technology-focused.

CRITICAL REQUIREMENTS:
- The new title MUST be different from the original title
- Highlight the main technologies/skills used in the project
- Make it professional and impactful
- Use technology prefixes when applicable (e.g., "React-Based", "Python-Powered", "n8n-Driven", "AWS-Deployed")
- Focus on what makes this project technically interesting
- Return ONLY the enhanced title, no explanations

Original Title: {original_title}
Project Description: {description}
Technologies Used: {', '.join(technologies) if technologies else 'Not specified'}

Examples of good enhanced titles:
- "n8n-Based Resume Automation Pipeline" 
- "React-Powered E-commerce Platform"
- "Python-Driven Data Analytics Dashboard"
- "AWS-Deployed Microservices Architecture"
- "MongoDB-Backed Social Media Application"
- "Full-Stack Web Application with Authentication"
- "Machine Learning-Powered Recommendation System"
- "Real-Time Chat Application with WebSocket"

Create an enhanced, skill-focused title:"""

        try:
            response = self.client.chat.completions.create(
                model=self.deployment,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                response_format={"type": "text"}
            )
            enhanced_title = response.choices[0].message.content.strip()
            
            # Remove any quotes if they exist
            enhanced_title = enhanced_title.strip('"\'')
            
            # Safety check: if somehow the same title is returned, force a change
            if self._normalize_title(enhanced_title) == self._normalize_title(original_title):
                # Extract main technology and create a forced enhancement
                main_tech = self._extract_main_technology(description, technologies)
                if main_tech:
                    enhanced_title = f"{main_tech}-Based {original_title}"
                else:
                    enhanced_title = f"Advanced {original_title}"
            
            return enhanced_title
            
        except Exception as e:
            print(f"Error enhancing project title: {str(e)}")
            # Robust fallback that always produces a different title
            main_tech = self._extract_main_technology(description, technologies)
            if main_tech:
                return f"{main_tech}-Based {original_title}"
            else:
                return f"Professional {original_title}"
    
    def enhance_project_description_car(self, project: Dict, job_keywords: Set[str]) -> str:
        """Enhance project description using CAR strategy with job description keywords."""
        keywords = ", ".join(list(job_keywords)[:8])  # Limit to 8 keywords for better coverage
        original_description = project.get('description', '').strip()
        
        if not original_description:
            return original_description
            
        prompt = f"""You're a resume writing assistant. Rewrite the given project description into 6–8 **concise**, **to-the-point**, **easy-to-read sentences** using the CAR (Cause, Action, Result) strategy. Your goal is to:

- Maintain accuracy — do not hallucinate or exaggerate.
- Use provided **keywords** from the job description whenever applicable.
- Avoid fluff and background info — focus on **what was done and why it mattered**.
- Write each sentence as a **standalone impact point** suitable for resume or LinkedIn.
- **CRITICAL: Do NOT use any bullet points, symbols, dashes, arrows, or formatting markers. Write ONLY plain, direct sentences separated by line breaks.**
- **Do NOT use any markdown formatting (no **, *, _, etc.) or blank lines. Output only plain text sentences.**
- **Keep each sentence extremely concise and clear to the point.**
- If results or metrics are not given, **do not make them up**.
- Use clear, active language and relevant technical terminology.

---

**Input**
Project Description: {original_description}
Job Description Keywords: {keywords}

---

**Output**
6–8 clean, CAR-style resume points. Each should be 1–2 lines max, use keywords where appropriate, and communicate tangible work or outcomes clearly."""
        
        try:
            response = self.client.chat.completions.create(
                model=self.deployment,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
                response_format={"type": "text"}
            )
            enhanced_description = response.choices[0].message.content.strip()
            
            # Ensure we return something useful even if the response is empty
            if not enhanced_description or len(enhanced_description) < 20:
                return original_description
                
            return enhanced_description
            
        except Exception as e:
            print(f"Error enhancing project description: {str(e)}")
            return original_description
    
    def select_relevant_projects(self, all_projects: list, job_keywords: Set[str]) -> list:
        """Select relevant projects based on job description keywords."""
        keywords_lower = {k.lower() for k in job_keywords}
        relevant = []
        
        # First, try direct keyword matching
        for proj in all_projects:
            text = (proj.get('title', '') + ' ' + proj.get('description', '')).lower()
            if any(k in text for k in keywords_lower):
                relevant.append(proj)
        
        if relevant:
            return relevant
        
        # If no direct matches, pick top 2 by description length
        return sorted(all_projects, key=lambda p: len(p.get('description', '')), reverse=True)[:2]
    
    def generate_job_specific_title(self, candidate: Dict, job_keywords: Set[str]) -> str:
        """Generate a job-specific title for the candidate based on their profile and job keywords."""
        prompt = f"""You are an expert HR professional specializing in job title creation. Create a specific, professional job title that accurately reflects the candidate's experience and aligns with the job requirements.

Rules:
- Use industry-standard job titles
- Match the candidate's actual experience level (don't overstate)
- Be specific to the role and industry
- Use ONLY information from the candidate's profile and job keywords
- Return ONLY the job title, no explanation

Candidate Profile:
- Name: {candidate.get('name', '')}
- Current Title: {candidate.get('title', '')}
- Skills: {', '.join(candidate.get('skills', []))}
- Projects: {json.dumps(candidate.get('projects', []), indent=2)}
- Education: {json.dumps(candidate.get('education', []), indent=2)}

Job Keywords: {', '.join(job_keywords)}

Generate a professional job title that matches their experience level and aligns with the job requirements:"""

        try:
            response = self.client.chat.completions.create(
                model=self.deployment,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                response_format={"type": "text"}
            )
            
            title = response.choices[0].message.content.strip()
            return title
            
        except Exception as e:
            print(f"Error generating job title: {str(e)}")
            return candidate.get('title', '')
    
    def generate_professional_summary(self, candidate: Dict, job_keywords: Set[str]) -> str:
        """Generates a professional summary aligned with job keywords."""
        prompt = f"""You are an expert resume writer and HR professional. Create a concise, compelling, and professional summary (3-4 sentences) for a candidate, tailored to specific job requirements.

CRITICAL RULES:
- Write in the third person, maintaining a formal and confident tone.
- The summary must strictly be based on the candidate's profile. Do not invent or exaggerate information.
- Seamlessly weave in skills and experiences that are most relevant to the provided Job Keywords.
- The summary should highlight the candidate's key strengths and value proposition for the role.
- Return ONLY the summary paragraph. Do not include any extra text, labels, or quotation marks.

Write a professional summary for the following candidate, focusing on their fit for a job that requires these keywords: {', '.join(job_keywords)}.

**Candidate Profile:**
- Name: {candidate.get('name', '')}
- Title: {candidate.get('title', '')}
- Skills: {', '.join(candidate.get('skills', []))}
- Experience: {json.dumps(candidate.get('experience', []), indent=2)}
- Projects: {json.dumps(candidate.get('projects', []), indent=2)}

Generate a 3-4 sentence professional summary based *only* on the provided information:"""

        try:
            response = self.client.chat.completions.create(
                model=self.deployment,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.4,
                response_format={"type": "text"}
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            print(f"Error generating summary: {str(e)}")
            return candidate.get('summary', '')
    
    def _extract_candidate_text(self, resume: Dict) -> str:
        """Extract all text content from candidate's resume for skill matching."""
        text_parts = []
        
        # Add project descriptions and titles
        for proj in resume.get('projects', []):
            text_parts.append(proj.get('title', ''))
            text_parts.append(proj.get('description', ''))
            text_parts.extend(proj.get('technologies', []))
        
        # Add experience descriptions and titles
        for exp in resume.get('experience', []):
            text_parts.append(exp.get('title', ''))
            text_parts.append(exp.get('position', ''))
            text_parts.append(exp.get('description', ''))
            text_parts.extend(exp.get('technologies', []))
        
        # Add education information
        for edu in resume.get('education', []):
            text_parts.append(edu.get('degree', ''))
            text_parts.append(edu.get('institution', ''))
            text_parts.append(edu.get('field', ''))
        
        # Add certifications
        for cert in resume.get('certifications', []):
            if isinstance(cert, dict):
                text_parts.append(cert.get('title', ''))
                text_parts.append(cert.get('issuer', ''))
            else:
                text_parts.append(str(cert))
        
        # Add summary
        text_parts.append(resume.get('summary', ''))
        
        return ' '.join(text_parts).lower()
    
    def _find_matching_keywords(self, job_keywords: Set[str], original_skills: list, candidate_text: str) -> list:
        """Find JD keywords that the candidate actually demonstrates in their background."""
        matching_keywords = []
        original_skills_lower = {skill.lower() for skill in original_skills}
        
        for keyword in job_keywords:
            keyword_lower = keyword.lower()
            
            # Skip if already in original skills
            if keyword_lower in original_skills_lower:
                continue
            
            # Check if keyword appears in candidate's projects, experience, etc.
            if keyword_lower in candidate_text:
                matching_keywords.append(keyword)
        
        # Limit to top 3-5 most relevant matching keywords to avoid skill inflation
        return matching_keywords[:5]
    
    def retailor_resume_with_jd(self, original_resume: Dict) -> Dict:
        """
        Retailor the resume using job description keywords present in the resume.
        - Enhances relevant project titles and descriptions using job keywords
        - Converts work experience to projects and enhances them
        - Generates job-specific summary and title
        - Optimizes skills list with job-relevant keywords
        """
        # Convert ObjectId to string for JSON serialization
        safe_resume = self.convert_objectid_to_str(original_resume)
        
        # Extract job keywords from the resume
        job_keywords = set(safe_resume.get('keywords', []))
        
        if not job_keywords:
            print("Warning: No job keywords found in resume. Proceeding with basic enhancement.")
            job_keywords = set()
        
        # Extract ALL projects from both projects and experience sections
        all_projects = self.extract_all_projects(safe_resume)
        
        # Select relevant projects based on job keywords
        relevant_projects = self.select_relevant_projects(all_projects, job_keywords)
        
        # Enhance relevant projects with both title and description
        enhanced_projects = []
        for proj in relevant_projects:
            # UNIVERSAL title enhancement
            enhanced_title = self.universal_enhance_project_title(proj)
            proj_copy = proj.copy()
            proj_copy['title'] = enhanced_title
            
            # Enhance description with CAR strategy using job keywords
            if job_keywords:
                enhanced_desc = self.enhance_project_description_car(proj, job_keywords)
                proj_copy['description'] = enhanced_desc
            
            enhanced_projects.append(proj_copy)
        
        # Update the resume with enhanced projects
        safe_resume['projects'] = enhanced_projects
        
        # Generate job-specific title
        if job_keywords:
            safe_resume["title"] = self.generate_job_specific_title(safe_resume, job_keywords)
        
        # Generate job-specific summary
        if job_keywords:
            safe_resume["summary"] = self.generate_professional_summary(safe_resume, job_keywords)
        
        # Optimize skills list with job-relevant keywords
        if job_keywords:
            original_skills = list(safe_resume.get("skills", []))
            candidate_text = self._extract_candidate_text(safe_resume)
            matching_keywords = self._find_matching_keywords(job_keywords, original_skills, candidate_text)
            
            # Priority 1: Original skills that match job keywords (highest priority)
            job_keywords_lower = {k.lower() for k in job_keywords}
            original_skills_lower = {s.lower(): s for s in original_skills}
            matching_skills = []
            for keyword_lower in job_keywords_lower:
                if keyword_lower in original_skills_lower:
                    matching_skills.append(original_skills_lower[keyword_lower])
            
            # Priority 2: Only genuinely demonstrated JD keywords (not all JD keywords)
            demonstrated_keywords = matching_keywords
            
            # Priority 3: Remaining original skills (non-matching ones)
            remaining_skills = []
            for skill in original_skills:
                if skill.lower() not in job_keywords_lower:
                    remaining_skills.append(skill)
            
            # Combine skills with priority order and limit to 18
            prioritized_skills = matching_skills + demonstrated_keywords + remaining_skills
            final_skills = prioritized_skills[:18]
            
            safe_resume["skills"] = final_skills
        
        return safe_resume

def main():
    """
    Example usage of the ResumeRetailorWithJD class.
    This function demonstrates how to use the retailor with job description keywords.
    """
    # Example Azure OpenAI configuration
    azure_config = {
        "api_key": "your_azure_openai_api_key",
        "api_version": "2024-02-15-preview",
        "endpoint": "https://your-resource.openai.azure.com/",
        "deployment": "your-deployment-name"
    }
    
    # Example resume data with job keywords
    example_resume = {
        "name": "John Doe",
        "email": "john.doe@email.com",
        "phone": "+1-555-0123",
        "title": "Software Developer",
        "skills": ["Python", "JavaScript", "React", "Node.js", "MongoDB"],
        "keywords": ["Python", "React", "AWS", "Docker", "Microservices", "API Development"],
        "projects": [
            {
                "title": "E-commerce Website",
                "description": "Built a full-stack e-commerce platform using React and Node.js",
                "technologies": ["React", "Node.js", "MongoDB"]
            }
        ],
        "experience": [
            {
                "title": "Software Engineer",
                "company": "Tech Corp",
                "description": "Developed web applications using Python and Django",
                "technologies": ["Python", "Django", "PostgreSQL"],
                "duration": "2020-2022"
            }
        ],
        "education": [
            {
                "degree": "Bachelor of Science",
                "institution": "University of Technology",
                "field": "Computer Science"
            }
        ]
    }
    
    # Initialize the retailor
    retailor = ResumeRetailorWithJD(azure_config)
    
    # Retailor the resume with job description keywords
    try:
        retailored_resume = retailor.retailor_resume_with_jd(example_resume)
        
        print("=== ORIGINAL RESUME ===")
        print(json.dumps(example_resume, indent=2))
        
        print("\n=== RETAILORED RESUME ===")
        print(json.dumps(retailored_resume, indent=2))
        
        # Show what changed
        print("\n=== CHANGES MADE ===")
        print(f"Job Keywords Used: {', '.join(example_resume.get('keywords', []))}")
        
        print("\nEnhanced Project Titles and Descriptions:")
        for i, (orig_proj, retailored_proj) in enumerate(zip(example_resume.get('projects', []), retailored_resume.get('projects', []))):
            print(f"  {i+1}. Title: '{orig_proj.get('title', '')}' → '{retailored_proj.get('title', '')}'")
            print(f"     Description: Enhanced with job keywords")
        
        print("\nEnhanced Work Experience (converted to projects):")
        for i, exp in enumerate(example_resume.get('experience', [])):
            retailored_proj = retailored_resume['projects'][len(example_resume.get('projects', [])) + i]
            print(f"  {i+1}. '{exp.get('title', '')}' → '{retailored_proj.get('title', '')}'")
        
        print(f"\nGenerated Title: {retailored_resume.get('title', '')}")
        print(f"Generated Summary: {retailored_resume.get('summary', '')}")
        print(f"Optimized Skills: {', '.join(retailored_resume.get('skills', []))}")
        
    except Exception as e:
        print(f"Error retailoring resume: {str(e)}")

if __name__ == "__main__":
    main() 