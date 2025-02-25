
import braintrust

project = braintrust.projects.create(name="SupportChatbot")

prompt_v3 = project.prompts.create(
    name="Brand Support V3",
    slug="brand-support-v3",
    description="Over-enthusiastic support prompt with middling performance",
    model="gpt-4o",
    messages=[
        {"role": "system", "content": "You’re a SUPER EXCITED Sunshine Co. assistant! SHOUT IN ALL CAPS WITH LOTS OF EXCLAMATIONS!!!! SAY SORRY IF SOMETHING’S WRONG BUT KEEP IT VAGUE AND FUN!!! Make customers HAPPY with BIG ENERGY, even if solutions are UNCLEAR!!!!"},
        {"role": "user", "content": "{{{input}}}"}
    ],
    if_exists= "replace"
)
