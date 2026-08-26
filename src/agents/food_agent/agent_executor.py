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
from openai import AsyncOpenAI # type: ignore
from langfuse import observe, get_client

load_dotenv()

langfuse = get_client()


class FoodSearchParams(BaseModel):
    use_current_location: bool = Field(
        description=(
            "True if searching for restaurants near the vehicle's current position. "
            "False if a specific target location (city, street, address, or landmark) was provided."
        )
    )
    target_location: Optional[str] = Field(
        default=None, 
        description=(
            "A specific location provided by the driver to search around. "
            "Can be a city (e.g., 'London', 'Warszawa'), a street (e.g., 'Krakowskie Przedmieście'), "
            "or a point of interest/landmark (e.g., 'Neptun Monument', 'Pałac Kultury'). "
            "Extract ONLY the location name itself. Do NOT include words like 'restaurant', 'food', 'dinner', "
            "or specific food types like 'sushi' or 'pizza'. "
            "Leave as None if use_current_location is True."
        )
    )
    search_radius_meters: int = Field(
        default=3000, 
        description=(
            "The search radius in meters. Convert spoken distance units (e.g., 'within 5km') "
            "to integer meters (5000). Default to 3000 if not specified by the driver."
        )
    )
    cuisine_or_type: Optional[str] = Field(
        default=None,
        description=(
            "The specific type of food, cuisine, or restaurant style requested by the driver "
            "(e.g., 'sushi', 'italian', 'pizza', 'burgers', 'vegan', 'chinese', 'kebab', 'fast food'). "
            "Extract only the raw category name. "
            "Leave as None if the user is asking for general food/restaurants without a specific preference."
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
        name="extract_food_search_params",
        as_type="generation",
        capture_input=False,
        capture_output=False
)
async def extract_food_search_params(driver_command: str) -> FoodSearchParams:
    """Extracts structured search parameters from the driver's command using LLM."""
    client = AsyncOpenAI()
    messages = [
        {
            "role": "system", 
            "content": (
                "You are an NLP analysis module inside an in-car voice assistant system. "
                "Your sole task is to extract food and restaurant search parameters "
                "from the driver's spoken command and map them into the requested JSON schema."
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
        response_format=FoodSearchParams,
        temperature=0.0
    )
    
    parsed = completion.choices[0].message.parsed

    langfuse.update_current_generation(
        input=messages,
        output = parsed.model_dump(mode="json", exclude_none=True) if parsed is not None else None,
        model=completion.model,
        usage_details = completion.usage.model_dump(exclude_none=True) if completion.usage is not None else {}
    )

    if parsed is None:
        raise ValueError("The model did not return valid food search parameters.")

    return parsed


async def geocode_location_here(location: str, api_key: str) -> tuple[float, float]:
    """Converts a text location to coordinates using HERE Geocoding API."""
    url = "https://geocode.search.hereapi.com/v1/geocode"
    params = {
        "q": location,
        "apiKey": api_key
    }
    
    async with httpx.AsyncClient() as client:
        response = await client.get(url, params=params)
        response.raise_for_status()
        data = response.json()
        
        if not data.get("items"):
            raise ValueError(f"Could not resolve coordinates for: '{location}'")
            
        position = data["items"][0]["position"]
        return position["lat"], position["lng"]


async def search_food_here(lat: float, lng: float, query_text: Optional[str], api_key: str) -> Dict[str, Any]:
    """
    Searches for restaurants around coordinates using HERE Discover API.
    """
    url = "https://discover.search.hereapi.com/v1/discover"
    params = {
        "at": f"{lat},{lng}",
        #"categories": "100",  # HERE Eat & Drink category
        "limit": 5,
        "apiKey": api_key
    }
    
    # If the driver specified a food type (e.g., sushi), pass it to HERE
    # Otherwise, default to searching for "restaurant"
    params["q"] = query_text if query_text else "restaurant"

    async with httpx.AsyncClient() as client:
        response = await client.get(url, params=params)
        response.raise_for_status()
        return response.json()

@observe(
        name="google_places_food_search",
        as_type="tool",
        capture_input=False,
        capture_output=False
)
async def search_food_google(
    api_key: str,
    cuisine_or_type: Optional[str] = None,
    target_location: Optional[str] = None,
    lat: Optional[float] = None,
    lng: Optional[float] = None,
    radius: Optional[int] = None,
) -> Dict[str, Any]:
    """Searches for restaurants using Google Places API (New) searchText endpoint."""
    url = "https://places.googleapis.com/v1/places:searchText"
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": "places.displayName,places.formattedAddress",
    }

    food_query = cuisine_or_type if cuisine_or_type else "restaurant"
    payload: Dict[str, Any] = {"maxResultCount": 5}

    if target_location:
        payload["textQuery"] = f"{food_query} near {target_location}"

    elif lat is not None and lng is not None and radius is not None:
        payload["textQuery"] = food_query
        payload["locationBias"] = {
            "circle": {
                "center": {"latitude": lat, "longitude": lng},
                "radius": float(radius),
            }
        }
    else:
        payload["textQuery"] = food_query

    endpoint = url.removeprefix("https://places.googleapis.com/v1/")
    span_metadata = {
        "provider": "google_places_api",
        "endpoint": endpoint,
        "http_method": "POST"
    }
    langfuse.update_current_span(input=payload, metadata=span_metadata)

    async with httpx.AsyncClient(timeout=5.0) as client:
        response = await client.post(url, json=payload, headers=headers)
        langfuse.update_current_span(metadata={**span_metadata, "status_code": response.status_code})
        response.raise_for_status()
        raw_response = response.json()
        langfuse.update_current_span(output=raw_response)
        return raw_response


class MockFoodAgent:
    """Mock version of FoodAgent for offline testing."""

    @observe(
            name="mock_food_agent_invoke",
            capture_input=False,
            capture_output=False
    )
    async def invoke(
        self, 
        user_request: str, 
        car_lat: Optional[float] = None, 
        car_lng: Optional[float] = None,
    ) -> str:
        return (
            "[MOCK] I found the following dining options near your location:\n"
            "1. Example Bistro - Testowa 12, Test City, Poland\n"
            "2. Mock Sushi House - Przykładowa 17, Test City, Poland\n"
            "3. Demo Pizza - Testowa 34,  Test City, Poland\n"
            "4. Sample Burger - Mockowa 67, Test City, Poland\n"
            "5. Test Kitchen - Wymyślona 31, Test City, Poland"
        )
    

class FoodAgent:
    """Sub-agent that resolves constraints and fetches restaurants near coordinates using Google Places API or HERE Discover API."""

    @observe(
            name="food_agent_invoke",
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
            # Extract parameters using LLM
            search_params = await extract_food_search_params(user_request)

            # Route request based on selected provider
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
        search_params: FoodSearchParams,
        car_lat: Optional[float],
        car_lng: Optional[float],
        api_key: str,
    ) -> str:
        """Executes food search using Google Places API."""
        if search_params.use_current_location:
            if car_lat is None or car_lng is None:
                return "I cannot perform a local search because the vehicle's current GPS data is unavailable."
            
            raw_results = await search_food_google(
                api_key=api_key,
                cuisine_or_type=search_params.cuisine_or_type,
                lat=car_lat,
                lng=car_lng,
                radius=search_params.search_radius_meters,
            )
            location_name = "your current location"
        else:
            if not search_params.target_location:
                return "Sorry, I couldn't understand the target location for the food search."
            
            raw_results = await search_food_google(
                api_key=api_key,
                cuisine_or_type=search_params.cuisine_or_type,
                target_location=search_params.target_location,
            )
            location_name = f"'{search_params.target_location}'"

        places = raw_results.get("places", [])
        if not places:
            search_term = search_params.cuisine_or_type if search_params.cuisine_or_type else "dining options"
            return f"I couldn't find any {search_term} within {search_params.search_radius_meters} meters around {location_name}."

        response_lines = [f"I found the following dining options near {location_name}:"]
        for i, place in enumerate(places, 1):
            name = place.get("displayName", {}).get("text", "Restaurant")
            address = place.get("formattedAddress", "No address available")
            response_lines.append(f"{i}. {name} - {address}")

        return "\n".join(response_lines)


    async def _search_via_here(
        self,
        search_params: FoodSearchParams,
        car_lat: Optional[float],
        car_lng: Optional[float],
        api_key: str,
    ) -> str:
        """Executes food search using HERE Discover API."""
        # Resolve location to coordinates
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

        # Fetch data from HERE API
        raw_results = await search_food_here(
            lat=target_lat,
            lng=target_lng,
            query_text=search_params.cuisine_or_type,
            api_key=api_key
        )
        
        items = raw_results.get("items", [])

        if search_params.search_radius_meters:
            items = [
                item for item in items 
                if item.get("distance", 0) <= search_params.search_radius_meters
            ]

        if not items:
            search_term = search_params.cuisine_or_type if search_params.cuisine_or_type else "dining options"
            return f"I couldn't find any {search_term} within {search_params.search_radius_meters} meters around {location_name}."

        # Format output into a clean plain text string for A2A pipeline
        response_lines = [f"I found the following dining options near {location_name}:"]
        for i, item in enumerate(items, 1):
            name = item.get("title", "Unknown Place")
            address = item.get("address", {}).get("label", "No address available")
            distance_km = item.get("distance", 0) / 1000

            if search_params.use_current_location:
                distance_str = f"{distance_km:.2f} km away"
            else:
                distance_str = f"{distance_km:.2f} km from {location_name}"
            
            response_lines.append(f"{i}. {name} - {address} ({distance_str})")
            
        return "\n".join(response_lines)


class FoodAgentExecutor(AgentExecutor):
    """Handles incoming A2A requests and executes the food search flow."""

    def __init__(self, agent: Optional[Any] = None) -> None:
        self.agent = agent if agent is not None else FoodAgent()

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

        # Reuse the current task or create one for a new request
        if context.current_task:
            task = context.current_task
        else:
            task = new_task_from_user_message(context.message)
            await event_queue.enqueue_event(task)

        # Mark the task as working in EventQueue
        task_updater = TaskUpdater(
            event_queue=event_queue, 
            task_id=task.id, 
            context_id=task.context_id
        )
        await task_updater.update_status(
            state=TaskState.TASK_STATE_WORKING,
            message=new_text_message('Processing restaurant search request...'),
        )

        # Extract the request text and parse available telemetry from context
        query = get_message_text(context.message)
        
        # Change this if the Orchestrator sends car GPS in a different field.
        # Currently defaults to Warsaw Center coordinates as a fallback mock.
        car_lat = getattr(context, 'car_lat', 52.2297)
        car_lng = getattr(context, 'car_lng', 21.0122)

        if query:
            with langfuse.start_as_current_observation(
                name="food_agent_execute",
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

        # Add the agent response as a task artifact to EventQueue
        await task_updater.add_artifact(
            parts=[
                new_text_part(
                    text=result, 
                    media_type='text/plain'
                )
            ]
        )
        print('FoodAgent result: ', result)

        # Mark the task as completed
        await task_updater.update_status(
            state=TaskState.TASK_STATE_COMPLETED,
            message=new_text_message('Restaurant request is completed!'),
        )

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        """Raise exception as cancel is not supported."""
        raise NotImplementedError('Cancel is not supported.')
