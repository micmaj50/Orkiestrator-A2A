import os
from typing import Any, Dict, Literal, Optional

import httpx
from a2a.helpers import (
    get_message_text,
    new_task_from_user_message,
    new_text_message,
    new_text_part,
)
from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.server.tasks import TaskUpdater
from a2a.types import TaskState
from dotenv import load_dotenv
from langfuse import get_client, observe
from openai import AsyncOpenAI  # type: ignore
from pydantic import BaseModel, Field

from config import (
    get_external_api_timeout_seconds,
    get_llm_max_output_tokens,
    get_llm_max_retries,
    get_llm_timeout_seconds,
)

load_dotenv()

langfuse = get_client()


class WeatherSearchParams(BaseModel):
    use_current_location: bool = Field(
        description=(
            "True if searching for weather conditions around the vehicle's current position. "
            "False if a specific target location (city, street, address, or landmark) was provided."
        )
    )
    target_location: Optional[str] = Field(
        default=None,
        description=(
            "A specific location provided by the driver (e.g., 'London', 'Warsaw', 'Zakopane'). "
            "Extract ONLY the location name itself. Leave as None if use_current_location is True."
        )
    )
    days: int = Field(
        default=1,
        description=
            "Total forecast days to fetch from WeatherAPI (1 to 3): "
            "1 = Today / Current weather / Right now, "
            "2 = Tomorrow / in 1 day, "
            "3 = Day after tomorrow / in 2 days"
    )

@observe(
        name="extract_weather_search_params",
        as_type="generation",
        capture_input=False,
        capture_output=False
)
async def extract_weather_search_params(driver_command: str) -> WeatherSearchParams:
    """Extracts structured search parameters from the driver's command using LLM."""
    client = AsyncOpenAI(
        timeout=get_llm_timeout_seconds(),
        max_retries=get_llm_max_retries(),
    )
    messages = [
        {
            "role": "system",
            "content": (
                "You are an NLP analysis module inside an in-car voice assistant system. "
                "Your sole task is to extract weather search parameters from the driver's spoken command "
                "and map them into the requested JSON schema."
            )
        },
        {
            "role": "user",
            "content": driver_command
        }
    ]

    completion = await client.chat.completions.parse(
        model="gpt-4o-mini",
        messages=messages,
        response_format=WeatherSearchParams,
        temperature=0.0,
        max_tokens=get_llm_max_output_tokens(),
    )

    parsed = completion.choices[0].message.parsed

    langfuse.update_current_generation(
        input=messages,
        output = parsed.model_dump(mode="json", exclude_none=True) if parsed is not None else None,
        model=completion.model,
        usage_details = completion.usage.model_dump(exclude_none=True) if completion.usage is not None else {}
    )

    if parsed is None:
        raise ValueError("The model did not return valid weather search parameters.")

    return parsed

@observe(
        name="weather_api_forecast",
        as_type="tool",
        capture_input=False,
        capture_output=False
)
async def fetch_weather_data(query: str, days: int, api_key: str) -> Dict[str, Any]:
    """Fetches weather data from WeatherAPI.com forecast endpoint."""
    url = "https://api.weatherapi.com/v1/forecast.json"
    request_params = {
        "q": query,
        "days": min(max(days, 1), 3),  # capped at 3 days in the free plan
        "aqi": "no",
        "alerts": "yes",
    }
    params = {"key": api_key, **request_params}
    span_metadata = {
        "provider": "weatherapi",
        "endpoint": "forecast.json",
        "http_method": "GET"
    }
    langfuse.update_current_span(input=request_params, metadata=span_metadata)

    async with httpx.AsyncClient(timeout=get_external_api_timeout_seconds()) as client:
        response = await client.get(url, params=params)
        langfuse.update_current_span(metadata={**span_metadata, "status_code": response.status_code})
        response.raise_for_status()
        raw_response = response.json()
        langfuse.update_current_span(output=raw_response)
        return raw_response


class MockWeatherAgent:
    """Mock version of WeatherAgent for offline testing."""

    @observe(
            name="mock_weather_agent_invoke",
            capture_input=False,
            capture_output=False
    )
    async def invoke(
        self,
        user_request: str,
        car_lat: Optional[float] = None,
        car_lng: Optional[float] = None
    ) -> str:
        return (
            "[MOCK] Weather in Test City: 23.3°C (feels like 22.7°C), partly cloudy. "
            "Wind: 14.8 km/h, visibility: 9.0 km."
        )


