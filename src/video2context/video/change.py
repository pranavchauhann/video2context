import cv2
import numpy as np


def change_score(
    previous: np.ndarray,
    current: np.ndarray,
    pixel_threshold: int = 24,
    cursor_area_threshold: float = 0.003,
) -> float:
    """Compare low-res layout, intensity and histograms, ignoring tiny moving regions."""
    a = cv2.cvtColor(previous, cv2.COLOR_BGR2GRAY)
    b = cv2.cvtColor(current, cv2.COLOR_BGR2GRAY)
    diff = cv2.absdiff(a, b)
    area = float(np.mean(diff > pixel_threshold))
    if area < cursor_area_threshold:
        return 0.0
    structural = float(np.mean(diff)) / 255
    histogram_a = cv2.calcHist([a], [0], None, [32], [0, 256])
    histogram_b = cv2.calcHist([b], [0], None, [32], [0, 256])
    cv2.normalize(histogram_a, histogram_a)
    cv2.normalize(histogram_b, histogram_b)
    histogram = cv2.compareHist(histogram_a, histogram_b, cv2.HISTCMP_BHATTACHARYYA)
    edge = float(np.mean(cv2.absdiff(cv2.Canny(a, 50, 150), cv2.Canny(b, 50, 150)))) / 255
    return min(1.0, 0.45 * structural + 0.25 * histogram + 0.20 * edge + 0.10 * area)
