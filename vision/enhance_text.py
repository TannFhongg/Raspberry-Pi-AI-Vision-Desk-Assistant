"""Text-focused image enhancement helpers for distant screen captures."""

from __future__ import annotations


def enhance_text_image(image, cv2_module, grayscale: bool = False):
    """Apply lightweight denoise, brightness, contrast, and sharpening tuned for text."""
    if len(image.shape) == 2:
        return _enhance_grayscale_image(image, cv2_module)

    denoised = cv2_module.bilateralFilter(image, 7, 45, 45)
    lab_image = cv2_module.cvtColor(denoised, cv2_module.COLOR_BGR2LAB)
    lightness, a_channel, b_channel = cv2_module.split(lab_image)
    normalized_lightness = _normalize_lightness(lightness, cv2_module)
    enhanced_lightness = cv2_module.createCLAHE(clipLimit=2.5, tileGridSize=(8, 8)).apply(
        normalized_lightness
    )

    merged = cv2_module.merge((enhanced_lightness, a_channel, b_channel))
    enhanced = cv2_module.cvtColor(merged, cv2_module.COLOR_LAB2BGR)
    sharpened = _apply_text_sharpening(enhanced, cv2_module)
    if grayscale:
        return cv2_module.cvtColor(sharpened, cv2_module.COLOR_BGR2GRAY)
    return sharpened


def _enhance_grayscale_image(image, cv2_module):
    """Enhance a grayscale source image with the same readability-oriented steps."""
    denoised = cv2_module.bilateralFilter(image, 7, 45, 45)
    normalized = _normalize_lightness(denoised, cv2_module)
    enhanced = cv2_module.createCLAHE(clipLimit=2.5, tileGridSize=(8, 8)).apply(normalized)
    return _apply_text_sharpening(enhanced, cv2_module)


def _normalize_lightness(lightness, cv2_module):
    """Correct uneven brightness without aggressively flattening the image."""
    mean_lightness = float(lightness.mean())
    target_mean = 150.0
    brightness_shift = max(-35.0, min(35.0, target_mean - mean_lightness))

    contrast_alpha = 1.0
    if mean_lightness < 95.0:
        contrast_alpha = 1.12
    elif mean_lightness > 190.0:
        contrast_alpha = 0.92

    return cv2_module.convertScaleAbs(lightness, alpha=contrast_alpha, beta=brightness_shift)


def _apply_text_sharpening(image, cv2_module):
    """Use a restrained unsharp mask so text edges pop without ringing heavily."""
    blurred = cv2_module.GaussianBlur(image, (0, 0), 1.2)
    return cv2_module.addWeighted(image, 1.22, blurred, -0.22, 0)
