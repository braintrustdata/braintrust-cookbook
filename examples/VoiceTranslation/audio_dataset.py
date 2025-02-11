import braintrust

# 1. Configure the project and dataset name
PROJECT_NAME = "Audio Translator"   # Update if needed
DATASET_NAME = "Audio snippets"

# 2. List of audio URLs
audio_urls = [
    "https://github.com/braintrustdata/braintrust-cookbook/raw/acbc93be6f8b6da8926b2468a72e657d04abc0ee/examples/VoiceTranslation/assets/1.mp3",
    "https://github.com/braintrustdata/braintrust-cookbook/raw/acbc93be6f8b6da8926b2468a72e657d04abc0ee/examples/VoiceTranslation/assets/2.mp3",
    "https://github.com/braintrustdata/braintrust-cookbook/raw/acbc93be6f8b6da8926b2468a72e657d04abc0ee/examples/VoiceTranslation/assets/3.mp3",
    "https://github.com/braintrustdata/braintrust-cookbook/raw/acbc93be6f8b6da8926b2468a72e657d04abc0ee/examples/VoiceTranslation/assets/4.mp3",
    "https://github.com/braintrustdata/braintrust-cookbook/raw/acbc93be6f8b6da8926b2468a72e657d04abc0ee/examples/VoiceTranslation/assets/5.mp3",
    "https://github.com/braintrustdata/braintrust-cookbook/raw/acbc93be6f8b6da8926b2468a72e657d04abc0ee/examples/VoiceTranslation/assets/6.mp3"
]

# 3. Corresponding placeholder translations (one for each audio clip)
placeholder_translations = [
    "Placeholder translation for audio 1",
    "Placeholder translation for audio 2",
    "Placeholder translation for audio 3",
    "Placeholder translation for audio 4",
    "Placeholder translation for audio 5",
    "Placeholder translation for audio 6"
]

# 4. Initialize (or load) the dataset in Braintrust
dataset = braintrust.init_dataset(
    project=PROJECT_NAME,
    name=DATASET_NAME
)

# 5. Insert records into the dataset
for i, url in enumerate(audio_urls):
    record_id = dataset.insert(
        input={"audio_url": url},
        expected={"translation": placeholder_translations[i]},
        metadata={"clip_index": i+1}  # Optional metadata
    )
    print(f"Inserted record with id {record_id}")
