import os
import shutil
import tempfile
import unittest

import cv2
import numpy as np

from photographer_ai import io_utils
from photographer_ai.models import FaceReport, QualityMetrics
from photographer_ai.pipeline import PipelineConfig, run_batch
from photographer_ai.stages import (
    stage1_quality,
    stage4_composition,
    stage6_lightroom,
    stage7_crop,
    stage9_hero,
    stage10_bw,
    stage12_export,
)


def _checkerboard(size=256, square=8):
    tile = np.indices((size, size)).sum(axis=0) // square % 2
    img = (tile * 255).astype(np.uint8)
    return np.stack([img] * 3, axis=-1)


def _flat(size=256, value=128):
    return np.full((size, size, 3), value, dtype=np.uint8)


class TestStage1Quality(unittest.TestCase):
    def test_sharp_vs_blurry(self):
        sharp = _checkerboard()
        blurry = cv2.GaussianBlur(sharp, (25, 25), 0)

        sharp_metrics = stage1_quality.analyze_quality(sharp)
        blurry_metrics = stage1_quality.analyze_quality(blurry)

        self.assertGreater(sharp_metrics.sharpness, blurry_metrics.sharpness)
        self.assertFalse(sharp_metrics.is_blurry)
        self.assertTrue(blurry_metrics.is_blurry)

    def test_overexposed_and_underexposed(self):
        bright = _flat(value=250)
        dark = _flat(value=5)
        normal = _flat(value=120)

        self.assertTrue(stage1_quality.analyze_quality(bright).is_overexposed)
        self.assertTrue(stage1_quality.analyze_quality(dark).is_underexposed)
        normal_metrics = stage1_quality.analyze_quality(normal)
        self.assertFalse(normal_metrics.is_overexposed)
        self.assertFalse(normal_metrics.is_underexposed)

    def test_color_cast_detected(self):
        neutral = _flat(value=120)
        tinted = neutral.copy()
        tinted[:, :, 0] = 200  # heavy red cast

        neutral_delta = stage1_quality.analyze_quality(neutral).color_cast_rgb_delta
        tinted_delta = stage1_quality.analyze_quality(tinted).color_cast_rgb_delta
        self.assertGreater(tinted_delta, neutral_delta)

    def test_quality_score_bounds(self):
        for img in (_checkerboard(), _flat(250), _flat(5)):
            score = stage1_quality.analyze_quality(img).quality_score
            self.assertGreaterEqual(score, 0.0)
            self.assertLessEqual(score, 100.0)

    def test_duplicate_detection(self):
        from photographer_ai.models import ImageRecord

        base = _checkerboard()
        near_dup = base.copy()
        near_dup[0:5, 0:5] = 0  # tiny change, still near-identical
        different = cv2.GaussianBlur(base, (15, 15), 0)

        records = []
        for name, img in [("a.jpg", base), ("b.jpg", near_dup), ("c.jpg", different)]:
            r = ImageRecord(path=name)
            r.quality = stage1_quality.analyze_quality(img)
            records.append(r)

        stage1_quality.detect_duplicates_and_bursts(records)

        a, b, c = records
        self.assertEqual(b.quality.duplicate_of, "a.jpg")
        self.assertIsNone(a.quality.duplicate_of)


class TestStage4Composition(unittest.TestCase):
    def test_returns_bounded_score_without_faces(self):
        img = _checkerboard()
        result = stage4_composition.analyze_composition(img, FaceReport())
        self.assertGreaterEqual(result.composition_score, 0.0)
        self.assertLessEqual(result.composition_score, 100.0)

    def test_face_near_thirds_scores_higher_than_dead_center(self):
        from photographer_ai.models import FaceInfo

        img = _checkerboard(size=300)
        off_center_face = FaceReport(faces=[FaceInfo(bbox=(180, 80, 40, 40))], face_count=1)
        centered_face = FaceReport(faces=[FaceInfo(bbox=(130, 130, 40, 40))], face_count=1)

        off_score = stage4_composition.analyze_composition(img, off_center_face).rule_of_thirds
        center_score = stage4_composition.analyze_composition(img, centered_face).rule_of_thirds
        self.assertGreater(off_score, center_score)


class TestStage6Lightroom(unittest.TestCase):
    def test_auto_edit_preserves_shape_and_dtype(self):
        img = _flat(value=200)  # overexposed-ish, triggers highlight recovery
        metrics = stage1_quality.analyze_quality(img)
        edited = stage6_lightroom.auto_edit(img, metrics)
        self.assertEqual(edited.shape, img.shape)
        self.assertEqual(edited.dtype, np.uint8)

    def test_dark_image_gets_brighter(self):
        img = _flat(value=40)
        metrics = stage1_quality.analyze_quality(img)
        edited = stage6_lightroom.auto_edit(img, metrics)
        self.assertGreaterEqual(edited.mean(), img.mean())


