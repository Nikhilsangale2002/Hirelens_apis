import os
from supabase import create_client, Client
from typing import Optional, Dict, Any

class SupabaseAuth:
    """Supabase Authentication Service"""
    
    def __init__(self):
        self.url = os.getenv('SUPABASE_URL', '')
        self.key = os.getenv('SUPABASE_ANON_KEY', '')
        self.service_key = os.getenv('SUPABASE_SERVICE_KEY', '')
        
        if not self.url or not self.key:
            raise ValueError("SUPABASE_URL and SUPABASE_ANON_KEY must be set in environment")
        
        try:
            self.client: Client = create_client(self.url, self.key)
            self.admin_client: Optional[Client] = None
            
            if self.service_key:
                self.admin_client = create_client(self.url, self.service_key)
        except Exception as e:
            print(f"Failed to create Supabase client: {e}")
            raise
    
    def verify_token(self, access_token: str) -> Optional[Dict[str, Any]]:
        """Verify Supabase access token and get user info"""
        try:
            user = self.client.auth.get_user(access_token)
            return user.user.dict() if user.user else None
        except Exception as e:
            print(f"Token verification failed: {e}")
            return None
    
    def get_user_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """Get user from Supabase by email (admin only)"""
        try:
            if not self.admin_client:
                return None
            
            response = self.admin_client.auth.admin.list_users()
            users = response if isinstance(response, list) else []
            
            for user in users:
                if user.email == email:
                    return user.dict()
            return None
        except Exception as e:
            print(f"Failed to get user: {e}")
            return None
    
    def create_session_from_supabase(self, supabase_user: Dict[str, Any]) -> Dict[str, Any]:
        """Extract user info from Supabase response"""
        return {
            'id': supabase_user.get('id'),
            'email': supabase_user.get('email'),
            'name': supabase_user.get('user_metadata', {}).get('full_name', ''),
            'avatar': supabase_user.get('user_metadata', {}).get('avatar_url', ''),
            'provider': supabase_user.get('app_metadata', {}).get('provider', 'email'),
            'email_confirmed': supabase_user.get('email_confirmed_at') is not None
        }

# Global instance
supabase_auth = None

def get_supabase_auth() -> SupabaseAuth:
    """Get or create Supabase auth instance"""
    global supabase_auth
    if supabase_auth is None:
        try:
            supabase_auth = SupabaseAuth()
        except ValueError as e:
            print(f"Supabase not configured: {e}")
            return None
    return supabase_auth
