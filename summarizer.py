import logging

from google import genai
from google.genai import errors as genai_errors
from prompts import SUMMARIZATION_PROMPT_TEMPLATE

logger = logging.getLogger(__name__)


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


async def summarize(
    client: genai.Client,
    model_name: str,
    text: str,
    *,
    langfuse_client=None,
    url: str = "",
) -> tuple[str | None, str | None, str | None]:
    """
    Summarize text using Gemini.
    Returns (summary, error_message, trace_id); summary and error are mutually exclusive.
    trace_id is None when Langfuse is disabled or tracing failed.
    """
    prompt = SUMMARIZATION_PROMPT_TEMPLATE.format(text=text[:30000])

    # Set up Langfuse tracing (failures are isolated — summarization proceeds regardless)
    trace_id = None
    generation = None
    if langfuse_client:
        try:
            trace_id = langfuse_client.create_trace_id()
            logger.info(f"Langfuse trace started: trace_id={trace_id} url={url!r}")
            generation = langfuse_client.start_generation(
                trace_context={"trace_id": trace_id},
                name="gemini-generate",
                model=model_name,
                input=prompt,
                metadata={"url": url},
            )
        except Exception as e:
            logger.warning(f"Langfuse tracing setup failed: {e}")
            trace_id = None
            generation = None

    try:
        response = await client.aio.models.generate_content(model=model_name, contents=prompt)
        summary = response.text
        if generation:
            try:
                generation.update(output=summary)
                generation.end()
                logger.info(f"Langfuse generation ended successfully: trace_id={trace_id}")
            except Exception as e:
                logger.warning(f"Langfuse generation end failed: {e}")
                trace_id = None
        return summary, None, trace_id
    except (genai_errors.ServerError, genai_errors.ClientError) as e:
        error = _format_error(e)
        if generation:
            try:
                generation.update(level="ERROR", status_message=error)
                generation.end()
                logger.info(f"Langfuse generation ended with error: trace_id={trace_id}")
            except Exception as ex:
                logger.warning(f"Langfuse generation error-end failed: {ex}")
        return None, error, None
    except Exception as e:
        error = f"Unexpected error: {str(e)}"
        if generation:
            try:
                generation.update(level="ERROR", status_message=error)
                generation.end()
                logger.info(f"Langfuse generation ended with unexpected error: trace_id={trace_id}")
            except Exception as ex:
                logger.warning(f"Langfuse generation error-end failed: {ex}")
        return None, error, None
