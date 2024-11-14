import pytesseract
from PIL import Image
from pydantic import BaseModel
import base64
from io import BytesIO
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
    image_base64: str

print(Args.schema_json(indent=2))

# Define the OCR function
def ocr_image(args: Args) -> str:
    # Access the `image_base64` field from the Args instance
    image_data = base64.b64decode(args.image_base64)
    image = Image.open(BytesIO(image_data))
    # Perform OCR
    text = pytesseract.image_to_string(image)
    return text

# Create the OCR tool
project.tools.create(
    name="OCR",
    description="Extracts text from an image using OCR",
    handler=ocr_image,  # Pass the function here
    parameters=Args,    # Use the Pydantic model for parameters
    if_exists="replace",  # Replace the tool if it already exists
)
