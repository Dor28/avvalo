"""FSM states for the onboarding and consent flow."""

from aiogram.fsm.state import State, StatesGroup


class Onboarding(StatesGroup):
    """States a user moves through before reaching the check prompt."""

    choosing_language = State()
    awaiting_consent = State()
    ready = State()


class StoryCapture(StatesGroup):
    """States for the opt-in anonymous story flow."""

    awaiting_story = State()
    awaiting_publish = State()
