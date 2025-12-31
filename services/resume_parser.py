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
        """Extract skills with comprehensive matching"""
        # Expanded skill database with variations and synonyms
        skill_patterns = {
            # Programming Languages
            'Python': ['python', 'py'],
            'Java': ['java'],
            'JavaScript': ['javascript', 'js', 'ecmascript'],
            'TypeScript': ['typescript', 'ts'],
            'C++': ['c++', 'cpp', 'cplusplus'],
            'C#': ['c#', 'csharp', 'c sharp'],
            'PHP': ['php'],
            'Ruby': ['ruby', 'rails'],
            'Go': ['golang', 'go'],
            'Rust': ['rust'],
            'Swift': ['swift'],
            'Kotlin': ['kotlin'],
            'Scala': ['scala'],
            'R': ['\br\b'],
            
            # Web Technologies
            'React': ['react', 'reactjs', 'react.js'],
            'Angular': ['angular', 'angularjs'],
            'Vue': ['vue', 'vuejs', 'vue.js'],
            'Next.js': ['next.js', 'nextjs', 'next'],
            'Node.js': ['node', 'nodejs', 'node.js'],
            'Express': ['express', 'expressjs', 'express.js'],
            'Django': ['django'],
            'Flask': ['flask'],
            'FastAPI': ['fastapi', 'fast api'],
            'Spring': ['spring', 'spring boot', 'springboot'],
            'ASP.NET': ['asp.net', 'aspnet', 'asp net'],
            'HTML': ['html', 'html5'],
            'CSS': ['css', 'css3'],
            'Tailwind': ['tailwind', 'tailwindcss'],
            'Bootstrap': ['bootstrap'],
            'jQuery': ['jquery'],
            
            # Databases
            'MySQL': ['mysql', 'my sql'],
            'PostgreSQL': ['postgresql', 'postgres', 'psql'],
            'MongoDB': ['mongodb', 'mongo'],
            'Redis': ['redis'],
            'Oracle': ['oracle', 'oracle db'],
            'SQL Server': ['sql server', 'mssql', 'ms sql'],
            'SQLite': ['sqlite'],
            'Cassandra': ['cassandra'],
            'Elasticsearch': ['elasticsearch', 'elastic search', 'elastic'],
            'DynamoDB': ['dynamodb', 'dynamo'],
            
            # Cloud & DevOps
            'AWS': ['aws', 'amazon web services'],
            'Azure': ['azure', 'microsoft azure'],
            'GCP': ['gcp', 'google cloud', 'google cloud platform'],
            'Docker': ['docker', 'containerization'],
            'Kubernetes': ['kubernetes', 'k8s'],
            'Jenkins': ['jenkins'],
            'CI/CD': ['ci/cd', 'cicd', 'continuous integration', 'continuous deployment'],
            'Terraform': ['terraform'],
            'Ansible': ['ansible'],
            'Git': ['git', 'github', 'gitlab', 'bitbucket'],
            'Linux': ['linux', 'unix'],
            
            # API & Architecture
            'REST API': ['rest', 'rest api', 'restful', 'restful api', 'rest apis'],
            'GraphQL': ['graphql', 'graph ql'],
            'Microservices': ['microservices', 'micro services', 'microservice'],
            'SOAP': ['soap'],
            'gRPC': ['grpc'],
            
            # Data Science & ML
            'Machine Learning': ['machine learning', 'ml', 'artificial intelligence', 'ai'],
            'Deep Learning': ['deep learning', 'neural network', 'neural networks'],
            'TensorFlow': ['tensorflow', 'tensor flow'],
            'PyTorch': ['pytorch', 'torch'],
            'Scikit-learn': ['scikit-learn', 'sklearn', 'scikit learn'],
            'Pandas': ['pandas'],
            'NumPy': ['numpy', 'np'],
            'Keras': ['keras'],
            'NLP': ['nlp', 'natural language processing'],
            'Computer Vision': ['computer vision', 'cv', 'image processing'],
            
            # Testing
            'Jest': ['jest'],
            'Pytest': ['pytest', 'py.test'],
            'JUnit': ['junit'],
            'Selenium': ['selenium'],
            'Cypress': ['cypress'],
            'Mocha': ['mocha'],
            
            # Methodologies
            'Agile': ['agile', 'scrum', 'kanban'],
            'JIRA': ['jira'],
            'Postman': ['postman'],
        }
        
        text_lower = text.lower()
        found_skills = set()  # Use set to avoid duplicates
        
        for skill_name, patterns in skill_patterns.items():
            for pattern in patterns:
                # Use word boundaries for better matching
                if pattern.startswith('\\b'):
                    # Already has word boundary
                    if re.search(pattern, text_lower):
                        found_skills.add(skill_name)
                        break
                else:
                    # Add word boundaries or check if pattern exists
                    if re.search(r'\b' + re.escape(pattern) + r'\b', text_lower):
                        found_skills.add(skill_name)
                        break
        
        result = sorted(list(found_skills))
        print(f"DEBUG: Extracted {len(result)} skills from resume: {result}")
        return result
    
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
