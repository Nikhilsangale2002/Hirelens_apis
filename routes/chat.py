from flask import Blueprint, request, jsonify
import google.generativeai as genai
import os
import logging

chat_bp = Blueprint('chat', __name__)
logger = logging.getLogger(__name__)

# Configure Gemini API
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

# System context for the chatbot - More concise for better responses
SYSTEM_CONTEXT = """You are HireLens AI Assistant - a helpful, friendly AI chatbot for HireLens recruitment platform.

WHAT YOU KNOW ABOUT HIRELENS:
- Product: AI-powered hiring platform (resume screening, smart candidate ranking, AI video interviews)
- Founder & CEO: Nikhil Sangale (Owner and Founder of HireLens)
- Pricing: Starter $19.99/mo (3 jobs, 500 resumes), Pro $49.99/mo (10 jobs, 2000 resumes), Enterprise (custom pricing, unlimited)
- Contact: support@hirelens.ai, sales@hirelens.ai, Phone: +91 9075910683
- Business Hours: Mon-Fri 9am-6pm IST
- Location: Based in Pune, India
- Key Features: AI resume parsing, automated candidate ranking, AI interviews, ATS integration, real-time analytics
- Free Trial: 14-day trial available

WHAT YOU DON'T KNOW:
- Internal company details beyond the basics above - direct to support
- Technical implementation specifics beyond features - direct to tech support

HOW TO RESPOND:
✅ Answer questions directly if you know the info
✅ Be honest when you don't know - say "I don't have that specific information" then offer helpful alternatives
✅ Keep answers conversational, friendly, under 100 words
✅ For unknown details: "I don't have information about [topic], but our team can help! Contact sales@hirelens.ai or support@hirelens.ai"
✅ Never make up information
✅ Vary your responses - don't repeat yourself"""

@chat_bp.route('/chat', methods=['POST'])
def chat():
    """Handle chat messages from the chatbot"""
    try:
        data = request.get_json()
        user_message = data.get('message', '').strip()
        conversation_history = data.get('history', [])  # Get conversation history
        
        if not user_message:
            return jsonify({'error': 'Message is required'}), 400
        
        # Check if Gemini API is configured
        if not GEMINI_API_KEY:
            logger.warning("Gemini API key not configured, using fallback")
            return jsonify({
                'response': get_fallback_response(user_message)
            }), 200
        
        try:
            # Try multiple Gemini models in order of preference
            models_to_try = ['gemini-1.5-flash', 'gemini-1.5-pro', 'gemini-2.0-flash-exp']
            
            response_text = None
            last_error = None
            
            # Build conversation context from history
            conversation_text = ""
            if conversation_history:
                for msg in conversation_history[-6:]:  # Last 6 messages for context
                    role = "User" if msg.get('sender') == 'user' else "Assistant"
                    conversation_text += f"{role}: {msg.get('text', '')}\n"
            
            # Create contextual prompt
            prompt = f"""{SYSTEM_CONTEXT}

Previous conversation:
{conversation_text if conversation_text else 'No previous context'}

User's current question: {user_message}

Instructions: Answer this question directly. If you don't know something specific (like employee names, CEO, internal details), be honest and say you don't have that information, then offer to connect them with the right team. Be conversational and helpful. Keep it under 100 words."""
            
            # Try each model until one succeeds
            for model_name in models_to_try:
                try:
                    model = genai.GenerativeModel(model_name)
                    
                    # Generate response with settings for better quality
                    response = model.generate_content(
                        prompt,
                        generation_config=genai.types.GenerationConfig(
                            temperature=0.7,  # More creative but still focused
                            top_p=0.95,
                            top_k=40,
                            max_output_tokens=200,  # Concise responses
                        )
                    )
                    
                    response_text = response.text.strip()
                    logger.info(f"Successfully used model: {model_name}")
                    break  # Success, exit the loop
                except Exception as model_error:
                    last_error = model_error
                    logger.warning(f"Model {model_name} failed: {str(model_error)[:100]}")
                    continue  # Try next model
            
            if not response_text:
                # All models failed, use fallback
                raise Exception(f"All models failed. Last error: {last_error}")
            
            bot_response = response_text
            
            # Log the conversation
            logger.info(f"Chat - User: {user_message[:80]}... | Bot: {bot_response[:80]}...")
            
            return jsonify({
                'response': bot_response,
                'timestamp': '2026-01-08T00:00:00Z'
            }), 200
            
        except Exception as gemini_error:
            logger.error(f"Gemini API error: {str(gemini_error)}")
            # Fallback to predefined responses
            return jsonify({
                'response': get_fallback_response(user_message)
            }), 200
        
    except Exception as e:
        logger.error(f"Chat error: {str(e)}")
        return jsonify({'error': 'Failed to process message'}), 500


