import os
from typing import Optional, Dict, Any, Literal
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

@observe(name="extract_gas_search_params")
async def extract_gas_search_params(driver_command: str) -> GasSearchParams:
    """Extracts structured search parameters from the driver's command using LLM."""
    client = AsyncOpenAI()
    
    completion = await client.beta.chat.completions.parse(
        model="gpt-4o-mini",
        messages=[
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
        ],
        response_format=GasSearchParams,
        temperature=0.0
    )
    return completion.choices[0].message.parsed


async def geocode_location_here(location: str, api_key: str) -> tuple[float, float]:
    """Converts a text location to coordinates using HERE Geocoding API."""
    url = "https://geocode.search.hereapi.com/v1/geocode"
    params = {
        "q": location,
        "apiKey": api_key
    }
    
    async with httpx.AsyncClient(timeout=5.0) as client:
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

    async with httpx.AsyncClient(timeout=5.0) as client:
        response = await client.get(url, params=params)
        response.raise_for_status()
        return response.json()
    

async def search_gas_google(
    api_key: str,
    target_location: Optional[str] = None,
    lat: Optional[float] = None,
    lng: Optional[float] = None,
    radius: Optional[int] = None,
) -> Dict[str, Any]:
    """Searches for gas stations using Google Places API."""
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

    async with httpx.AsyncClient(timeout=5.0) as client:
        response = await client.post(url, json=payload, headers=headers)
        response.raise_for_status()
        return response.json()


class MockGasStationAgent:
    """Mock version of GasStationAgent for offline testing."""

    @observe(name="mock_gas_agent_invoke")
    async def invoke(
        self, 
        user_request: str, 
        car_lat: Optional[float] = None, 
        car_lng: Optional[float] = None,
        langfuse_trace_id: Optional[str] = None,
        langfuse_parent_observation_id: Optional[str] = None
    ) -> str:

        return (
            "[MOCK] I found the following gas stations near your location:\n"
            "1. Orlen - Al. 3 Maja 1A, 00-401 Warszawa, Poland\n"
            "2. Petrol Station ORLEN - Grzybowska 74, 00-844 Warszawa, Poland\n"
            "3. BP - Al. Solidarności 100, 01-016 Warszawa, Poland\n"
            "4. Shell - Srebrna 9, 00-810 Warszawa, Poland\n"
            "5. Circle K - Polna 1A, 00-622 Warszawa, Poland"
        )


class GasStationAgent:
    """Sub-agent that resolves constraints and fetches gas stations via Google Places API or HERE API."""

    # HERE Category ID for Gas Stations
    GAS_STATION_CATEGORY_ID = "700-7600-0116"

    @observe(name="gas_agent_invoke")
    async def invoke(
        self, 
        user_request: str, 
        car_lat: Optional[float] = None, 
        car_lng: Optional[float] = None,
        langfuse_trace_id: Optional[str] = None,
        langfuse_parent_observation_id: Optional[str] = None
    ) -> str:
        try:
            # Extract parameters using OpenAI
            search_params = await extract_gas_search_params(user_request)

            if search_params.provider == "google":
                google_api_key = os.environ.get("GOOGLE_API_KEY")
                if not google_api_key:
                    return "Error: GOOGLE_API_KEY environment variable is missing on the server."
                return await self._search_via_google(search_params, car_lat, car_lng, google_api_key)
            else:
                here_api_key = os.environ.get("HERE_API_KEY")
                if not here_api_key:
                    return "Error: HERE_API_KEY environment variable is missing on the server."
                return await self._search_via_here(search_params, car_lat, car_lng, here_api_key)
            
        except Exception as e:
            return f"An error occurred while processing the request: {str(e)}"
    

    async def _search_via_google(
        self,
        search_params: GasSearchParams,
        car_lat: Optional[float],
        car_lng: Optional[float],
        api_key: str,
    ) -> str:
        """Executes search using Google Places API."""
        if search_params.use_current_location:
            if car_lat is None or car_lng is None:
                return "I cannot perform a local search because the vehicle's current GPS data is unavailable."
            raw_results = await search_gas_google(
                api_key=api_key,
                lat=car_lat,
                lng=car_lng,
                radius=search_params.search_radius_meters,
            )
            location_name = "your current location"
        else:
            if not search_params.target_location:
                return "Sorry, I couldn't understand the target location for the gas station search."
            raw_results = await search_gas_google(
                api_key=api_key,
                target_location=search_params.target_location,
            )
            location_name = f"'{search_params.target_location}'"

        places = raw_results.get("places", [])
        if not places:
            return f"I couldn't find any gas stations within {search_params.search_radius_meters} meters around {location_name}."

        response_lines = [f"I found the following gas stations near {location_name}:"]
        for i, place in enumerate(places, 1):
            name = place.get("displayName", {}).get("text", "Gas Station")
            address = place.get("formattedAddress", "No address available")
            response_lines.append(f"{i}. {name} - {address}")

        return "\n".join(response_lines)
    

    async def _search_via_here(
        self,
        search_params: GasSearchParams,
        car_lat: Optional[float],
        car_lng: Optional[float],
        api_key: str,
    ) -> str:
        """Executes search using HERE API."""
        # Resolve Location to Coordinates
        if search_params.use_current_location:
            if car_lat is None or car_lng is None:
                return "I cannot perform a local search because the vehicle's current GPS data is unavailable."
            target_lat, target_lng = car_lat, car_lng
            location_name = "your current location"
        else:
            try:
                target_lat, target_lng = await geocode_location_here(search_params.target_location, api_key)
                location_name = f"'{search_params.target_location}'"
            except Exception as e:
                return f"Sorry, I couldn't find the location {search_params.target_location}. Please try specifying a different landmark or city."

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
            return f"I couldn't find any gas stations within {search_params.search_radius_meters} meters around {location_name}."

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
            
        return "\n".join(response_lines)


class GasStationAgentExecutor(AgentExecutor):
    """Handles incoming A2A requests and executes the gas station search flow."""

    def __init__(self, agent: Optional[Any] = None) -> None:
        self.agent = agent if agent is not None else GasStationAgent()

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
            message=new_text_message('Processing gas station search request...'),
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
                langfuse_parent_observation_id=incoming_parent_id
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
        print('GasStationAgent result: ', result)

        await task_updater.update_status(
            state=TaskState.TASK_STATE_COMPLETED,
            message=new_text_message('Gas station request is completed!'),
        )


    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        """Raise exception as cancel is not supported."""
        raise NotImplementedError('Cancel is not supported.')