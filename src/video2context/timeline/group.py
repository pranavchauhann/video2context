from copy import deepcopy

from video2context.config import Config
from video2context.domain.models import Timeline


def group_events(timeline: Timeline, config: Config) -> Timeline:
    grouped = []
    for original in timeline.events:
        event = deepcopy(original)
        previous = grouped[-1] if grouped else None
        same_evidence = (
            previous and previous.frames == event.frames and previous.screen == event.screen
        )
        if (
            same_evidence
            and not event.intent
            and not previous.intent
            and event.start_s - previous.end_s <= config.group_gap
            and event.end_s - previous.start_s <= config.max_event_duration
        ):
            previous.end_s = max(previous.end_s, event.end_s)
            previous.speech = list(dict.fromkeys(previous.speech + event.speech))
            previous.ocr = list(dict.fromkeys(previous.ocr + event.ocr))
            previous.visual = " ".join(dict.fromkeys(filter(None, [previous.visual, event.visual])))
            previous.importance = max(previous.importance, event.importance)
        else:
            grouped.append(event)
    for i, event in enumerate(grouped, 1):
        event.id = f"evt_{i:04d}"
    return Timeline(grouped)
