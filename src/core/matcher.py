import json
import os
import re
import time
from typing import Tuple, Optional, List
from google import genai
from pydantic import BaseModel, Field
from core import config

try:
    from groq import Groq
    HAS_GROQ = True
except ImportError:
    HAS_GROQ = False

class EligibilityVerdict(BaseModel):
    is_egypt_eligible: bool
    gpa_requirement_met: str = Field(description="Yes (Needs <= 3.0) | Borderline | Unknown")
    language_barrier: str = Field(description="None | IELTS Mandatory | English Certificate Accepted")

class OpportunityExtraction(BaseModel):
    match_score: int = Field(description="Score from 0 to 100 based on fit to the Applicant Profile.")
    category: str = Field(description="One of: Red (disqualified), Yellow (maybe/requires effort), Green (perfect fit)")
    opportunity_title: str = Field(description="Name of the scholarship or position")
    opportunity_type: str = Field(description="E.g., MSc, PhD, Postdoc, Internship, Short Course")
    institution_or_country: str = Field(description="University or country offering it")
    deadline: str = Field(description="Application deadline, or 'Unspecified'")
    funding_status: str = Field(description="E.g., Fully Funded, Partially Funded, Self Funded")
    fields_of_study: list[str] = Field(description="List of eligible fields")
    application_link: str = Field(description="URL or contact email if present, else 'Unspecified'")
    reasoning: str = Field(description="Brief 2-sentence rationale for the score")
    action_items: str = Field(description="Immediate next step")

# Track current active key index to minimize churn
_active_groq_idx = 0
_active_gemini_idx = 0

def mask_key(k: str) -> str:
    if not k or len(k) < 8:
        return "invalid_key"
    return f"{k[:4]}...{k[-4:]}"

def get_groq_keys() -> List[str]:
    keys = getattr(config, "GROQ_API_KEYS", None)
    if keys and isinstance(keys, list):
        return [k.strip() for k in keys if k and k.strip()]
    single = getattr(config, "GROQ_API_KEY", None) or os.getenv("GROQ_API_KEY")
    return [single.strip()] if single and single.strip() else []

def get_gemini_keys() -> List[str]:
    keys = getattr(config, "GEMINI_API_KEYS", None)
    if keys and isinstance(keys, list):
        return [k.strip() for k in keys if k and k.strip()]
    single = getattr(config, "GEMINI_API_KEY", None) or os.getenv("GEMINI_API_KEY")
    return [single.strip()] if single and single.strip() else []

def clean_scholarship_text(text: str, max_chars: int = 10000) -> str:
    """
    Safely strips pure web boilerplate (cookie banners, share buttons, comment forms)
    while strictly preserving 100% of scholarship information (eligibility, funding,
    fields, dates, requirements).
    """
    if not text:
        return ""
        
    cleaned = text
    
    # Strip common web noise patterns that contain zero scholarship content
    garbage_patterns = [
        r'Share this:.*?(?:\n|$)',
        r'Share on (Facebook|Twitter|WhatsApp|LinkedIn|Pinterest).*?(?:\n|$)',
        r'Leave a Reply[\s\S]*?(?:Required fields are marked \*|Submit Comment)?',
        r'Your email address will not be published\.',
        r'Cookie Policy.*?Privacy Policy',
        r'We use cookies to ensure you get the best experience.*?(?:Accept|Got it|Decline)',
        r'Follow us on (Facebook|Twitter|Instagram|Telegram|YouTube).*?(?:\n|$)',
        r'Related Posts[\s\S]*?(?:Previous Post|Next Post)?'
    ]
    for pattern in garbage_patterns:
        cleaned = re.sub(pattern, '', cleaned, flags=re.IGNORECASE)
        
    # Collapse repeated whitespace and excessive blank lines
    cleaned = re.sub(r'\n{3,}', '\n\n', cleaned)
    cleaned = cleaned.strip()
    
    # Generous safety ceiling (10,000 characters = ~2,500 words / ~2,000 tokens)
    # This easily fits any full scholarship page, but prevents 50KB runaway HTML dumps
    if len(cleaned) > max_chars:
        cleaned = cleaned[:max_chars] + "\n... [End of scholarship details]"
        
    return cleaned

