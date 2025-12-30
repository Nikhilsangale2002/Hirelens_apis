import PyPDF2
import docx
import re
from typing import Dict, List

class ResumeParser:
    """Parse resumes and extract structured data"""
    
    def parse(self, file_path: str) -> Dict:
        """Main parsing method"""
        try:
            # Extract text based on file type
            if file_path.endswith('.pdf'):
                text = self._extract_pdf(file_path)
            elif file_path.endswith('.docx'):
                text = self._extract_docx(file_path)
            else:
                raise ValueError("Unsupported file format")
            
            # Parse structured data
            parsed = {
                'raw_text': text,
                'name': self._extract_name(text),
                'email': self._extract_email(text),
                'phone': self._extract_phone(text),
                'location': self._extract_location(text),
                'skills': self._extract_skills(text),
                'experience_years': self._extract_experience_years(text),
                'education_level': self._extract_education(text),
                'projects': self._extract_projects(text),
                'certifications': self._extract_certifications(text)
            }
            
            return parsed
            
        except Exception as e:
            raise Exception(f"Error parsing resume: {str(e)}")
    
    def _extract_pdf(self, file_path: str) -> str:
        """Extract text from PDF"""
        text = ""
        with open(file_path, 'rb') as file:
            reader = PyPDF2.PdfReader(file)
            for page in reader.pages:
                text += page.extract_text()
        return text
    
    def _extract_docx(self, file_path: str) -> str:
        """Extract text from DOCX"""
        doc = docx.Document(file_path)
        return '\n'.join([para.text for para in doc.paragraphs])
    
    def _extract_name(self, text: str) -> str:
        """Extract candidate name (first few lines)"""
        lines = [l.strip() for l in text.split('\n') if l.strip()]
        if lines:
            return lines[0]
        return "Unknown"
    
    def _extract_email(self, text: str) -> str:
        """Extract email address"""
        pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        match = re.search(pattern, text)
        return match.group(0) if match else None
    
    def _extract_phone(self, text: str) -> str:
        """Extract phone number"""
        pattern = r'(\+?\d{1,3}[-.\s]?)?(\(?\d{3}\)?[-.\s]?)?\d{3}[-.\s]?\d{4}'
        match = re.search(pattern, text)
        return match.group(0) if match else None
    
    def _extract_location(self, text: str) -> str:
        """Extract location"""
        # Simple pattern matching for common locations
        lines = text.split('\n')
        for line in lines[:10]:  # Check first 10 lines
            if any(city in line.lower() for city in ['bangalore', 'mumbai', 'delhi', 'pune', 'hyderabad', 'chennai']):
                return line.strip()
        return None
    
    def _extract_skills(self, text: str) -> List[str]:
        """Extract skills"""
        # Common skill keywords
        common_skills = [
            'python', 'java', 'javascript', 'react', 'node', 'angular', 'vue',
            'sql', 'mongodb', 'aws', 'docker', 'kubernetes', 'git', 'agile',
            'machine learning', 'data science', 'tensorflow', 'pytorch',
            'html', 'css', 'typescript', 'c++', 'c#', 'php', 'ruby', 'golang'
        ]
        
        text_lower = text.lower()
        found_skills = []
        
        for skill in common_skills:
            if skill in text_lower:
                found_skills.append(skill.title())
        
        return found_skills
    
    def _extract_experience_years(self, text: str) -> float:
        """Extract years of experience"""
        # Look for patterns like "5 years", "3+ years", etc.
        pattern = r'(\d+\.?\d*)\s*\+?\s*years?'
        matches = re.findall(pattern, text.lower())
        
        if matches:
            return float(max(matches))  # Return the highest number found
        
        return 0.0
    
    def _extract_education(self, text: str) -> str:
        """Extract education level"""
        text_lower = text.lower()
        
        if any(word in text_lower for word in ['phd', 'ph.d', 'doctorate']):
            return 'PhD'
        elif any(word in text_lower for word in ['master', 'mba', 'm.tech', 'm.sc']):
            return 'Masters'
        elif any(word in text_lower for word in ['bachelor', 'b.tech', 'b.e', 'b.sc']):
            return 'Bachelors'
        
        return 'Unknown'
    
    def _extract_projects(self, text: str) -> List[str]:
        """Extract project names"""
        # Simple extraction - look for "Project:" or section headers
        projects = []
        lines = text.split('\n')
        
        for i, line in enumerate(lines):
            if 'project' in line.lower() and ':' in line:
                projects.append(line.strip())
        
        return projects[:5]  # Return top 5
    
    def _extract_certifications(self, text: str) -> List[str]:
        """Extract certifications"""
        certs = []
        common_certs = ['aws', 'azure', 'gcp', 'pmp', 'scrum', 'cissp', 'ceh']
        
        text_lower = text.lower()
        for cert in common_certs:
            if cert in text_lower:
                certs.append(cert.upper())
        
        return certs
