import os
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field
import httpx
from dotenv import load_dotenv
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
from langfuse.openai import AsyncOpenAI # type: ignore
from langfuse import observe

load_dotenv()


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
            "3 = Day after tomorrow / in 2 or 3 days (Max limit for free plan is 3)"
    )

@observe(name="extract_weather_search_params")
async def extract_weather_search_params(driver_command: str) -> WeatherSearchParams:
    """Extracts structured search parameters from the driver's command using LLM."""
    client = AsyncOpenAI()
    
    completion = await client.beta.chat.completions.parse(
        model="gpt-4o-mini",
        messages=[
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
        ],
        response_format=WeatherSearchParams,
        temperature=0.0
    )
    return completion.choices[0].message.parsed


async def fetch_weather_data(query: str, days: int, api_key: str) -> Dict[str, Any]:
    """Fetches weather data from WeatherAPI.com forecast endpoint."""
    url = "https://api.weatherapi.com/v1/forecast.json"
    params = {
        "key": api_key,
        "q": query,
        "days": min(max(days, 1), 3),  # capped at 3 days in the free plan
        "aqi": "no",
        "alerts": "yes",
    }

    async with httpx.AsyncClient(timeout=5.0) as client:
        response = await client.get(url, params=params)
        response.raise_for_status()
        return response.json()


class MockWeatherAgent:
    """Mock version of WeatherAgent for offline testing."""

    @observe(name="mock_weather_agent_invoke")
    async def invoke(
        self, 
        user_request: str, 
        car_lat: Optional[float] = None, 
        car_lng: Optional[float] = None,
        langfuse_trace_id: Optional[str] = None,
        langfuse_parent_observation_id: Optional[str] = None,
    ) -> str:
        return (
            "[MOCK] Weather in Warszawa: 35.3°C (feels like 33.7°C), thundery outbreaks in nearby. "
            "Wind: 14.8 km/h, visibility: 9.0 km."
        )


class WeatherAgent:
    """Sub-agent that resolves weather requests for drivers."""

    @observe(name="weather_agent_invoke")
    async def invoke(
        self, 
        user_request: str, 
        car_lat: Optional[float] = None, 
        car_lng: Optional[float] = None,
        langfuse_trace_id: Optional[str] = None,
        langfuse_parent_observation_id: Optional[str] = None,
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
                warnings.append(f"Official Weather Alert: {headline}.")

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
                max_wind_kph = day_info.get("maxwind_kph", 0)

                if min_temp <= 1 and chance_of_rain > 40:
                    warnings.append("Caution: Freezing temperatures with precipitation expected, watch out for icy roads.")
                if max_wind_kph > 50:
                    warnings.append("Caution: Strong winds expected on this day.")

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
            precip_mm = current.get("precip_mm", 0)

            if temp_c <= 1 and precip_mm > 0:
                warnings.append("Caution: Freezing temperatures with precipitation may cause icy roads.")
            if vis_km < 2.0:
                warnings.append("Caution: Low visibility ahead due to fog or mist.")
            if wind_kph > 50:
                warnings.append("Caution: High wind speeds detected.")

            base_msg = (
                    f"Weather in {city_name}: {temp_c}°C (feels like {feelslike_c}°C), {condition}. "
                    f"Wind: {wind_kph} km/h, visibility: {vis_km} km."
                )

        if warnings:
            return f"{base_msg} {' '.join(warnings)}"
        return base_msg


class WeatherAgentExecutor(AgentExecutor):
    """Handles incoming A2A requests and executes the weather query flow."""

    def __init__(self, agent: Optional[Any] = None) -> None:
        self.agent = agent if agent is not None else WeatherAgent()

    async def execute(
        self,
        context: RequestContext,
        event_queue: EventQueue,
    ) -> None:

        incoming_trace_id: Optional[str] = None
        incoming_parent_id: Optional[str] = None

        if hasattr(context.message, "metadata") and context.message.metadata:
            meta = context.message.metadata
            val_trace = None
            val_parent = None

            if hasattr(meta, "get"):
                val_trace = meta.get("langfuse_trace_id")
                val_parent = meta.get("langfuse_parent_observation_id")
            else:
                try:
                    val_trace = meta["langfuse_trace_id"]
                    val_parent = meta["langfuse_parent_observation_id"]
                except (KeyError, TypeError):
                    pass

            if val_trace is not None:
                incoming_trace_id = str(val_trace)
            if val_parent is not None:
                incoming_parent_id = str(val_parent)

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
            result = await self.agent.invoke(
                user_request=query, 
                car_lat=car_lat, 
                car_lng=car_lng,
                langfuse_trace_id=incoming_trace_id,
                langfuse_parent_observation_id=incoming_parent_id,
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