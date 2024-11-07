import braintrust
import ocr


project = braintrust.projects.create(name="toolOCR")


prompt = project.prompts.create(
    name= "Recipe text generator",
    messages= [{"role": "system", "content": "You are a helpful assistant that ",},
        {"role": "user", "content": "{{{question}}}",},
    ],
model= "gpt-4o-mini",
tools= [ocr],
ifExists= "replace",
)