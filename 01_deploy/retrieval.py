"""Course-note retrieval: one dot product against a prebuilt matrix.

No vector database. The index is a few hundred rows of 384 floats -- well under
a megabyte -- so brute-force cosine similarity is microseconds. A vector DB here
would add a service to run, a port to bind and a new way for the workshop to
fail, in exchange for nothing.
"""
import pathlib

import numpy as np

from embed import embed_one

INDEX = pathlib.Path(__file__).resolve().parents[1] / "data" / "index.npz"

with np.load(INDEX, allow_pickle=False) as _data:
    _vectors: np.ndarray = _data["vectors"]
    _texts: list[str] = list(_data["texts"])


def search(question: str, k: int) -> list[str]:
    """Return the k most similar note chunks. Vectors are already normalised."""
    if k <= 0:
        return []
    scores = _vectors @ embed_one(question)
    top = np.argsort(-scores)[:k]
    return [_texts[i] for i in top]


def size() -> int:
    return len(_texts)
