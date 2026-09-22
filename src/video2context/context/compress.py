from copy import deepcopy

from video2context.domain.models import ContextDocument, Timeline


class EvidenceCompressor:
    def __init__(self, detail: str = "balanced"):
        self.detail = detail

    def compress(self, timeline: Timeline, intent: str) -> ContextDocument:
        # Canonical JSON remains complete; only presentation is compressed.
        events = deepcopy(timeline.events)
        if self.detail == "compact":
            events = [
                e
                for i, e in enumerate(events)
                if e.intent or e.speech or e.importance >= 0.4 or i in {0, len(events) - 1}
            ]
        for event in events:
            event.speech = list(dict.fromkeys(event.speech))
            event.ocr = list(dict.fromkeys(event.ocr))
        return ContextDocument(Timeline(events), [e for e in events if e.intent])
