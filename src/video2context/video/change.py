import numpy as np

EDGE_THRESHOLD = 30.0


def to_gray(image: np.ndarray) -> np.ndarray:
    """BGR uint8 -> float32 luminance, matching the usual Rec. 601 weights."""
    if image.ndim == 2:
        return image.astype(np.float32)
    return image[..., 0] * 0.114 + image[..., 1] * 0.587 + image[..., 2] * 0.299


def edge_map(gray: np.ndarray) -> np.ndarray:
    gy, gx = np.gradient(gray)
    return np.hypot(gx, gy) > EDGE_THRESHOLD


def change_score(
    previous: np.ndarray,
    current: np.ndarray,
    pixel_threshold: int = 24,
    cursor_area_threshold: float = 0.003,
) -> float:
    """Compare low-res layout, intensity and histograms, ignoring tiny moving regions."""
    a = to_gray(previous)
    b = to_gray(current)
    diff = np.abs(a - b)
    area = float(np.mean(diff > pixel_threshold))
    if area < cursor_area_threshold:
        return 0.0
    structural = float(np.mean(diff)) / 255
    histogram_a = np.histogram(a, bins=32, range=(0, 256))[0].astype(np.float64)
    histogram_b = np.histogram(b, bins=32, range=(0, 256))[0].astype(np.float64)
    histogram_a /= max(histogram_a.sum(), 1)
    histogram_b /= max(histogram_b.sum(), 1)
    # Bhattacharyya distance between the two intensity distributions.
    histogram = float(np.sqrt(max(0.0, 1 - np.sum(np.sqrt(histogram_a * histogram_b)))))
    edge = float(np.mean(edge_map(a) != edge_map(b)))
    return min(1.0, 0.45 * structural + 0.25 * histogram + 0.20 * edge + 0.10 * area)
