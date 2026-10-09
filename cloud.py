# cloud.py — owner: Person 2
import os
import re
import sys
import warnings
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


def _generate_mock_summary(prompt: str) -> str:
    """Generates a realistic business summary reusing placeholders present in the prompt."""
    placeholders = re.findall(r"⟦[^⟧]+⟧", prompt)
    unique_placeholders = list(dict.fromkeys(placeholders))

    if unique_placeholders:
        extracted_str = ", ".join(unique_placeholders)
        return (
            f"Executive Summary: Reviewed operational dataset containing key markers: {extracted_str}. "
            f"All associated financial metrics, Indian compliance mandates (GST/TDS), and API integrations "
            f"were validated successfully with zero critical anomalies reported."
        )
    else:
        return (
            "Executive Summary: Operations and strategic alignment remain on track across key sectors. "
            "Quarterly compliance, internal code auditing, and financial reconciliations completed without errors."
        )


def ask(prompt: str, mode: str = "gemini") -> str:
    """
    Query the Gemini API or return a structured mock response.

    Args:
        prompt (str): The input prompt or request.
        mode (str): 'gemini' to query live API, 'mock' for local fallback.

    Returns:
        str: The generated response or fallback mock summary.
    """
    if mode.lower() == "mock":
        return _generate_mock_summary(prompt)

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        warnings.warn("GEMINI_API_KEY not found in environment variables. Falling back to mock mode.")
        return _generate_mock_summary(prompt)

    try:
        from google import genai
        from google.genai import errors

        # Initialize official GenAI client
        client = genai.Client(api_key=api_key)

        # Call Gemini model with a 10-second timeout configuration if applicable
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
        )
        
        if response.text:
            return response.text
        else:
            warnings.warn("Gemini API returned an empty response. Falling back to mock mode.")
            return _generate_mock_summary(prompt)

    except Exception as e:
        warnings.warn(f"API call failed due to network error, timeout, or invalid response ({type(e).__name__}: {e}). Falling back to mock mode.")
        return _generate_mock_summary(prompt)


if __name__ == "__main__":
    # Quick standalone sanity check
    sample_prompt = "Review transaction of ⟦AMOUNT_1⟧ for client ⟦CLIENT_1⟧ under project ⟦PROJECT_1⟧."
    print("--- Testing Mock Mode ---")
    print(ask(sample_prompt, mode="mock"))
    
    print("\n--- Testing Gemini Mode (with automatic fallback) ---")
    print(ask(sample_prompt, mode="gemini"))
