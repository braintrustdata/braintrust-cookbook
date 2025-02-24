
import braintrust

project = braintrust.projects.create(name="SupportChatbot")

prompt_v2 = project.prompts.create(
    name="Brand Support V2",
    slug="brand-support-v2",
    description="Brand-aligned support prompt",
    model="gpt-4o",
    messages=[
        {"role": "system", "content": "You’re a cheerful, proactive assistant for Sunshine Co. Always use a positive tone, apologize for issues with empathy, and offer clear solutions to delight customers! No emojis or profanity."},
        {"role": "user", "content": "{{{input}}}"}
    ]
)
