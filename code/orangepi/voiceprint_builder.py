# Import necessary libraries
from resemblyzer import VoiceEncoder, preprocess_wav  # For extracting voice embeddings
from pathlib import Path                              # For handling file paths
import numpy as np                                     # For saving embeddings as a NumPy array

# Create a VoiceEncoder instance to generate voice embeddings
encoder = VoiceEncoder()

# Initialize an empty dictionary to store voiceprints (embeddings) keyed by name
voiceprints = {}

# Iterate over all .wav files in the /home/orangepi directory
for fname in Path("/home/orangepi").glob("*.wav"):
    name = fname.stem.lower()                # Get the filename without extension and convert it to lowercase (e.g., elif.wav → elif)
    wav = preprocess_wav(fname)              # Preprocess the audio file (normalization, trimming, etc.)
    embed = encoder.embed_utterance(wav)     # Generate an embedding (voiceprint) from the preprocessed audio
    voiceprints[name] = embed                # Store the embedding in the dictionary with the name as the key

# Save the entire voiceprints dictionary to a .npy file for later use
np.save("voiceprints.npy", voiceprints)

# Print a message indicating the process is complete
print("Voiceprints of group members have been saved.")
