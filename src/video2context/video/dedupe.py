import numpy as np

from video2context.video.change import to_gray

HASH_SIZE = 32


def _dct_matrix(size: int) -> np.ndarray:
    n = np.arange(size)
    matrix = np.cos(np.pi * (2 * n[None, :] + 1) * n[:, None] / (2 * size))
    matrix[0] *= 1 / np.sqrt(2)
    return matrix * np.sqrt(2 / size)


DCT = _dct_matrix(HASH_SIZE)


def box_resize(gray: np.ndarray, size: int = HASH_SIZE) -> np.ndarray:
    """Area-averaging downsample via an integral image; nearest sampling for tiny inputs."""
    height, width = gray.shape
    if height < size or width < size:
        ys = np.minimum((np.arange(size) * height) // size, height - 1)
        xs = np.minimum((np.arange(size) * width) // size, width - 1)
        return gray[ys][:, xs].astype(np.float64)
    integral = np.zeros((height + 1, width + 1), dtype=np.float64)
    integral[1:, 1:] = np.cumsum(np.cumsum(gray, axis=0), axis=1)
    ys = np.rint(np.linspace(0, height, size + 1)).astype(int)
    xs = np.rint(np.linspace(0, width, size + 1)).astype(int)
    y0, y1 = ys[:-1][:, None], ys[1:][:, None]
    x0, x1 = xs[:-1][None, :], xs[1:][None, :]
    total = integral[y1, x1] - integral[y0, x1] - integral[y1, x0] + integral[y0, x0]
    return total / ((y1 - y0) * (x1 - x0))


def perceptual_hash(image: np.ndarray) -> int:
    small = box_resize(to_gray(image))
    dct = (DCT @ small @ DCT.T)[:8, :8].flatten()
    # Exclude DC so the hash describes structure, not mean brightness.
    bits = dct > np.median(dct[1:])
    return sum(int(bit) << i for i, bit in enumerate(bits))


def distance(a: int, b: int) -> int:
    return (a ^ b).bit_count()
