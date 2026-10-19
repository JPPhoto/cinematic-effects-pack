# Copyright (c) 2025 Jonathan S. Pollack (https://github.com/JPPhoto)

import numpy as np
from invokeai.invocation_api import (
    BaseInvocation,
    ColorField,
    ImageField,
    ImageOutput,
    InputField,
    InvocationContext,
    WithBoard,
    WithMetadata,
    invocation,
)
from PIL import Image

from .util import oklch_to_rgb, rgb_to_oklch  # noqa: TID252


@invocation("color_cast_correction", title="Color Cast Correction", tags=["color", "correction"], version="1.1.0")
class ColorCastCorrectionInvocation(BaseInvocation, WithBoard, WithMetadata):
    """Correct color cast while preserving perceptual brightness"""

    image: ImageField = InputField(description="Image to correct")
    strength: float = InputField(default=0.75, ge=0, le=2, description="Strength of correction adjustment")
    target_color: ColorField = InputField(
        default=ColorField(r=127, g=127, b=127, a=255), description="The target color for correction"
    )

    def invoke(self, context: InvocationContext) -> ImageOutput:
        image = context.images.get_pil(self.image.image_name)
        img_np = np.asarray(image).astype(np.float32) / 255.0
        if img_np.shape[2] == 4:
            alpha = img_np[..., 3:]
            img_np = img_np[..., :3]
        else:
            alpha = None

        height, width, _ = img_np.shape

        oklch_orig = rgb_to_oklch(img_np)
        original_L = oklch_orig[..., 0]

        target_rgb = np.array([self.target_color.r, self.target_color.g, self.target_color.b], dtype=np.float32) / 255.0
        mean_rgb = img_np.mean(axis=(0, 1))
        gain = target_rgb / (mean_rgb + 1e-6)
        gain = 1.0 + self.strength * (gain - 1.0)
        r_gain, g_gain, b_gain = gain

        corrected = img_np.copy()
        corrected[..., 0] *= r_gain
        corrected[..., 1] *= g_gain
        corrected[..., 2] *= b_gain
        corrected = np.clip(corrected, 0.0, 1.0)

        oklch_corr = rgb_to_oklch(corrected)
        oklch_corr[..., 0] = original_L
        final_rgb = oklch_to_rgb(oklch_corr)
        if alpha is not None:
            final_rgb = np.concatenate([final_rgb, alpha], axis=-1)

        output_image = Image.fromarray((final_rgb * 255).astype(np.uint8))
        image_dto = context.images.save(image=output_image)
        return ImageOutput.build(image_dto)
