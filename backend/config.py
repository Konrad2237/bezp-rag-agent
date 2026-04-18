import os
from supabase import create_client, Client
from openai import OpenAI
import anthropic

# Supabase
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY")

# AI
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

# Klienty
supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
# Osobny klient do operacji DB — nigdy nie dotykamy auth na nim, żeby nie stracić service role
supabase_admin: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
openai_client = OpenAI(api_key=OPENAI_API_KEY)
claude_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