class WeatherAgent:
    """Sub-agent that resolves weather requests for drivers."""

    @observe(
            name="weather_agent_invoke",
            capture_input=False,
            capture_output=False
    )
    async def invoke(
        self,
        user_request: str,
        car_lat: Optional[float] = None,
        car_lng: Optional[float] = None
    ) -> str:
        try:
            search_params = await extract_weather_search_params(user_request)

            weather_api_key = os.environ.get("WEATHER_API_KEY")
            if not weather_api_key:
                return "Error: WEATHER_API_KEY environment variable is missing on the server."

            if search_params.use_current_location:
                if car_lat is None or car_lng is None:
                    return "I cannot fetch local weather because the vehicle's GPS data is unavailable."
                query = f"{car_lat},{car_lng}"
            else:
                if not search_params.target_location:
                    return "Sorry, I couldn't understand the target location for the weather query."
                query = search_params.target_location

            raw_data = await fetch_weather_data(query=query, days=search_params.days, api_key=weather_api_key)
            return self._format_weather_response(raw_data, requested_days=search_params.days)

        except Exception as e:
            return f"An error occurred while processing the weather request: {str(e)}"


    def _format_weather_response(self, data: Dict[str, Any], requested_days: int = 1) -> str:
        """Formats weather JSON data into a concise text response tailored for drivers."""
        location = data.get("location", {})
        city_name = location.get("name", "your area")

        warnings = []

        api_alerts = data.get("alerts", {}).get("alert", [])
        if api_alerts:
            headline = api_alerts[0].get("headline")
            if headline:
                warnings.append(f"Weather alert: {headline}.")

        if requested_days > 1:
            forecast_days = data.get("forecast", {}).get("forecastday", [])
            if forecast_days:
                target_day = forecast_days[-1]
                date_str = target_day.get("date", "upcoming day")
                day_info = target_day.get("day", {})

                max_temp = day_info.get("maxtemp_c", 0)
                min_temp = day_info.get("mintemp_c", 0)
                condition = day_info.get("condition", {}).get("text", "Unknown").lower()
                chance_of_rain = day_info.get("daily_chance_of_rain", 0)

                base_msg = (
                    f"Forecast for {city_name} on {date_str}: {condition} with temperatures "
                    f"between {min_temp}°C and {max_temp}°C. Chance of rain: {chance_of_rain}%."
                )

        else:
            current = data.get("current", {})
            temp_c = current.get("temp_c", 0)
            feelslike_c = current.get("feelslike_c", 0)
            condition = current.get("condition", {}).get("text", "Unknown").lower()
            wind_kph = current.get("wind_kph", 0)
            vis_km = current.get("vis_km", 10)

            base_msg = (
                    f"Weather in {city_name}: {temp_c}°C (feels like {feelslike_c}°C), {condition}. "
                    f"Wind: {wind_kph} km/h, visibility: {vis_km} km."
                )

        response_parts = [base_msg]
        response_parts.extend(warnings)

        return "\n".join(response_parts)


class WeatherAgentExecutor(AgentExecutor):
    """Handles incoming A2A requests and executes the weather query flow."""

    def __init__(self, agent: Optional[Any] = None) -> None:
        self.agent = agent if agent is not None else WeatherAgent()

    async def execute(
        self,
        context: RequestContext,
        event_queue: EventQueue,
    ) -> None:

        metadata = context.message.metadata
        trace_context = None

        if "langfuse_trace_id" in metadata and "langfuse_parent_observation_id" in metadata:
            trace_context = {
                "trace_id": metadata["langfuse_trace_id"],
                "parent_span_id": metadata["langfuse_parent_observation_id"]
            }

        if context.current_task:
            task = context.current_task
        else:
            task = new_task_from_user_message(context.message)
            await event_queue.enqueue_event(task)

        task_updater = TaskUpdater(
            event_queue=event_queue,
            task_id=task.id,
            context_id=task.context_id
        )
        await task_updater.update_status(
            state=TaskState.TASK_STATE_WORKING,
            message=new_text_message('Processing weather request...'),
        )

        query = get_message_text(context.message)

        # Change this if the Orchestrator sends car GPS in a different field.
        # Currently defaults to Warsaw Center coordinates as a fallback mock.
        car_lat = getattr(context, 'car_lat', 52.2297)
        car_lng = getattr(context, 'car_lng', 21.0122)

        if query:
            with langfuse.start_as_current_observation(
                name="weather_agent_execute",
                as_type="span",
                trace_context=trace_context
            ):
                result = await self.agent.invoke(
                    user_request=query,
                    car_lat=car_lat,
                    car_lng=car_lng
                )
        else:
            result = 'No text input is provided!'

        await task_updater.add_artifact(
            parts=[
                new_text_part(
                    text=result,
                    media_type='text/plain'
                )
            ]
        )
        print('WeatherAgent result: ', result)

        await task_updater.update_status(
            state=TaskState.TASK_STATE_COMPLETED,
            message=new_text_message('Weather request is completed!'),
        )


    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        """Raise exception as cancel is not supported."""
        raise NotImplementedError('Cancel is not supported.')
