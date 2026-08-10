from a2a.types import (
    AgentCapabilities,
    AgentCard,
    AgentInterface,
    AgentSkill,
)

from config import get_weather_agent_url

# Define the abilities or functions that weather agent can perform.
skill = AgentSkill(
    id='check-weather-and-forecast',
    name='Check Weather Conditions and Forecast',
    description='Provides current weather, forecasts, and driver safety warnings for current position or specified cities.',
    input_modes=['text/plain'],
    output_modes=['text/plain'],
    tags=['weather', 'forecast', 'temperature', 'rain', 'road-conditions'],
    examples=[
        'what is the weather in Warsaw?',
        'is it going to rain near me?',
        'what is the temperature in Kraków?'
    ],
)
# Publish metadata that A2A clients use to discover the agent
agent_card = AgentCard(
    name='Weather Agent',
    description='Sub-agent for retrieving weather conditions, forecasts, and driving safety alerts.',
    version='1.0.0',
    default_input_modes=['text/plain'],
    default_output_modes=['text/plain'],
    capabilities=AgentCapabilities(streaming=True, extended_agent_card=True),
    supported_interfaces=[
        AgentInterface(
            protocol_binding='JSONRPC',
            url=get_weather_agent_url(),
            protocol_version='1.0',
        )
    ],
    skills=[skill],
)