def evaluate_opportunity(message_text: str, max_retries=2) -> Tuple[Optional[OpportunityExtraction], Optional[str]]:
    global _active_groq_idx, _active_gemini_idx
    
    # Safely clean web noise while preserving 100% of academic/funding information
    message_text = clean_scholarship_text(message_text)
    
    # 1. Local Ollama Check
    if getattr(config, "USE_OLLAMA", False):
        print("  [Matcher] Engine: Local Ollama")
        return evaluate_with_ollama(message_text, max_retries)
        
    groq_keys = get_groq_keys()
    gemini_keys = get_gemini_keys()
    
    # Priority 1: Groq LPUs with multi-key cycling pool
    if groq_keys and HAS_GROQ:
        num_keys = len(groq_keys)
        # Try each key in the pool starting from the active index
        for attempt_offset in range(num_keys):
            idx = (_active_groq_idx + attempt_offset) % num_keys
            api_key = groq_keys[idx]
            
            print(f"  [AI Engine] Groq LPU 120B | Key {idx+1}/{num_keys} ({mask_key(api_key)})")
            opp, err = evaluate_with_groq(message_text, api_key, max_retries=max_retries)
            
            if opp:
                _active_groq_idx = idx # Stick to this healthy key
                print(f"  [Match Result] Score: {opp.match_score}/100 [{opp.category}] | Title: {opp.opportunity_title[:50]}")
                time.sleep(1.5) # Safe rate-pacing to prevent TPM burst limit
                return opp, None
                
            # If 429 / quota limit exceeded, rotate to next key
            if err and ("429" in err or "quota" in err.lower() or "limit" in err.lower()):
                print(f"  [!] Groq Key {idx+1}/{num_keys} ({mask_key(api_key)}) hit daily/minute quota.")
                if attempt_offset < num_keys - 1:
                    print(f"  🔄 Cycling to next available Groq key...")
                continue
            else:
                # If non-quota error (e.g. malformed input), don't blame the key alone
                print(f"  [!] Groq evaluation error: {err}")
                
        print("  [!] All Groq keys in rotation pool exhausted. Seamlessly cascading to Gemini API...")
        
    # Priority 2: Gemini with multi-key cycling pool
    if gemini_keys:
        num_gemini = len(gemini_keys)
        for g_offset in range(num_gemini):
            g_idx = (_active_gemini_idx + g_offset) % num_gemini
            api_key = gemini_keys[g_idx]
            
            print(f"  [AI Engine] Gemini Fallback | Key {g_idx+1}/{num_gemini} ({mask_key(api_key)})")
            opp, err = evaluate_with_gemini(message_text, api_key, max_retries=max_retries)
            
            if opp:
                _active_gemini_idx = g_idx
                print(f"  [Match Result] Score: {opp.match_score}/100 [{opp.category}] | Title: {opp.opportunity_title[:50]}")
                time.sleep(1.5) # Safe rate-pacing to prevent TPM burst limit
                return opp, None
                
            if err and ("429" in err or "503" in err or "quota" in err.lower()):
                print(f"  [!] Gemini Key {g_idx+1}/{num_gemini} reached rate limit. Cycling...")
                continue
                
        return None, "All Groq and Gemini API keys exhausted."
    else:
        return None, "No API keys configured."

def evaluate_with_ollama(message_text: str, max_retries=2) -> Tuple[Optional[OpportunityExtraction], Optional[str]]:
    import urllib.request
    
    url = "http://localhost:11434/api/chat"
    schema_json = json.dumps(OpportunityExtraction.model_json_schema(), indent=2)
    model_name = getattr(config, "OLLAMA_MODEL", "llama3.1")
    
    prompt = f"""
    You are an expert AI scholarship and opportunity matcher.
    Analyze the forwarded message about a scholarship or academic opportunity.
    Extract the metadata and evaluate it against the Applicant Profile below.
    
    Applicant Profile:
    {config.APPLICANT_PROFILE}
    
    Scoring Rules for match_score (0-100):
    * +40 pts: Field matches Theoretical, HEP, Astro, Plasma, or Computational Physics.
    * +30 pts: 100% Fully Funded (Stipend + Tuition + Airfare).
    * +15 pts: GPA requirement is <= 3.1 or not strictly screened.
    * +15 pts: Open to Egyptian / non-EU nationals.
    * Disqualifiers (Score set to 0): Strictly self-funded, ineligible nationality, requires completed Master's degree for a PhD, or unrelated field (e.g. accounting, civil engineering).

    Output MUST be valid JSON exactly matching this schema:
    {schema_json}
    
    Message to Analyze:
    {message_text}
    """
    
    data = {
        "model": model_name,
        "messages": [{"role": "user", "content": prompt}],
        "format": "json",
        "stream": False,
        "options": {"temperature": 0.1}
    }
    
    req = urllib.request.Request(url, json.dumps(data).encode('utf-8'), headers={'Content-Type': 'application/json'})
    
    last_error = ""
    for attempt in range(max_retries):
        try:
            with urllib.request.urlopen(req, timeout=40) as response:
                result = json.loads(response.read().decode())
                content = result['message']['content'].strip()
                if content.startswith("```json"): content = content[7:]
                if content.startswith("```"): content = content[3:]
                if content.endswith("```"): content = content[:-3]
                return OpportunityExtraction.model_validate_json(content.strip()), None
        except Exception as e:
            last_error = str(e)
            if "10061" in last_error or "refused" in last_error:
                return None, "Ollama connection refused. Is Ollama running?"
            time.sleep(2)
            
    return None, f"Ollama failed: {last_error}"

