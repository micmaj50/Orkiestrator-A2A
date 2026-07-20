from typing import Union,Dict,Any
from langchain_openai import ChatOpenAI
from langchain_core.prompts import BasePromptTemplate
from langchain_core.output_parsers import JsonOutputParser, StrOutputParser


#callable LLM class
class Llm:

    def __init__(self):
        # api_key is read from the OPENAI_API_KEY environment variable,
        # matching the convention used by the gas/food agents (AsyncOpenAI()).
        self.llm = ChatOpenAI(model="gpt-4o-mini")


    def __call__(self, prompt: BasePromptTemplate, inputs: Dict[str, Any], asJSON: bool) -> Union[dict, str]:

        """
        executes a merged prompt


        
        Parameters
        ----------
        prompt : BasePromptTemplate
            An unformatted prompt template (e.g., PromptTemplate, ChatPromptTemplate).
        inputs : Dict[str, Any]
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
        return chain.invoke(inputs)