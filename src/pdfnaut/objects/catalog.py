from __future__ import annotations

from typing import Literal

PageLayout = Literal[
    "SinglePage", "OneColumn", "TwoColumnLeft", "TwoColumnRight", "TwoPageLeft", "TwoPageRight"
]
PageMode = Literal["UseNone", "UseOutlines", "UseThumbs", "FullScreen", "UseOC", "UseAttachments"]
