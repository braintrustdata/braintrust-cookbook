import pytesseract
from PIL import Image
import base64
from io import BytesIO
import braintrust
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

if not os.getenv("BRAINTRUST_API_KEY"):
    raise ValueError("BRAINTRUST_API_KEY is not set")

project = braintrust.projects.create(name="toolOCR")

# Define the OCR function
def ocr_image(image_base64):
    # Decode the base64 image
    image_data = base64.b64decode(image_base64)
    image = Image.open(BytesIO(image_data))
    # Perform OCR
    text = pytesseract.image_to_string(image)

    return text


project.tools.create(
    name="OCR",
    description="Extracts text from an image using OCR",
    handler=ocr_image,
    parameters=[
        {"name": "image_base64", "type": "str", "description": "the base-64 encoded image"},
    ],
        if_exists="replace",
)
