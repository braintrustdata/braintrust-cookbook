import braintrust
import requests
from pydantic import BaseModel, HttpUrl
import braintrust
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

if not os.getenv("BRAINTRUST_API_KEY"):
    raise ValueError("BRAINTRUST_API_KEY is not set")

# Create the Braintrust project
project = braintrust.projects.create(name="toolOCR")

# Define the input parameters schema using Pydantic
class Args(BaseModel):
    image_url: HttpUrl  # Ensure the input is a valid URL

# Define the OCR function
def ocr_image(**kwargs) -> str:
    # Parse input arguments
    args = Args(**kwargs)

    # OCR.Space API endpoint and payload
    api_url = "https://api.ocr.space/parse/imageurl"
    payload = {
        "apikey": "helloworld",  # Free tier API key
        "url": args.image_url,
        "language": "eng",
        "OCREngine": "2",
        "scale": "true",
    }

    # Make the API request
    try:
        response = requests.get(api_url, params=payload)
        response.raise_for_status()
        result = response.json()

        # Handle errors in the OCR response
        if result.get("IsErroredOnProcessing", False):
            raise ValueError(f"OCR error: {result.get('ErrorMessage', 'Unknown error')}")

        # Extract and return the parsed text
        return result["ParsedResults"][0]["ParsedText"] if "ParsedResults" in result else "No text detected."
    except Exception as e:
        raise ValueError(f"Failed to perform OCR: {e}")

# Create the OCR tool
ocr_tool = project.tools.create(
        name="OCR",
        description="Extracts text from an image URL using OCR.Space API",
        handler=ocr_image,  # Pass the function here
        parameters=Args,    # Define the parameters schema
        if_exists="replace",  # Replace the tool if it already exists
    )


project = braintrust.projects.create(name="toolOCR")

prompt = project.prompts.create(
    name= "Recipe text generator",
    messages= [{"role": "system", "content": "You are a helpful assistant that turns images of recipes into text-based grocery lists that are organized by category.",},
        {"role": "user", "content": "{{{image}}}",},
    ],
model= "gpt-4o-mini",
tools= [ocr_tool],
if_exists= "replace",
)