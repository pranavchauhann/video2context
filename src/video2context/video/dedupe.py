import cv2
import numpy as np


def perceptual_hash(image: np.ndarray) -> int:
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    dct = cv2.dct(cv2.resize(gray, (32, 32)).astype(np.float32))[:8, :8].flatten()
    # Exclude DC so the hash describes structure, not mean brightness.
    bits = dct > np.median(dct[1:])
    return sum(int(bit) << i for i, bit in enumerate(bits))


def distance(a: int, b: int) -> int:
    return (a ^ b).bit_count()
