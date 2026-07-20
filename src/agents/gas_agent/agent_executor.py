import os
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field
from openai import AsyncOpenAI
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


async def geocode_location(location: str, api_key: str) -> tuple[float, float]:
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


async def browse_gas_stations(lat: float, lng: float, radius: int, api_key: str) -> Dict[str, Any]:
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


class GasStationAgent:
    """Sub-agent that resolves constraints and fetches real gas stations via HERE API."""

    # HERE Category ID for Gas Stations
    GAS_STATION_CATEGORY_ID = "700-7600-0116"

    async def invoke(self, user_request: str, car_lat: Optional[float] = None, car_lng: Optional[float] = None) -> str:
        here_api_key = os.environ.get("HERE_API_KEY")
        if not here_api_key:
            return "Error: HERE_API_KEY environment variable is missing on the server."

        try:
            # Extract parameters using OpenAI
            search_params = await extract_gas_search_params(user_request)
            
            # Resolve Location to Coordinates
            if search_params.use_current_location:
                if car_lat is None or car_lng is None:
                    return "I cannot perform a local search because the vehicle's current GPS data is unavailable."
                target_lat, target_lng = car_lat, car_lng
                location_name = "your current location"
            else:
                try:
                    target_lat, target_lng = await geocode_location(search_params.target_location, here_api_key)
                    location_name = f"'{search_params.target_location}'"
                except Exception as e:
                    return f"Sorry, I couldn't find the location {search_params.target_location}. Please try specifying a different landmark or city."

            # Fetch Data from HERE API
            raw_results = await browse_gas_stations(
                lat=target_lat, 
                lng=target_lng, 
                radius=search_params.search_radius_meters, 
                api_key=here_api_key
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

        except Exception as e:
            return f"An error occurred while processing the request: {str(e)}"


class GasStationAgentExecutor(AgentExecutor):
    """Handles incoming A2A requests and executes the gas station search flow."""

    def __init__(self) -> None:
        self.agent = GasStationAgent()

    async def execute(
        self,
        context: RequestContext,
        event_queue: EventQueue,
    ) -> None:

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
        
        car_lat = getattr(context, 'car_lat', 52.2297)
        car_lng = getattr(context, 'car_lng', 21.0122)

        if query:
            result = await self.agent.invoke(user_request=query, car_lat=car_lat, car_lng=car_lng)
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