def evaluate_with_groq(message_text: str, api_key: str, max_retries=2) -> Tuple[Optional[OpportunityExtraction], Optional[str]]:
    try:
        client = Groq(api_key=api_key)
    except Exception as e:
        return None, f"Groq client init failed: {e}"
        
    schema_json = json.dumps(OpportunityExtraction.model_json_schema(), indent=2)
    
    prompt = f"""
    You are an expert AI scholarship and opportunity matcher.
    Analyze the forwarded message about a scholarship or academic opportunity.
    Extract the metadata and evaluate it against the Applicant Profile below.
    
    Applicant Profile:
    {config.APPLICANT_PROFILE}
    
    Scoring Rules for match_score (0-100):
    * +40 pts: Field matches Theoretical, HEP, Astro, Plasma, or Computational Physics.
    * +30 pts: 100% Fully Funded (Stipend + Tuition + Airfare).
    * +15 pts: GPA requirement is <= 3.1 or not strictly screened.
    * +15 pts: Open to Egyptian / non-EU nationals.
    * Disqualifiers (Score set to 0): Strictly self-funded, ineligible nationality, requires completed Master's degree for a PhD, or unrelated field (e.g. accounting, civil engineering).

    Output MUST be valid JSON exactly matching this schema:
    {schema_json}
    
    Message to Analyze:
    {message_text}
    """
    
    last_error = ""
    for attempt in range(max_retries):
        try:
            completion = client.chat.completions.create(
                model="openai/gpt-oss-120b",
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"}
            )
            content = completion.choices[0].message.content.strip()
            
            if content.startswith("```json"): content = content[7:]
            if content.startswith("```"): content = content[3:]
            if content.endswith("```"): content = content[:-3]
                
            return OpportunityExtraction.model_validate_json(content.strip()), None
        except Exception as e:
            last_error = str(e)
            # If 429 / quota exceeded, break immediately to let key rotation take over
            if "429" in last_error or "limit" in last_error.lower():
                return None, last_error
            time.sleep(2)
            
    return None, last_error

def evaluate_with_gemini(message_text: str, api_key: str, max_retries=2) -> Tuple[Optional[OpportunityExtraction], Optional[str]]:
    import warnings
    warnings.filterwarnings("ignore", message=".*automatic function calling.*")
    
    try:
        client = genai.Client(api_key=api_key)
    except Exception as e:
        return None, f"Gemini client init failed: {e}"
        
    prompt = f"""
    You are an expert AI scholarship and opportunity matcher.
    Your task is to analyze the following forwarded message about a scholarship or academic opportunity.
    Extract the metadata and evaluate it against the Applicant Profile below.
    
    Applicant Profile:
    {config.APPLICANT_PROFILE}
    
    Scoring Rules for match_score (0-100):
    * +40 pts: Field matches Theoretical, HEP, Astro, Plasma, or Computational Physics.
    * +30 pts: 100% Fully Funded (Stipend + Tuition + Airfare).
    * +15 pts: GPA requirement is <= 3.1 or not strictly screened.
    * +15 pts: Open to Egyptian / non-EU nationals.
    * Disqualifiers (Score set to 0): Strictly self-funded, ineligible nationality, requires completed Master's degree for a PhD, or unrelated field (e.g. accounting, civil engineering).

    Message to Analyze:
    {message_text}
    """
    
    candidate_models = ['gemini-3.6-flash', 'gemini-3.5-flash-lite', 'gemini-3.5-flash', 'gemini-3-flash-preview']
    last_error = ""
    
    for model_name in candidate_models:
        for attempt in range(max_retries):
            try:
                response = client.models.generate_content(
                    model=model_name,
                    contents=prompt,
                    config={
                        'response_mime_type': 'application/json',
                        'response_schema': OpportunityExtraction,
                    },
                )
                return OpportunityExtraction.model_validate_json(response.text), None
            except Exception as e:
                last_error = str(e)
                if "503" in last_error or "429" in last_error:
                    if attempt < max_retries - 1:
                        print(f"    [Gemini {model_name}] Busy / Rate limit. Waiting 5s before model retry...")
                        time.sleep(5)
                        continue
                    else:
                        break # Switch to next candidate model
                else:
                    return None, last_error
                    
    return None, last_error
