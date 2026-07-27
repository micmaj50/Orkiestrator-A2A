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


class ParkingSearchParams(BaseModel):
    use_current_location: bool = Field(
        description=(
            "True if searching for parking lots or spaces near the vehicle's current position. "
            "False if a specific target location (city, street, address, or landmark) was provided."
        )
    )
    target_location: Optional[str] = Field(
        default=None, 
        description=(
            "A specific location provided by the driver to search parking around. "
            "Can be a city (e.g., 'Kraków'), a street (e.g., 'Floriańska'), "
            "or a landmark (e.g., 'Wawel Castle'). "
            "Extract ONLY the location name itself. Do NOT include words like 'parking', 'park', "
            "or 'place to park'. Leave as None if use_current_location is True."
        )
    )
    search_radius_meters: int = Field(
        default=3000, 
        description=(
            "The search radius in meters. Convert spoken distance units (e.g., 'within 5km') "
            "to integer meters (5000). Default to 3000 if not specified by the driver."
        )
    )


async def extract_parking_search_params(driver_command: str) -> ParkingSearchParams:
    """Extracts structured search parameters from the driver's command using LLM."""
    client = AsyncOpenAI()
    
    completion = await client.beta.chat.completions.parse(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system", 
                "content": (
                    "You are an NLP analysis module inside an in-car voice assistant system. "
                    "Your sole task is to extract parking search parameters "
                    "from the driver's spoken command and map them into the requested JSON schema."
                )
            },
            {
                "role": "user", 
                "content": driver_command
            }
        ],
        response_format=ParkingSearchParams,
        temperature=0.0
    )
    return completion.choices[0].message.parsed


async def search_parking_google(
    api_key: str,
    target_location: Optional[str] = None,
    lat: Optional[float] = None,
    lng: Optional[float] = None,
    radius: Optional[int] = None,
) -> Dict[str, Any]:
    """Searches for parking places using Google Places API."""
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": "places.displayName,places.formattedAddress",
    }

    if target_location:
        url = "https://places.googleapis.com/v1/places:searchText"
        payload = {
            "textQuery": f"parking near {target_location}",
            "includedType": "parking",
            "maxResultCount": 5,
        }

    elif lat is not None and lng is not None and radius is not None:
        url = "https://places.googleapis.com/v1/places:searchNearby"
        payload = {
            "includedTypes": ["parking"],
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


class ParkingAgent:
    """Sub-agent that resolves constraints and fetches parking places using Google Places API."""

    async def invoke(self, user_request: str, car_lat: Optional[float] = None, car_lng: Optional[float] = None) -> str:
        try:
            search_params = await extract_parking_search_params(user_request)

            google_api_key = os.environ.get("GOOGLE_API_KEY")
            if not google_api_key:
                return self._get_mock_response(search_params)

            if search_params.use_current_location:
                if car_lat is None or car_lng is None:
                    return "I cannot perform a local search because the vehicle's current GPS data is unavailable."

                raw_results = await search_parking_google(
                    lat=car_lat,
                    lng=car_lng,
                    radius=search_params.search_radius_meters,
                    api_key=google_api_key,
                )
                location_name = "your current location"
            else:
                if not search_params.target_location:
                    return "Sorry, I couldn't understand the target location for parking."

                raw_results = await search_parking_google(
                    target_location=search_params.target_location,
                    api_key=google_api_key,
                )
                location_name = f"'{search_params.target_location}'"

            places = raw_results.get("places", [])

            if not places:
                return f"I couldn't find any parking lots within {search_params.search_radius_meters} meters around {location_name}."

            response_lines = [
                f"I found the following parking options near {location_name}:"
            ]
            for i, place in enumerate(places, 1):
                name = place.get("displayName", {}).get("text", "Parking Lot")
                address = place.get("formattedAddress", "No address available")
                response_lines.append(f"{i}. {name} - {address}")

            return "\n".join(response_lines)

        except Exception as e:
            return f"An error occurred while processing the request: {str(e)}"


    def _get_mock_response(self, search_params: ParkingSearchParams) -> str:
        """Fallback mock response when GOOGLE_API_KEY is missing on the server."""
        if search_params.use_current_location or not search_params.target_location:
            location_name = "your current location"
        else:
            location_name = f"'{search_params.target_location}'"

        response_lines = [f"[MOCK] I found the following parking options near {location_name}:"]
        
        mock_parkings = [
            ("Parking Stadion Narodowy", "aleja Zieleniecka 6, 03-727 Warszawa, Poland"),
            ("Torwar", "00-456 Warsaw, Poland"),
            ("Campanile Warszawa", "Towarowa 2, 00-811 Warszawa, Poland"),
            ("Parking Łazienki Królewskie", "Parkowa 23, 00-759 Warszawa, Poland"),
            ("Parking in the Old Town", "Unnamed Road, 00-001 Warszawa, Poland"),
        ]

        for i, (name, address) in enumerate(mock_parkings, 1):
            response_lines.append(f"{i}. {name} - {address}")

        return "\n".join(response_lines)


class ParkingAgentExecutor(AgentExecutor):
    """Handles incoming A2A requests and executes the parking search flow."""

    def __init__(self) -> None:
        self.agent = ParkingAgent()

    async def execute(
        self,
        context: RequestContext,
        event_queue: EventQueue,
    ) -> None:
        
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
            message=new_text_message('Processing parking search request...'),
        )

        # Extract the request text and parse available telemetry from context
        query = get_message_text(context.message)
        
        # Change this if the Orchestrator sends car GPS in a different field.
        # Currently defaults to Warsaw Center coordinates as a fallback mock.
        car_lat = getattr(context, 'car_lat', 52.2297)
        car_lng = getattr(context, 'car_lng', 21.0122)

        if query:
            result = await self.agent.invoke(user_request=query, car_lat=car_lat, car_lng=car_lng)
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
        print('ParkingAgent result: ', result)

        # Mark the task as completed
        await task_updater.update_status(
            state=TaskState.TASK_STATE_COMPLETED,
            message=new_text_message('Parking request is completed!'),
        )

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        """Raise exception as cancel is not supported."""
        raise NotImplementedError('Cancel is not supported.')
