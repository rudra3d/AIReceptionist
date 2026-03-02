from receptionist.config import BusinessConfig
from receptionist.prompts import build_system_prompt


EXAMPLE_YAML = """
business:
  name: "Test Dental"
  type: "dental office"
  timezone: "America/New_York"
voice:
  voice_id: "coral"
greeting: "Thank you for calling Test Dental."
personality: "You are a friendly receptionist."
hours:
  monday: { open: "08:00", close: "17:00" }
  tuesday: { open: "08:00", close: "17:00" }
  wednesday: closed
  thursday: { open: "08:00", close: "17:00" }
  friday: { open: "08:00", close: "15:00" }
  saturday: closed
  sunday: closed
after_hours_message: "We are currently closed."
routing:
  - name: "Front Desk"
    number: "+15551234567"
    description: "General inquiries"
  - name: "Billing"
    number: "+15551234569"
    description: "Payment questions"
faqs:
  - question: "Where are you located?"
    answer: "123 Main Street."
  - question: "Do you accept insurance?"
    answer: "Yes, most plans."
messages:
  delivery: "file"
  file_path: "./messages/test/"
"""


def _make_config():
    return BusinessConfig.from_yaml_string(EXAMPLE_YAML)


def test_prompt_contains_business_name():
    prompt = build_system_prompt(_make_config())
    assert "Test Dental" in prompt


def test_prompt_contains_personality():
    prompt = build_system_prompt(_make_config())
    assert "friendly receptionist" in prompt


def test_prompt_contains_faq_content():
    prompt = build_system_prompt(_make_config())
    assert "Where are you located?" in prompt
    assert "123 Main Street." in prompt


def test_prompt_contains_routing_info():
    prompt = build_system_prompt(_make_config())
    assert "Front Desk" in prompt
    assert "Billing" in prompt


def test_prompt_contains_hours():
    prompt = build_system_prompt(_make_config())
    assert "Monday" in prompt
    assert "08:00" in prompt


def test_prompt_contains_after_hours_instructions():
    prompt = build_system_prompt(_make_config())
    assert "currently closed" in prompt