def get_fallback_response(message):
    """Generate smart fallback responses when AI is unavailable"""
    message_lower = message.lower()
    
    # CEO / Team questions
    if any(word in message_lower for word in ['ceo', 'founder', 'owner', 'who run', 'who made', 'who created', 'who built', 'nikhil']):
        return """**Nikhil Sangale** is the Founder, Owner, and CEO of HireLens! 🚀

He built HireLens to revolutionize recruitment with AI-powered hiring solutions.

Want to connect with the team?
📧 support@hirelens.ai | sales@hirelens.ai
📞 +91 9075910683"""

    # Pricing questions
    if any(word in message_lower for word in ['price', 'pricing', 'cost', 'plan', 'subscription', 'pay', 'money', '$']):
        return """💰 **Our Pricing:**

• **Starter** - $19.99/mo: 3 jobs, 500 resumes
• **Pro** - $49.99/mo: 10 jobs, 2000 resumes  
• **Enterprise** - Custom: Unlimited everything

14-day free trial available! Want to chat with sales? 
📧 sales@hirelens.ai"""

    # How it works
    elif any(word in message_lower for word in ['work', 'how', 'what', 'feature', 'do', 'does']):
        return """🚀 **HireLens in 4 steps:**

1. Post your job with requirements
2. Upload resumes (or connect ATS)
3. AI screens & ranks candidates automatically
4. Review top matches with detailed insights

We save you 80% of screening time! Want a demo?"""

    # AI/Interview features
    elif any(word in message_lower for word in ['ai', 'interview', 'video', 'automation', 'smart', 'intelligent']):
        return """🤖 **AI Features:**

✅ Smart resume parsing & analysis
✅ Automated candidate ranking
✅ AI-powered video interviews
✅ Skills matching & gap analysis
✅ Real-time insights & reports

The AI learns from your hiring patterns. Interested in a demo?"""

    # Contact/Support
    elif any(word in message_lower for word in ['contact', 'support', 'help', 'talk', 'human', 'call', 'speak', 'email']):
        return """📞 **Get in touch:**

• **Email**: support@hirelens.ai (fastest!)
• **Sales**: sales@hirelens.ai
• **Phone**: +91 9075910683
• **Hours**: Mon-Fri, 9am-6pm IST

We typically respond within 2 hours. What do you need help with?"""

    # Getting started
    elif any(word in message_lower for word in ['start', 'begin', 'sign up', 'register', 'trial', 'demo', 'try']):
        return """🎯 **Get Started:**

1. Sign up at hirelens.ai (free trial)
2. Create your first job
3. Upload resumes
4. Watch AI work its magic!

No credit card needed for trial. Want me to connect you with our team for a personalized demo?"""

    # Resume/screening
    elif any(word in message_lower for word in ['resume', 'cv', 'screen', 'candidate', 'applicant']):
        return """📄 **Resume Screening:**

Our AI reads resumes like a human recruiter:
• Extracts skills, experience, education
• Matches against job requirements
• Scores candidates objectively
• Finds hidden gems you might miss

Handles PDFs, Word docs, and more. Want to see it in action?"""

    # Integration
    elif any(word in message_lower for word in ['integrat', 'ats', 'api', 'connect', 'sync']):
        return """🔗 **Integrations:**

We integrate with popular ATS platforms and offer:
• REST API for custom integrations
• Webhook support for real-time updates
• CSV import/export
• Email forwarding for auto-parsing

Need specific integration? Email sales@hirelens.ai"""

    # Benefits/why
    elif any(word in message_lower for word in ['why', 'benefit', 'better', 'advantage', 'save']):
        return """✨ **Why HireLens?**

⚡ Save 80% of screening time
🎯 Reduce bias with objective AI scoring
💡 Never miss qualified candidates
📊 Data-driven hiring decisions
🚀 Faster time-to-hire

Try free for 14 days and see the difference!"""

    # Default response
    else:
        return """👋 I'm here to help! I can answer questions about:

• 💰 Pricing & plans
• 🎯 How HireLens works
• 🤖 AI features
• 📞 Support & demos
• 🚀 Getting started

What would you like to know?"""


@chat_bp.route('/chat/health', methods=['GET'])
def chat_health():
    """Health check endpoint for chat service"""
    return jsonify({
        'status': 'healthy',
        'ai_available': GEMINI_API_KEY is not None
    }), 200
