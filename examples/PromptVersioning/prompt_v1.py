
import braintrust

project = braintrust.projects.create(name="SupportChatbot")

prompt_v1 = project.prompts.create(
    name="Brand Support V1",
    slug="brand-support-v1",
    description="Simple support prompt",
    model="gpt-4o",
    messages=[
        {"role": "user", "content": "{{{input}}}"}
    ]
)
