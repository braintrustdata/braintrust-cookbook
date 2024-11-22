import braintrust

# Initialize the dataset
dataset = braintrust.init_dataset(project="toolOCR", name="Recipes")

# List of image URLs
images = [
    "https://images.squarespace-cdn.com/content/v1/5ec6e2030422441e3a7dceeb/1595445920408-QP7Y52ZON1E0J8WEMPQO/un-1.jpg",
    "https://i.redd.it/how-do-i-make-this-recipe-card-not-look-so-janky-on-ds-v0-f0ntfxf2i52a1.jpg?width=1024&format=pjpg&auto=webp&s=c2bdd4b746311688a4f477e0d90738988420590b",
    "https://marketplace.canva.com/EAFe99ATpL4/1/0/1600w/canva-neutral-minimalist-pancake-recipe-card-Z_cO765s1-U.jpg",
    "https://images.squarespace-cdn.com/content/v1/6419d9e9c7527734c8cff21b/05018823-a6c6-4acc-b104-93aa9b2f1aff/Screen%2BShot%2B2018-02-14%2Bat%2B6.28.16%2BAM.png",
]

# Insert records into the dataset
for image_url in images:
    id = dataset.insert(
        input={"image": image_url},
        expected=None,  # Replace with expected output if any
        metadata=None   # Replace with any metadata if needed
    )
    print("Inserted record with id", id)

# Summarize the dataset
print(dataset.summarize())