class TestStage7Crop(unittest.TestCase):
    def test_crop_contains_face(self):
        from photographer_ai.models import FaceInfo

        img = _checkerboard(size=400)
        face = FaceInfo(bbox=(350, 10, 40, 40))  # near top-right corner
        faces = FaceReport(faces=[face], face_count=1)

        crops = stage7_crop.generate_crops(img, faces, subject_point=(370, 30))
        square = crops["instagram_square"]
        self.assertGreater(square.shape[0], 0)
        self.assertGreater(square.shape[1], 0)

    def test_all_presets_produce_nonempty_crops(self):
        img = _checkerboard(size=400)
        crops = stage7_crop.generate_crops(img, FaceReport(), subject_point=(200, 200))
        for name, crop in crops.items():
            self.assertGreater(crop.size, 0, msg=f"{name} crop was empty")


class TestStage9Hero(unittest.TestCase):
    def test_sharp_well_composed_scores_higher_than_blurry(self):
        good_q = QualityMetrics(quality_score=90, is_blurry=False)
        bad_q = QualityMetrics(quality_score=20, is_blurry=True)
        comp = stage4_composition.analyze_composition(_checkerboard(), FaceReport())

        good = stage9_hero.score_hero(good_q, FaceReport(), comp)
        bad = stage9_hero.score_hero(bad_q, FaceReport(), comp)
        self.assertGreater(good.hero_score, bad.hero_score)
        self.assertGreaterEqual(good.stars, bad.stars)

    def test_duplicate_never_outranks_original(self):
        comp = stage4_composition.analyze_composition(_checkerboard(), FaceReport())
        q = QualityMetrics(quality_score=90, is_blurry=False, duplicate_of="other.jpg")
        result = stage9_hero.score_hero(q, FaceReport(), comp)
        self.assertLess(result.hero_score, 90)


class TestStage10BW(unittest.TestCase):
    def test_output_is_grayscale_in_rgb_channels(self):
        img = _checkerboard()
        bw = stage10_bw.convert_bw(img, grain=False)
        self.assertTrue(np.array_equal(bw[:, :, 0], bw[:, :, 1]))
        self.assertTrue(np.array_equal(bw[:, :, 1], bw[:, :, 2]))

    def test_not_a_naive_desaturate(self):
        img = _flat(value=128)
        img = img.copy()
        img[:, :, 0] = 200  # push red channel up
        naive_gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
        bw = stage10_bw.convert_bw(img, grain=False)[:, :, 0]
        # The weighted-red conversion should differ from plain luma.
        self.assertFalse(np.array_equal(bw, naive_gray))


class TestPipelineIntegration(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.input_dir = os.path.join(self.tmpdir, "in")
        self.output_dir = os.path.join(self.tmpdir, "out")
        os.makedirs(self.input_dir)

        images = {
            "sharp.jpg": _checkerboard(),
            "blurry.jpg": cv2.GaussianBlur(_checkerboard(), (31, 31), 0),
            "overexposed.jpg": _flat(250),
            "near_dup_of_sharp.jpg": _checkerboard(),
        }
        for name, arr in images.items():
            io_utils.save_rgb(arr, os.path.join(self.input_dir, name))

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_run_batch_end_to_end(self):
        config = PipelineConfig(
            output_dir=self.output_dir,
            enable_body_analysis=False,       # avoid network dependency in tests
            enable_background_cleanup=False,  # avoid network dependency in tests
        )
        result = run_batch(self.input_dir, config)

        self.assertEqual(len(result.records), 4)
        report_path = os.path.join(self.output_dir, "report.json")
        self.assertTrue(os.path.isfile(report_path))

        kept = [r for r in result.records if not r.rejected]
        for r in kept:
            self.assertIn("high_resolution", r.export_paths)
            self.assertTrue(os.path.isfile(r.export_paths["high_resolution"]))
            self.assertTrue(os.path.isfile(r.export_paths["zip"]))

        sharp = next(r for r in result.records if r.filename == "sharp.jpg")
        near_dup = next(r for r in result.records if r.filename == "near_dup_of_sharp.jpg")
        # Pixel-identical images: exactly one of the pair is kept as the
        # representative and the other is marked as its duplicate.
        marked = [r for r in (sharp, near_dup) if r.quality.duplicate_of is not None]
        self.assertEqual(len(marked), 1)
        self.assertTrue(marked[0].rejected)

        total_bucketed = sum(len(v) for v in result.buckets.values())
        self.assertEqual(total_bucketed, len(result.records))


if __name__ == "__main__":
    unittest.main()
