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


class GasSearchParams(BaseModel):
    use_current_location: bool = Field(
        description=(
            "True if searching for gas stations around the vehicle's current position. "
            "False if a specific target location (city, street, address, or landmark) was provided."
        )
    )
    target_location: Optional[str] = Field(
        default=None,
        description=(
            "A specific location provided by the driver to search around. "
            "Can be a city (e.g., 'London', 'Radom'), a street (e.g., 'Oxford Street', 'Marszałkowska'), "
            "or a point of interest/landmark (e.g., 'Big Ben', 'Wały Chrobrego'). "
            "Extract ONLY the location name itself. Do NOT include words like 'gas station', 'fuel', "
            "or brand names like 'Shell' or 'Orlen'. "
            "Leave as None if use_current_location is True."
        )
    )
    search_radius_meters: int = Field(
        default=3000,
        description=(
            "The search radius in meters. Convert spoken distance units (e.g., 'within 10km') "
            "to integer meters (10000). Default to 3000 if not specified by the driver."
        )
    )
    provider: Literal["google", "here"] = Field(
        default="google",
        description=(
            "The API provider to use for the search. "
            "If the driver specifically mentions 'here', 'here api' or 'here maps', set to 'here'. "
            "Otherwise, ALWAYS default to 'google'."
        )
    )

@observe(
        name="extract_gas_search_params",
        as_type="generation",
        capture_input=False,
        capture_output=False
)
async def extract_gas_search_params(driver_command: str) -> GasSearchParams:
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
                "Your sole task is to extract gas station search parameters from the driver's spoken command "
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
        response_format=GasSearchParams,
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
        raise ValueError("The model did not return valid gas search parameters.")

    return parsed

async def geocode_location_here(location: str, api_key: str) -> tuple[float, float]:
    """Converts a text location to coordinates using HERE Geocoding API."""
    url = "https://geocode.search.hereapi.com/v1/geocode"
    params = {
        "q": location,
        "apiKey": api_key
    }

    async with httpx.AsyncClient(timeout=get_external_api_timeout_seconds()) as client:
        response = await client.get(url, params=params)
        response.raise_for_status()
        data = response.json()

        if not data.get("items"):
            raise ValueError(f"Could not resolve coordinates for: '{location}'")

        position = data["items"][0]["position"]
        return position["lat"], position["lng"]


async def search_gas_here(lat: float, lng: float, radius: int, api_key: str) -> Dict[str, Any]:
    """Searches for gas/petrol stations around coordinates using HERE Browse API."""
    url = "https://browse.search.hereapi.com/v1/browse"
    params = {
        "at": f"{lat},{lng}",
        "categories": "700-7600-0116",  # HERE Category ID for Gas Stations
        "limit": 5,
        "apiKey": api_key
    }

    if radius:
        params["in"] = f"circle:{lat},{lng};r={radius}"

    async with httpx.AsyncClient(timeout=get_external_api_timeout_seconds()) as client:
        response = await client.get(url, params=params)
        response.raise_for_status()
        return response.json()

@observe(
        name="google_places_gas_search",
        as_type="tool",
        capture_input=False,
        capture_output=False
)
async def search_gas_google(
    api_key: str,
    target_location: Optional[str] = None,
    lat: Optional[float] = None,
    lng: Optional[float] = None,
    radius: Optional[int] = None,
) -> Dict[str, Any]:
    """Searches for gas stations using Google Places API (New)."""
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": "places.displayName,places.formattedAddress",
    }

    if target_location:
        url = "https://places.googleapis.com/v1/places:searchText"
        payload = {
            "textQuery": f"gas station near {target_location}",
            "includedType": "gas_station",
            "maxResultCount": 5,
        }

    elif lat is not None and lng is not None and radius is not None:
        url = "https://places.googleapis.com/v1/places:searchNearby"
        payload = {
            "includedTypes": ["gas_station"],
            "maxResultCount": 5,
            "locationRestriction": {
                "circle": {
                    "center": {"latitude": lat, "longitude": lng},
                    "radius": float(radius),
                }
            },
        }
    else:
        raise ValueError("Either target_location or coordinates (lat, lng, radius) must be provided.")

    endpoint = url.removeprefix("https://places.googleapis.com/v1/")
    span_metadata = {
        "provider": "google_places_api",
        "endpoint": endpoint,
        "http_method": "POST"
    }
    langfuse.update_current_span(input=payload, metadata=span_metadata)

    async with httpx.AsyncClient(timeout=get_external_api_timeout_seconds()) as client:
        response = await client.post(url, json=payload, headers=headers)
        langfuse.update_current_span(metadata={**span_metadata, "status_code": response.status_code})
        response.raise_for_status()
        raw_response = response.json()
        langfuse.update_current_span(output=raw_response)
        return raw_response


