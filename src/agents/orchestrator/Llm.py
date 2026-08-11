import os
from typing import Any

from langchain_core.output_parsers import JsonOutputParser, StrOutputParser
from langchain_core.prompts import BasePromptTemplate
from langchain_openai import ChatOpenAI
from langfuse.langchain import CallbackHandler


#callable LLM class
class Llm:

    def __init__(self):
        self.llm = ChatOpenAI(
            model="gpt-4o-mini",
            api_key = os.environ["OPENAI_API_KEY"] # type: ignore
        )


    def __call__(self, prompt: BasePromptTemplate, inputs: dict[str, Any], asJSON: bool) -> dict | str:

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
        chain = prompt | self.llm | parser

        langfuse_handler = CallbackHandler()

        return chain.invoke(inputs, config={"callbacks": [langfuse_handler]})
