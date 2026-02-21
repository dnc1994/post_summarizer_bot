from google import genai
from google.genai import errors as genai_errors
from prompts import SUMMARIZATION_PROMPT_TEMPLATE


def _format_error(e: Exception) -> str:
    if isinstance(e, genai_errors.ServerError):
        if e.code == 503 or "overloaded" in str(e).lower():
            return "The Gemini model is currently overloaded. Please retry in a moment."
        return f"Gemini server error ({e.code}): {e.message}"
    if isinstance(e, genai_errors.ClientError):
        if e.code == 429 or "quota" in str(e).lower() or "rate" in str(e).lower():
            return "Gemini API quota or rate limit exceeded. Please try again later."
        return f"Gemini client error ({e.code}): {e.message}"
    return f"Gemini error: {str(e)}"


async def summarize(client: genai.Client, model_name: str, text: str) -> tuple[str | None, str | None]:
    """
    Summarize text using Gemini. Returns (summary, error_message); exactly one is None.

    Future: add a `logging_callback` parameter here to integrate with Langfuse or
    another observability service. Call it after the API response with the prompt,
    response/error, latency, and URL metadata.
    """
    prompt = SUMMARIZATION_PROMPT_TEMPLATE.format(text=text[:30000])
    try:
        response = await client.aio.models.generate_content(model=model_name, contents=prompt)
        return response.text, None
    except (genai_errors.ServerError, genai_errors.ClientError) as e:
        return None, _format_error(e)
    except Exception as e:
        return None, f"Unexpected error: {str(e)}"