class MockGasStationAgent:
    """Mock version of GasStationAgent for offline testing."""

    @observe(
            name="mock_gas_agent_invoke",
            capture_input=False,
            capture_output=False
    )
    async def invoke(
        self,
        user_request: str,
        car_lat: Optional[float] = None,
        car_lng: Optional[float] = None
    ) -> tuple[TaskState, str]:

        return TaskState.TASK_STATE_COMPLETED, (
            "[MOCK] I found the following gas stations near your location:\n"
            "1. Example Fuel Station - Testowa 15, Test City, Poland\n"
            "2. Mock Fuel Point - Przykładowa 28, Test City, Poland\n"
            "3. Demo Gas Station - Testowa 63,  Test City, Poland\n"
            "4. Sample Station - Mockowa 69, Test City, Poland\n"
            "5. Test Fuel Stop - Wymyślona 29, Test City, Poland"
        )


class GasStationAgent:
    """Sub-agent that resolves constraints and fetches gas stations via Google Places API or HERE API."""

    # HERE Category ID for Gas Stations
    GAS_STATION_CATEGORY_ID = "700-7600-0116"

    @observe(
            name="gas_agent_invoke",
            capture_input=False,
            capture_output=False
    )
    async def invoke(
        self,
        user_request: str,
        car_lat: Optional[float] = None,
        car_lng: Optional[float] = None
    ) -> tuple[TaskState, str]:
        try:
            # Extract parameters using OpenAI
            search_params = await extract_gas_search_params(user_request)

            if search_params.provider == "google":
                google_api_key = os.environ.get("GOOGLE_API_KEY")
                if not google_api_key:
                    return TaskState.TASK_STATE_FAILED, "Error: GOOGLE_API_KEY environment variable is missing on the server."
                return await self._search_via_google(search_params, car_lat, car_lng, google_api_key)
            else:
                here_api_key = os.environ.get("HERE_API_KEY")
                if not here_api_key:
                    return TaskState.TASK_STATE_FAILED, "Error: HERE_API_KEY environment variable is missing on the server."
                return await self._search_via_here(search_params, car_lat, car_lng, here_api_key)

        except Exception as e:
            return TaskState.TASK_STATE_FAILED, f"An error occurred while processing the request: {str(e)}"


    async def _search_via_google(
        self,
        search_params: GasSearchParams,
        car_lat: Optional[float],
        car_lng: Optional[float],
        api_key: str,
    ) -> tuple[TaskState, str]:
        """Executes search using Google Places API."""
        if search_params.use_current_location:
            if car_lat is None or car_lng is None:
                return TaskState.TASK_STATE_INPUT_REQUIRED, "I cannot perform a local search because the vehicle's current GPS data is unavailable."
            raw_results = await search_gas_google(
                api_key=api_key,
                lat=car_lat,
                lng=car_lng,
                radius=search_params.search_radius_meters,
            )
            location_name = "your current location"
        else:
            if not search_params.target_location:
                return TaskState.TASK_STATE_INPUT_REQUIRED, "Sorry, I couldn't understand the target location for the gas station search."
            raw_results = await search_gas_google(
                api_key=api_key,
                target_location=search_params.target_location,
            )
            location_name = f"'{search_params.target_location}'"

        places = raw_results.get("places", [])

        if not places:
            return TaskState.TASK_STATE_COMPLETED, f"I couldn't find any gas stations within {search_params.search_radius_meters} meters around {location_name}."

        response_lines = [f"I found the following gas stations near {location_name}:"]
        for i, place in enumerate(places, 1):
            name = place.get("displayName", {}).get("text", "Gas Station")
            address = place.get("formattedAddress", "No address available")
            response_lines.append(f"{i}. {name} - {address}")

        return TaskState.TASK_STATE_COMPLETED, "\n".join(response_lines)


    async def _search_via_here(
        self,
        search_params: GasSearchParams,
        car_lat: Optional[float],
        car_lng: Optional[float],
        api_key: str,
    ) -> tuple[TaskState, str]:
        """Executes search using HERE API."""
        # Resolve Location to Coordinates
        if search_params.use_current_location:
            if car_lat is None or car_lng is None:
                return TaskState.TASK_STATE_INPUT_REQUIRED, "I cannot perform a local search because the vehicle's current GPS data is unavailable."
            target_lat, target_lng = car_lat, car_lng
            location_name = "your current location"
        else:
            try:
                target_lat, target_lng = await geocode_location_here(search_params.target_location, api_key)
                location_name = f"'{search_params.target_location}'"
            except Exception:
                # A place nobody can resolve: the request is short of usable
                # input rather than broken.
                return TaskState.TASK_STATE_INPUT_REQUIRED, f"Sorry, I couldn't find the location {search_params.target_location}. Please try specifying a different landmark or city."

        # Fetch Data from HERE API
        raw_results = await search_gas_here(
            lat=target_lat,
            lng=target_lng,
            radius=search_params.search_radius_meters,
            api_key=api_key
        )

        items = raw_results.get("items", [])

        filtered_items = []
        for item in items:
            categories = item.get("categories", [])

            is_primary_gas_station = any(
                cat.get("id") == self.GAS_STATION_CATEGORY_ID and cat.get("primary") is True
                for cat in categories
            )

            if is_primary_gas_station:
                filtered_items.append(item)

        items = filtered_items

        if not items:
            return TaskState.TASK_STATE_COMPLETED, f"I couldn't find any gas stations within {search_params.search_radius_meters} meters around {location_name}."

        # Format output into a clean plain text string for A2A pipeline
        response_lines = [f"I found the following gas stations near {location_name}:"]
        for i, item in enumerate(items, 1):
            name = item.get("title", "Unknown Station")
            address = item.get("address", {}).get("label", "No address available")
            distance_km = item.get("distance", 0) / 1000

            if search_params.use_current_location:
                distance_str = f"{distance_km:.2f} km away"
            else:
                distance_str = f"{distance_km:.2f} km from {location_name}"

            response_lines.append(f"{i}. {name} - {address} ({distance_str})")

        return TaskState.TASK_STATE_COMPLETED, "\n".join(response_lines)


