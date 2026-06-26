"""Hugging Face sentiment analysis wrapper.

Model weights are expected to be pre-baked into the Docker image at HF_HOME.
TRANSFORMERS_OFFLINE=1 is set in the runtime env, so any missing weights
will cause this module to fail loudly at import time.
"""
import os

from transformers import AutoModelForSequenceClassification, AutoTokenizer

MODEL_NAME = os.environ.get(
    "MODEL_NAME", "distilbert-base-uncased-finetuned-sst-2-english"
)

# Loaded at module import time -> guarantees weights are in memory before
# the first request reaches the API.
_tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
_model = AutoModelForSequenceClassification.from_pretrained(MODEL_NAME)
_model.eval()

# Defensive mapping for the dry-run acceptance criterion. The SST-2 model
# already returns POSITIVE/NEGATIVE, but we map LABEL_0/1 just in case a
# different checkpoint is ever swapped in.
_LABEL_FIXUP = {
    "LABEL_0": "NEGATIVE",
    "LABEL_1": "POSITIVE",
    "NEGATIVE": "NEGATIVE",
    "POSITIVE": "POSITIVE",
}


def analyze(text: str) -> tuple[str, float]:
    """Return (sentiment_label, confidence) for the given text."""
    inputs = _tokenizer(text, return_tensors="pt", truncation=True, max_length=512)
    outputs = _model(**inputs)
    probs = outputs.logits.softmax(dim=-1).detach().tolist()[0]
    idx = int(max(range(len(probs)), key=lambda i: probs[i]))
    raw_label = _model.config.id2label[idx]
    label = _LABEL_FIXUP.get(raw_label, raw_label)
    confidence = float(probs[idx])
    return label, confidence
