"""The OpenAI sensor"""
import requests
import voluptuous as vol
from homeassistant.components.sensor import PLATFORM_SCHEMA, SensorEntity
from homeassistant.const import CONF_API_KEY, CONF_NAME
import homeassistant.helpers.config_validation as cv
from homeassistant.core import HomeAssistant, callback
import logging


_LOGGER = logging.getLogger(__name__)

ATTR_MODEL = "model"
ATTR_PROMPT = "prompt"
CONF_MODEL = "model"
DEFAULT_NAME = "hassio_openai_response"
DEFAULT_MODEL = "gpt4hassio"
DOMAIN = "openai_response"
SERVICE_OPENAI_INPUT = "openai_input"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required("session_cookie"): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_MODEL, default=DEFAULT_MODEL): cv.string,
    }
)


async def async_setup_platform(
    hass: HomeAssistant, config, async_add_entities, discovery_info=None
):
    """Setting up the sensor"""
    name = config[CONF_NAME]
    model = config[CONF_MODEL]
    session_cookie = config["session_cookie"]


    sensor = OpenAIResponseSensor(hass, name, model,session_cookie)
    async_add_entities([sensor], True)

    @callback
    async def async_generate_openai_request(service):
        """Handling service call"""
        _LOGGER.debug(service.data)
        sensor.request_running(
            service.data.get(ATTR_MODEL, config[CONF_MODEL]),
            service.data.get(ATTR_PROMPT),
        )
        response = await hass.async_add_executor_job(
            ask,
            session_cookie,
            service.data.get(ATTR_MODEL, config[CONF_MODEL]),
            service.data.get(ATTR_PROMPT),
        )
        _LOGGER.debug(response)
        sensor.response_received(response)

    hass.services.async_register(
        DOMAIN, SERVICE_OPENAI_INPUT, async_generate_openai_request
    )
    return True


# def generate_openai_response_sync(model: str, prompt: str, mood: str):
#     """Do the real OpenAI request"""
#     _LOGGER.debug("Model: %s, Mood: %s, Prompt: %s", model, mood, prompt)
#     return openai.ChatCompletion.create(
#         model=model,
#         messages=[
#             {"role": "system", "content": mood},
#             {"role": "user", "content": prompt},
#         ],
#     )
def query_message(query, token_budget=4096 - 500):
    return query

def ask(session_cookie, model, query, token_budget=4096 - 500):
    message = query_message(query, token_budget=token_budget)

    url = f"https://cloud.mindsdb.com/api/projects/mindsdb/models/{model}/predict"
    cookies = {"session": session_cookie}
    data = {"data": [{"text": message}]}
    headers = {"Content-Type": "application/json"}
    response = requests.post(url, json=data, cookies=cookies, headers=headers)
    response_json = response.json()
    response_message = response_json[0]["response"]

    return response_message


class OpenAIResponseSensor(SensorEntity):
    """The OpenAI sensor"""

    def __init__(self, hass: HomeAssistant, name: str, model: str, session_cookie: str) -> None:
        self._hass = hass
        self._name = name
        self._model = model
        self._prompt = None
        self._attr_native_value = None
        self._response_text = ""
        self._session_cookie = session_cookie
    @property
    def name(self):
        return self._name

    @property
    def extra_state_attributes(self):
        return {
            "response_text": self._response_text,
            "prompt": self._prompt,
            "model": self._model,
        }

    def request_running(self, model, prompt):
        """Staring a new request"""
        self._model = model
        self._prompt = prompt
        self._response_text = ""
        self._attr_native_value = "requesting"
        self.async_write_ha_state()

    def response_received(self, response_text):
        """Updating the sensor state"""
        self._response_text = response_text
        self._attr_native_value = "response_received"
        self.async_write_ha_state()

    async def async_generate_openai_response(self, entity_id, old_state, new_state):
        """Updating the sensor from the input_text"""
        new_text = new_state.state

        if new_text:
            self.request_running(self._model, new_text)
            response = await self._hass.async_add_executor_job(
                ask,
                self._session_cookie,
                self._model,
                new_text,
            )
            self.response_received(response)

    # async def async_added_to_hass(self):
    #     """Added to hass"""
    #     self.async_on_remove(
    #         self._hass.helpers.event.async_track_state_change(
    #             "input_text.gpt_input", self.async_generate_openai_response
    #         )
    #     )

    async def async_update(self):
        """Ignore other updates"""
        pass
