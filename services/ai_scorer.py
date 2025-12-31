from typing import Dict, List
import google.generativeai as genai
from config import Config

class AIScorer:
    """Score resumes against job requirements using AI"""
    
    def __init__(self):
        if Config.AI_PROVIDER == 'gemini' and Config.GEMINI_API_KEY:
            genai.configure(api_key=Config.GEMINI_API_KEY)
            self.model = genai.GenerativeModel('gemini-pro')
            self.use_ai = True
        else:
            self.use_ai = False
    
    def score_resume(self, parsed_data: Dict, job) -> Dict:
        """Score resume against job requirements"""
        
        if self.use_ai:
            return self._ai_score(parsed_data, job)
        else:
            return self._rule_based_score(parsed_data, job)
    
    def _rule_based_score(self, parsed_data: Dict, job) -> Dict:
        """Rule-based scoring with intelligent skill matching"""
        
        score = 0.0
        matched_skills = []
        missing_skills = []
        
        candidate_skills = [s.lower().strip() for s in (parsed_data.get('skills') or [])]
        required_skills_orig = job.skills_required or []
        
        # Skill synonyms for better matching
        skill_synonyms = {
            'javascript': ['js', 'javascript', 'ecmascript'],
            'typescript': ['ts', 'typescript'],
            'python': ['py', 'python'],
            'rest api': ['rest', 'restful', 'rest api', 'restful api', 'rest apis'],
            'mysql': ['mysql', 'my sql'],
            'postgresql': ['postgres', 'postgresql', 'psql'],
            'mongodb': ['mongo', 'mongodb'],
            'node.js': ['node', 'nodejs', 'node.js'],
            'react': ['react', 'reactjs', 'react.js'],
            'angular': ['angular', 'angularjs'],
            'vue': ['vue', 'vuejs', 'vue.js'],
            'machine learning': ['ml', 'machine learning', 'ai', 'artificial intelligence'],
            'docker': ['docker', 'containerization'],
            'kubernetes': ['k8s', 'kubernetes'],
            'flask': ['flask'],
            'django': ['django'],
            'spring': ['spring', 'spring boot', 'springboot'],
            'aws': ['aws', 'amazon web services'],
            'azure': ['azure', 'microsoft azure'],
            'gcp': ['gcp', 'google cloud'],
        }
        
        # Skills match (50% weight)
        if required_skills_orig:
            for req_skill in required_skills_orig:
                req_skill_lower = req_skill.lower().strip()
                matched = False
                
                # Get synonyms for this required skill
                synonyms = skill_synonyms.get(req_skill_lower, [req_skill_lower])
                
                # Check if any candidate skill matches any synonym
                for cand_skill in candidate_skills:
                    # Direct match
                    if cand_skill == req_skill_lower:
                        matched_skills.append(req_skill)
                        matched = True
                        break
                    
                    # Synonym match
                    for synonym in synonyms:
                        if synonym in cand_skill or cand_skill in synonym:
                            matched_skills.append(req_skill)
                            matched = True
                            break
                    
                    if matched:
                        break
                
                if not matched:
                    missing_skills.append(req_skill)
            
            skills_score = (len(matched_skills) / len(required_skills_orig)) * 50
            score += skills_score
            
            # Debug logging
            print(f"DEBUG: Required skills: {required_skills_orig}")
            print(f"DEBUG: Candidate skills: {candidate_skills}")
            print(f"DEBUG: Matched skills: {matched_skills}")
            print(f"DEBUG: Missing skills: {missing_skills}")
            print(f"DEBUG: Skills score: {skills_score}/50")
        else:
            score += 50  # If no required skills, give full score
        
        # Experience match (30% weight)
        candidate_exp = parsed_data.get('experience_years', 0)
        required_exp = self._parse_experience_requirement(job.experience_required)
        
        if required_exp:
            if candidate_exp >= required_exp:
                score += 30
            elif candidate_exp >= required_exp * 0.7:  # 70% of required
                score += 20
            elif candidate_exp >= required_exp * 0.5:  # 50% of required
                score += 10
        else:
            score += 30
        
        # Education match (10% weight)
        education_levels = {'phd': 4, 'masters': 3, 'bachelors': 2, 'unknown': 1}
        candidate_edu = education_levels.get(parsed_data.get('education_level', '').lower(), 1)
        
        if candidate_edu >= 2:  # At least Bachelors
            score += 10
        
        # Projects/Certifications (10% weight)
        if parsed_data.get('projects') or parsed_data.get('certifications'):
            score += 10
        
        explanation = f"Matched {len(matched_skills)}/{len(required_skills_orig)} required skills. "
        explanation += f"{candidate_exp} years experience. "
        explanation += f"Education: {parsed_data.get('education_level', 'Unknown')}."
        
        return {
            'score': min(score, 100),  # Cap at 100
            'matched_skills': matched_skills,
            'missing_skills': missing_skills,
            'explanation': explanation
        }
    
    def _ai_score(self, parsed_data: Dict, job) -> Dict:
        """AI-based scoring using Gemini"""
        
        try:
            prompt = f"""
You are an expert recruiter. Score this resume against the job requirements on a scale of 0-100.

Job Details:
Title: {job.title}
Description: {job.description}
Required Skills: {', '.join(job.skills_required or [])}
Experience Required: {job.experience_required}
Education: {job.education}

Candidate Details:
Skills: {', '.join(parsed_data.get('skills', []))}
Experience: {parsed_data.get('experience_years', 0)} years
Education: {parsed_data.get('education_level', 'Unknown')}
Projects: {len(parsed_data.get('projects', []))}
Certifications: {', '.join(parsed_data.get('certifications', []))}

Provide:
1. Overall score (0-100)
2. Matched skills (comma-separated)
3. Missing skills (comma-separated)
4. Brief explanation (2-3 sentences)

Format your response as:
SCORE: [number]
MATCHED: [skills]
MISSING: [skills]
EXPLANATION: [text]
"""
            
            response = self.model.generate_content(prompt)
            result_text = response.text
            
            # Parse AI response
            score = self._extract_value(result_text, 'SCORE:', float, 50.0)
            matched = self._extract_value(result_text, 'MATCHED:', str, '').split(',')
            missing = self._extract_value(result_text, 'MISSING:', str, '').split(',')
            explanation = self._extract_value(result_text, 'EXPLANATION:', str, 'AI scoring completed')
            
            matched_skills = [s.strip() for s in matched if s.strip()]
            missing_skills = [s.strip() for s in missing if s.strip()]
            
            return {
                'score': min(max(score, 0), 100),  # Clamp between 0-100
                'matched_skills': matched_skills,
                'missing_skills': missing_skills,
                'explanation': explanation.strip()
            }
            
        except Exception as e:
            print(f"AI scoring failed: {e}. Falling back to rule-based scoring.")
            return self._rule_based_score(parsed_data, job)
    
    def _parse_experience_requirement(self, exp_str: str) -> int:
        """Parse experience requirement string to years"""
        if not exp_str:
            return 0
        
        import re
        match = re.search(r'(\d+)', exp_str)
        return int(match.group(1)) if match else 0
    
    def _extract_value(self, text: str, key: str, value_type, default):
        """Extract value from AI response"""
        try:
            lines = text.split('\n')
            for line in lines:
                if line.startswith(key):
                    value = line.replace(key, '').strip()
                    return value_type(value)
            return default
        except:
            return default
