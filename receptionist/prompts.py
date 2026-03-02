from receptionist.config import BusinessConfig


def build_system_prompt(config: BusinessConfig) -> str:
    hours_lines = []
    for day_name in [
        "monday",
        "tuesday",
        "wednesday",
        "thursday",
        "friday",
        "saturday",
        "sunday",
    ]:
        day_hours = getattr(config.hours, day_name)
        display_name = day_name.capitalize()
        if day_hours is None:
            hours_lines.append(f"  {display_name}: Closed")
        else:
            hours_lines.append(
                f"  {display_name}: {day_hours.open} - {day_hours.close}"
            )
    hours_block = "\n".join(hours_lines)

    routing_lines = []
    for entry in config.routing:
        routing_lines.append(f"  - {entry.name}: {entry.description}")
    routing_block = (
        "\n".join(routing_lines) if routing_lines else "  No routing configured."
    )

    faq_lines = []
    for faq in config.faqs:
        faq_lines.append(f"  Q: {faq.question}\n  A: {faq.answer}")
    faq_block = "\n\n".join(faq_lines) if faq_lines else "  No FAQs configured."

    return f"""You are the receptionist for {config.business.name}, a {config.business.type}.

{config.personality}

BUSINESS HOURS (timezone: {config.business.timezone}):
{hours_block}

When the business is closed, say: {config.after_hours_message}

DEPARTMENTS YOU CAN TRANSFER TO:
{routing_block}

When a caller asks to be transferred, use the transfer_call tool with the department name.
When a caller wants to leave a message, use the take_message tool to record their name, message, and callback number.
When asked about business hours, use the get_business_hours tool.

FREQUENTLY ASKED QUESTIONS:
{faq_block}

You can answer these questions directly. For questions not covered here, offer to take a message or transfer the caller to the appropriate department.

IMPORTANT RULES:
- Be concise. Phone conversations should be efficient.
- Never make up information. If you don't know, say so and offer alternatives.
- Always confirm before transferring a call.
- If the caller seems upset, be empathetic and offer to connect them with a person.
"""