class GasStationAgentExecutor(AgentExecutor):
    """Handles incoming A2A requests and executes the gas station search flow."""

    def __init__(self, agent: Optional[Any] = None) -> None:
        self.agent = agent if agent is not None else GasStationAgent()

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
            message=new_text_message('Processing gas station search request...'),
        )

        query = get_message_text(context.message)

        # Change this if the Orchestrator sends car GPS in a different field.
        # Currently defaults to Warsaw Center coordinates as a fallback mock.
        car_lat = getattr(context, 'car_lat', 52.2297)
        car_lng = getattr(context, 'car_lng', 21.0122)

        if query:
            with langfuse.start_as_current_observation(
                name="gas_agent_execute",
                as_type="span",
                trace_context=trace_context
            ):
                state, text = await self.agent.invoke(
                    user_request=query,
                    car_lat=car_lat,
                    car_lng=car_lng
                )
        else:
            state, text = TaskState.TASK_STATE_FAILED, 'No text input is provided!'

        await task_updater.add_artifact(
            parts=[
                new_text_part(
                    text=text,
                    media_type='text/plain'
                )
            ]
        )
        print('GasStationAgent result: ', TaskState.Name(state), text)

        await task_updater.update_status(
            state=state,
            message=new_text_message(text),
        )


    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        """Raise exception as cancel is not supported."""
        raise NotImplementedError('Cancel is not supported.')
