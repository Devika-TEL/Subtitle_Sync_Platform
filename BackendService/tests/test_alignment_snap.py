import unittest

from BackendService.subtitle_correction import correct_subtitles, hybrid_correct_subtitles

class TestSubtitleAlignmentSnap(unittest.TestCase):
    def setUp(self):
        # Simple transcript with three segments
        self.transcript = {
            "segments": [
                {"start": 1.0, "end": 2.0, "text": "Hello world"},
                {"start": 2.2, "end": 3.0, "text": "How are you"},
                {"start": 3.5, "end": 5.0, "text": "Nice to meet you"},
            ],
            "language": "en",
        }

    def assertCueEquals(self, cue, s, e):
        self.assertAlmostEqual(float(cue["start"]), float(s), places=6)
        self.assertAlmostEqual(float(cue["end"]), float(e), places=6)

    def test_snap_both_boundaries_simple(self):
        # Misaligned subtitle that should snap to segment 1 (1.0 - 2.0)
        subtitles = [
            {"start": 0.8, "end": 2.3, "text": "Hello wrld", "format": "srt", "language": "en"},
            {"start": 2.1, "end": 3.2, "text": "How are u", "format": "srt", "language": "en"},
        ]

        corrected = correct_subtitles(self.transcript, subtitles)
        self.assertEqual(len(corrected), 2)

        # Cue 1 snapped to segment 1
        self.assertCueEquals(corrected[0], 1.0, 2.0)
        # Cue 2 snapped to segment 2
        self.assertCueEquals(corrected[1], 2.2, 3.0)

    def test_snap_multi_segment_span(self):
        # One subtitle covering segments 2+3; should snap to 2.2 - 5.0
        subtitles = [
            {"start": 2.15, "end": 5.2, "text": "How are you Nice to meet you", "format": "srt", "language": "en"},
        ]
        corrected = correct_subtitles(self.transcript, subtitles)
        self.assertEqual(len(corrected), 1)
        self.assertCueEquals(corrected[0], 2.2, 5.0)

    def test_hybrid_pipeline_preserves_exact_snap(self):
        # Validate hybrid pipeline does not move exact snapped times in post OTT enforcement
        subtitles = [
            {"start": 0.9, "end": 2.4, "text": "Hello world", "format": "srt", "language": "en"},
            {"start": 2.0, "end": 3.4, "text": "How r you", "format": "srt", "language": "en"},
        ]
        hybrid = hybrid_correct_subtitles(self.transcript, subtitles, audio_file=None, enforce_ott_post=True)
        # hybrid returns list of dicts with index, start, end, text, format
        self.assertEqual(len(hybrid), 2)
        # Both cues should exactly match segment boundaries
        self.assertCueEquals(hybrid[0], 1.0, 2.0)
        self.assertCueEquals(hybrid[1], 2.2, 3.0)

if __name__ == "__main__":
    unittest.main()
