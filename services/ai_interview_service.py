"""
AI Interview Service
Handles AI-powered interview question generation and response analysis using Gemini
"""

import os
import json
import google.generativeai as genai
from typing import List, Dict, Any, Optional

class AIInterviewService:
    def __init__(self) -> None:
        """Initialize Gemini AI client"""
        self.api_key: Optional[str] = os.getenv('GEMINI_API_KEY')
        self.model_name: str = os.getenv('GEMINI_MODEL', 'gemini-1.5-flash')
        
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY not found in environment variables")
        
        genai.configure(api_key=self.api_key)
        self.model = genai.GenerativeModel(self.model_name)
    
    def _call_ai(self, prompt: str, temperature: float = 0.7) -> str:
        """
        Call Gemini AI with the given prompt
        """
        response = self.model.generate_content(
            prompt,
            generation_config={
                'temperature': temperature,
                'max_output_tokens': 8000,
            }
        )
        return response.text.strip()
    
    def generate_interview_questions(
        self, 
        job_title: str, 
        job_description: str, 
        required_skills: List[str],
        candidate_resume: Optional[str] = None,
        num_questions: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Generate AI interview questions based on job and candidate profile
        
        Args:
            job_title: The job position title
            job_description: Full job description
            required_skills: List of required skills
            candidate_resume: Optional resume text for personalized questions
            num_questions: Number of questions to generate (default: 5)
            
        Returns:
            List of question dictionaries with question, category, difficulty
        """
        
        # Build the prompt
        prompt = f"""You are an expert technical recruiter. Generate {num_questions} interview questions for the following job:

Job Title: {job_title}

Job Description:
{job_description}

Required Skills: {', '.join(required_skills)}
"""
        
        if candidate_resume:
            prompt += f"\n\nCandidate's Resume Summary:\n{candidate_resume[:1000]}"
            prompt += "\n\nGenerate questions that are tailored to this candidate's background."
        
        prompt += f"""

CRITICAL: You must respond with ONLY a valid JSON array. No explanations, no markdown, no code blocks.

Generate exactly {num_questions} interview questions as a JSON array. Each question must have:
- question: The interview question text (string)
- category: One of: "technical", "behavioral", "situational", or "cultural" (string)
- difficulty: One of: "easy", "medium", or "hard" (string)
- expected_points: List of 3-5 key points a good answer should cover (array of strings)
- max_score: Always set to 20 (number)

Example format:
[
  {{
    "question": "Describe a challenging project you worked on...",
    "category": "behavioral",
    "difficulty": "medium",
    "expected_points": ["Identified the challenge", "Described approach", "Explained outcome"],
    "max_score": 20
  }}
]

Return ONLY the JSON array, nothing else."""
        
        try:
            content = self._call_ai(prompt, temperature=0.3)
            
            print(f"=== RAW GEMINI RESPONSE ===")
            print(content)
            print(f"=== END RAW RESPONSE ===")
            
            # Extract JSON from response - handle various formats
            content = content.strip()
            
            # Remove markdown code blocks
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]
            
            content = content.strip()
            
            # Find JSON array boundaries
            if '[' in content and ']' in content:
                start = content.find('[')
                end = content.rfind(']') + 1
                content = content[start:end]
            
            # Try to fix common JSON issues
            # Replace smart quotes with regular quotes
            content = content.replace('"', '"').replace('"', '"')
            content = content.replace(''', "'").replace(''', "'")
            
            print(f"=== CLEANED JSON ===")
            print(content)
            print(f"=== END CLEANED ===")
            
            questions = json.loads(content)
            
            # Validate structure
            if not isinstance(questions, list):
                raise ValueError("Response is not a list")
            
            # Add question IDs
            for idx, q in enumerate(questions, 1):
                q['id'] = idx
                q['answer'] = None  # Placeholder for candidate's answer
                q['score'] = None   # Placeholder for AI score
            
            return questions
            
        except json.JSONDecodeError as e:
            print(f"Error parsing AI response: {e}")
            print(f"Response content: {content}")
            raise ValueError(f"Failed to parse AI response as JSON: {str(e)}")
        except Exception as e:
            print(f"Error generating questions: {e}")
            raise
    
    def analyze_answer(
        self,
        question: str,
        answer: str,
        expected_points: List[str],
        max_score: int = 20
    ) -> Dict[str, Any]:
        """
        Analyze a single answer and provide score and feedback
        
        Args:
            question: The interview question
            answer: Candidate's answer
            expected_points: Key points that should be covered
            max_score: Maximum score for this question
            
        Returns:
            Dictionary with score, feedback, and covered_points
        """
        
        prompt = f"""You are an expert interview evaluator. Analyze the following interview answer:

Question: {question}

Expected Points to Cover:
{chr(10).join(f'- {point}' for point in expected_points)}

Candidate's Answer:
{answer}

Evaluate the answer and provide:
1. A score out of {max_score} points
2. Detailed feedback on what was good and what could be improved
3. List of expected points that were covered
4. List of expected points that were missed

Respond in JSON format only:
{{
  "score": <number>,
  "feedback": "<detailed feedback>",
  "covered_points": ["point1", "point2"],
  "missed_points": ["point3"],
  "strengths": ["strength1", "strength2"],
  "improvements": ["improvement1", "improvement2"]
}}
"""
        
        try:
            content = self._call_ai(prompt, temperature=0.3)
            
            # Remove markdown code blocks if present
            if content.startswith("```json"):
                content = content[7:]
            if content.startswith("```"):
                content = content[3:]
            if content.endswith("```"):
                content = content[:-3]
            content = content.strip()
            
            analysis = json.loads(content)
            return analysis
            
        except Exception as e:
            print(f"Error analyzing answer: {e}")
            raise
    
    def analyze_complete_interview(
        self,
        questions_with_answers: List[Dict[str, Any]],
        job_title: str
    ) -> Dict[str, Any]:
        """
        Analyze complete interview and provide overall assessment
        
        Args:
            questions_with_answers: List of questions with candidate answers and scores
            job_title: The job position title
            
        Returns:
            Overall analysis with total score, recommendation, and summary
        """
        
        # Calculate overall metrics
        total_score = sum(q.get('score', 0) for q in questions_with_answers)
        max_possible = sum(q.get('max_score', 20) for q in questions_with_answers)
        percentage = (total_score / max_possible * 100) if max_possible > 0 else 0
        
        # Build summary for AI analysis
        summary = f"Job Position: {job_title}\n\n"
        summary += f"Total Score: {total_score}/{max_possible} ({percentage:.1f}%)\n\n"
        summary += "Question-by-Question Performance:\n"
        
        for idx, q in enumerate(questions_with_answers, 1):
            summary += f"\nQ{idx}. {q['question']}\n"
            summary += f"Category: {q.get('category', 'N/A')}\n"
            summary += f"Score: {q.get('score', 0)}/{q.get('max_score', 20)}\n"
            summary += f"Answer: {q.get('answer', 'N/A')[:200]}...\n"
        
        prompt = f"""You are a senior hiring manager. Based on the interview performance below, provide a comprehensive assessment:

{summary}

Provide your analysis in JSON format:
{{
  "overall_score": <total score>,
  "percentage": <percentage>,
  "recommendation": "<STRONG_HIRE|HIRE|MAYBE|NO_HIRE>",
  "summary": "<2-3 sentence overall summary>",
  "strengths": ["strength1", "strength2", "strength3"],
  "weaknesses": ["weakness1", "weakness2"],
  "decision_rationale": "<Why you recommend hire/no hire>",
  "next_steps": "<Recommended next steps>"
}}

Recommendation Guidelines:
- STRONG_HIRE: 85%+ score, excellent answers
- HIRE: 70-84% score, good answers with minor gaps
- MAYBE: 50-69% score, mixed performance, needs another round
- NO_HIRE: <50% score, significant gaps
"""
        
        try:
            content = self._call_ai(prompt, temperature=0.3)
            
            # Remove markdown code blocks
            if content.startswith("```json"):
                content = content[7:]
            if content.startswith("```"):
                content = content[3:]
            if content.endswith("```"):
                content = content[:-3]
            content = content.strip()
            
            analysis = json.loads(content)
            
            # Add calculated metrics
            analysis['total_score'] = total_score
            analysis['max_possible'] = max_possible
            analysis['questions_analyzed'] = len(questions_with_answers)
            
            return analysis
            
        except Exception as e:
            print(f"Error analyzing complete interview: {e}")
            # Return basic analysis if AI fails
            return {
                "total_score": total_score,
                "max_possible": max_possible,
                "percentage": percentage,
                "overall_score": total_score,
                "recommendation": "MAYBE" if percentage >= 50 else "NO_HIRE",
                "summary": f"Score: {total_score}/{max_possible} ({percentage:.1f}%)",
                "strengths": [],
                "weaknesses": [],
                "decision_rationale": "Automated analysis unavailable",
                "next_steps": "Manual review recommended",
                "questions_analyzed": len(questions_with_answers)
            }


# Create singleton instance
ai_interview_service = AIInterviewService()
