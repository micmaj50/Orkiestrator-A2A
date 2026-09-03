import os
from typing import Any

from langchain_core.output_parsers import JsonOutputParser, StrOutputParser
from langchain_core.prompts import BasePromptTemplate
from langchain_openai import ChatOpenAI
from langfuse import get_client, observe

from config import (
    get_llm_max_output_tokens,
    get_llm_max_retries,
    get_llm_timeout_seconds,
)

MODEL = "gpt-4o-mini"
langfuse = get_client()

#callable LLM class
class Llm:

    def __init__(self):
        self.llm = ChatOpenAI(
            model=MODEL,
            api_key = os.environ["OPENAI_API_KEY"], # type: ignore
            timeout=get_llm_timeout_seconds(),
            max_retries=get_llm_max_retries(),
            max_completion_tokens=get_llm_max_output_tokens(),
        )

    @observe(
            name="llm_generation",
            as_type="generation",
            capture_input=False,
            capture_output=False
    )
    def __call__(self, prompt: BasePromptTemplate, inputs: dict[str, Any], asJSON: bool, observation_name: str) -> dict | str:

        """
        executes a merged prompt



        Parameters
        ----------
        prompt : BasePromptTemplate
            An unformatted prompt template (e.g., PromptTemplate, ChatPromptTemplate).
        inputs : dict[str, Any]
            A dictionary containing the keys and values to format into the template.
        asJSON : bool
            A flag indicating whether to parse and return the output as a dictionary (True)
            or as a plain string (False).

        Returns
        -------
        Union[dict, str]
            The processed model response, returned as either a parsed dictionary or a string.
        """


        parser = JsonOutputParser() if asJSON else StrOutputParser()
        prompt_value = prompt.invoke(inputs)
        response = self.llm.invoke(prompt_value)
        parsed_response = parser.invoke(response)

        langfuse.update_current_generation(
            name=observation_name,
            input=prompt_value.to_string(),
            output=parsed_response,
            model=response.response_metadata.get("model_name", MODEL),
            usage_details=response.response_metadata.get("token_usage") or None
        )

        return parsed_response
