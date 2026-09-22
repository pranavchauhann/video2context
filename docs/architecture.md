# Architecture

`cli → config → pipeline → media/video/providers → timeline → context → export`

Domain dataclasses and protocols have no third-party imports. Provider implementations
normalize into domain types immediately. The orchestrator owns directories, cleanup, and
provider choice; media functions write only explicitly supplied staging paths.

1. Validate settings, local input, output collision, and FFmpeg prerequisites.
2. Probe stream metadata with ffprobe.
3. Stream low-resolution previews from a single FFmpeg decode pass (`fps` + `scale`
   filters, raw BGR over a pipe) and score intensity/layout/histogram/edge differences in
   NumPy; no OpenCV or other native image library is needed. The fps filter resamples by real timestamps, so variable-frame-rate screen
   recordings (QuickTime, OBS) land on the right moment; per-sample decoder seeks did not.
   Tiny moving areas are suppressed. Compare against both the preceding preview and the
   last retained state to catch gradual changes.
4. Apply perceptual hash + color dedupe between adjacent retained states. Strong scene
   boundaries bypass hash dedupe; revisiting a screen after another state is retained.
5. Select the strongest transition in each temporal budget bin, filling empty bin slots
   with remaining high scores. Extract selected JPEGs with FFmpeg. Candidate descriptors
   are capped; only two preview arrays are retained in memory at a time.
6. Extract timestamp-offset audio chunks and transcribe when a provider is configured.
7. Enrich only retained frames with bounded worker pools. Vision rate limiting also
   applies to retries. Cache successful normalized output, not errors. Per-frame failures
   are summarized into one warning per cause; a rejected API key stops the stage instead
   of repeating the same failed request for every frame.
8. Join speech with the frame that was on screen when it started (the latest frame at or
   before the segment). Later speech on static screens creates its own events referencing
   that frame, so frame dedupe never deletes speech and a long narration cannot pull later
   sentences back onto an earlier screen.
9. Group adjacent events only when they share evidence and do not introduce a request.
   Keep chronological order and stable IDs. Compression is presentation-only.
10. Export into a private sibling directory and rename. An exclusive lock prevents
    cooperating runs from publishing to the same path. Overwrite first moves the previous
    marked package aside and restores it if publication raises. A hard process kill during
    overwrite can leave a backup/lock requiring manual recovery; there is no cross-platform
    atomic directory exchange primitive here.

All internal times are float seconds. Frame names encode capture milliseconds; metadata
includes complete FrameRef records. Speech quotations and OCR are escaped in Markdown.
Generated handoff text treats source content as evidence rather than trusted instructions.

The V1 implementation runs audio and video branches sequentially for predictable resource
usage; frame extraction and enrichment are parallel. Sampling is one sequential decode with
low-resolution scoring, not persistent full-resolution candidate files; only two preview
arrays are held in memory at a time. Selected frames are then extracted at full resolution
with accurate FFmpeg seeks.
Future work: streaming low-resolution decode, speech-guided visual reselection, more providers,
and richer scene-boundary/persistence heuristics. None require changing the output contract.
