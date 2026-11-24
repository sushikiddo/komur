"""Dilim 3 testleri: acoustic_engine, sounds.py ve audio.py entegrasyonu."""
from __future__ import annotations

import io
import os
import random
import sys
import types
import unittest
from unittest import mock
import wave

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import acoustic_engine as ae
import audio
import sounds


def _read_wav_meta(wav_bytes: bytes) -> tuple[int, int, int, int]:
    with wave.open(io.BytesIO(wav_bytes), "rb") as w:
        return w.getnchannels(), w.getsampwidth(), w.getframerate(), w.getnframes()


class SpatialPanTests(unittest.TestCase):
    def test_pan_volumes_extremes_and_center(self):
        left, right = ae.pan_volumes(0, 1920, master_vol=1.0)
        self.assertAlmostEqual(left, 1.0, places=5)
        self.assertAlmostEqual(right, 0.0, places=5)

        left, right = ae.pan_volumes(1920, 1920, master_vol=1.0)
        self.assertAlmostEqual(left, 0.0, places=5)
        self.assertAlmostEqual(right, 1.0, places=5)

        left, right = ae.pan_volumes(960, 1920, master_vol=0.8)
        self.assertAlmostEqual(left, right, places=5)
        self.assertGreater(left, 0.5)
        self.assertLessEqual(left, 0.8)

    def test_pan_volumes_clamps_out_of_bounds_and_zero_width(self):
        self.assertEqual(ae.pan_volumes(-200, 1000, 1.0), (1.0, 0.0))
        self.assertEqual(ae.pan_volumes(5000, 1000, 0.5), (0.0, 0.5))
        l0, r0 = ae.pan_volumes(100, 0, 1.0)
        self.assertAlmostEqual(l0, r0, places=5)

    def test_apply_channel_pan_and_stereo_wav_pan(self):
        channel = mock.MagicMock()
        left, right = ae.apply_channel_pan(channel, 0, 1000, 0.6)
        channel.set_volume.assert_called_once_with(left, right)

        mono_wav = ae.samples_to_wav([0.5] * 200)
        stereo_wav = ae.pan_wav_stereo(mono_wav, 1000, 1000, master_vol=1.0)
        ch, sw, rate, frames = _read_wav_meta(stereo_wav)
        self.assertEqual(ch, 2)
        self.assertEqual(sw, 2)
        self.assertEqual(rate, ae.SAMPLE_RATE)
        self.assertEqual(frames, 200)
        channels, _ = ae.wav_to_channels(stereo_wav)
        self.assertAlmostEqual(max(abs(x) for x in channels[0]), 0.0, places=3)
        self.assertGreater(max(abs(x) for x in channels[1]), 0.4)


class DynamicPurrTests(unittest.TestCase):
    def test_compute_purr_params_range(self):
        f_min, v_min = ae.compute_purr_params(0.0)
        self.assertEqual((f_min, v_min), (24.0, 0.2))

        f_max, v_max = ae.compute_purr_params(5000.0, max_speed=1500.0)
        self.assertEqual((f_max, v_max), (34.0, 0.9))

        f_mid, v_mid = ae.compute_purr_params(750.0, max_speed=1500.0)
        self.assertAlmostEqual(f_mid, 29.0, places=3)
        self.assertAlmostEqual(v_mid, 0.55, places=3)

    def test_dynamic_purr_controller_and_synthesis(self):
        ctrl = ae.DynamicPurrController(max_speed=1000.0, smoothing=1.0)
        st = ctrl.update(1000.0, petting=True)
        self.assertTrue(st["active"])
        self.assertEqual(st["freq"], 34.0)
        self.assertEqual(st["volume"], 0.9)

        wav_bytes = ctrl.synthesize(duration=0.2)
        ch, _, _, frames = _read_wav_meta(wav_bytes)
        self.assertEqual(ch, 1)
        self.assertEqual(frames, int(ae.SAMPLE_RATE * 0.2))

        ctrl.stop()
        self.assertFalse(ctrl.active)
        self.assertEqual(ctrl.volume, 0.0)


class PitchShiftTests(unittest.TestCase):
    def test_random_pitch_factor_bounds(self):
        rng = random.Random(123)
        factors = [ae.random_pitch_factor(rng=rng) for _ in range(50)]
        self.assertTrue(all(0.90 <= f <= 1.10 for f in factors))
        self.assertGreater(len(set(factors)), 10)

    def test_pitch_shift_wav_changes_length_and_preserves_rate(self):
        src = ae.samples_to_wav([0.4 * ((i % 20) / 20.0 - 0.5) for i in range(1000)])
        up = ae.pitch_shift_wav(src, 1.10)
        down = ae.pitch_shift_wav(src, 0.90)
        _, _, rate_up, frames_up = _read_wav_meta(up)
        _, _, rate_dn, frames_dn = _read_wav_meta(down)
        self.assertEqual(rate_up, ae.SAMPLE_RATE)
        self.assertEqual(rate_dn, ae.SAMPLE_RATE)
        self.assertLess(frames_up, 1000)
        self.assertGreater(frames_dn, 1000)

    def test_invalid_pitch_shift_raises(self):
        with self.assertRaises(ValueError):
            ae.pitch_shift_samples([0.1, 0.2], 0.0)


class StepSoundTests(unittest.TestCase):
    def test_surface_mapping_and_spectral_difference(self):
        self.assertEqual(ae.step_sound_name("window"), "step_window")
        self.assertEqual(ae.step_sound_name("desktop"), "step_desktop")

        win_samples = ae.generate_step_window_samples()
        desk_samples = ae.generate_step_desktop_samples()
        # Pencere tıkırtısı daha yüksek frekanslı (daha fazla sıfır geçişi) olmalı
        def zero_crossings(xs):
            return sum(1 for a, b in zip(xs, xs[1:]) if (a >= 0) != (b >= 0))

        self.assertGreater(zero_crossings(win_samples), zero_crossings(desk_samples))
        self.assertEqual(_read_wav_meta(ae.generate_step_wav("window"))[0], 1)
        self.assertEqual(_read_wav_meta(ae.generate_step_wav("desktop"))[0], 1)


class KeyboardReactiveTests(unittest.TestCase):
    def test_triggers_at_4_kps_with_cooldown(self):
        kb = ae.KeyboardReactiveAudio(threshold_kps=4.0, cooldown_sec=5.0, window_sec=1.0)
        # 3 tuş/sn tetiklemez
        for t in (1.0, 1.2, 1.4):
            self.assertIsNone(kb.record_keystroke(now=t))
        # 4. tuş 1sn içinde -> 4.0 kps -> tetikler
        self.assertEqual(kb.record_keystroke(now=1.6), "keyboard_trill")
        # Cooldown içinde tekrar tetiklemez
        self.assertIsNone(kb.record_keystroke(now=2.0))
        self.assertIsNone(kb.evaluate_rate(6.0, now=4.0))
        # Cooldown sonrası yeniden tetikler
        self.assertEqual(kb.evaluate_rate(4.5, now=7.0), "keyboard_trill")


class LofiAmbienceTests(unittest.TestCase):
    def test_generate_lofi_ambience_wav_and_player(self):
        wav_bytes = ae.generate_lofi_ambience_wav(duration=1.0)
        ch, sw, rate, frames = _read_wav_meta(wav_bytes)
        self.assertEqual((ch, sw, rate, frames), (1, 2, ae.SAMPLE_RATE, ae.SAMPLE_RATE))

        fake_channel = mock.MagicMock()
        fake_sound = mock.MagicMock()
        fake_sound.play.return_value = fake_channel
        fake_mixer = mock.MagicMock()
        fake_mixer.get_init.return_value = (22050, -16, 2)
        fake_mixer.Sound.return_value = fake_sound

        with mock.patch.object(ae, "pygame", types.SimpleNamespace(mixer=fake_mixer)):
            player = ae.LofiAmbiencePlayer(duration=0.5)
            self.assertTrue(player.start(master_vol=0.4, cat_x=0, screen_w=1000))
            self.assertTrue(player.is_playing)
            fake_sound.play.assert_called_once_with(loops=-1)
            fake_channel.set_volume.assert_called()
            player.stop()
            self.assertFalse(player.is_playing)
            fake_channel.stop.assert_called_once()


class AudioAndSoundsIntegrationTests(unittest.TestCase):
    def test_audio_makers_and_pitch_shift(self):
        for name in ("step_window", "step_desktop", "lofi_ambience"):
            self.assertIn(name, audio._MAKERS)
            clip = audio._clip(name)
            self.assertIsNotNone(clip)
            self.assertGreater(len(clip), 44)

        base_clip = audio._clip("meow")
        shifted_clip = audio._clip("meow", pitch_shift=1.10)
        self.assertNotEqual(len(base_clip), len(shifted_clip))

    def test_sounds_init_stereo_and_play_pan_and_pitch_shift(self):
        fake_channel = mock.MagicMock()
        fake_sound = mock.MagicMock()
        fake_sound.play.return_value = fake_channel
        fake_mixer = mock.MagicMock()
        fake_mixer.Sound.return_value = fake_sound

        tmp_wav = ae.samples_to_wav([0.2] * 400)
        tmp_path = os.path.join(ROOT, "tests", "_tmp_meow.wav")
        with open(tmp_path, "wb") as f:
            f.write(tmp_wav)

        try:
            with mock.patch.object(sounds, "pygame", types.SimpleNamespace(mixer=fake_mixer)), \
                 mock.patch.object(sounds, "_mixer_initialized", False), \
                 mock.patch.object(sounds, "_full_path", return_value=tmp_path):
                sounds._init_mixer()
                fake_mixer.init.assert_called_once_with(
                    frequency=22050, size=-16, channels=2, buffer=512
                )
                # Doğrudan arka plan iş parçacığını senkron bekleyerek pan & pitch_shift doğrula
                threads = []
                orig_thread = sounds.threading.Thread

                def capture_thread(*args, **kwargs):
                    t = orig_thread(*args, **kwargs)
                    threads.append(t)
                    return t

                with mock.patch.object(sounds.threading, "Thread", side_effect=capture_thread):
                    sounds.play(
                        "meow",
                        enabled=True,
                        volume=80,
                        pan_x=0,
                        screen_w=1920,
                        pitch_shift=1.05,
                    )
                for t in threads:
                    t.join(timeout=2)

                fake_mixer.Sound.assert_called_once()
                arg = fake_mixer.Sound.call_args[0][0]
                self.assertIsInstance(arg, io.BytesIO)
                fake_channel.set_volume.assert_called_once()
                l_vol, r_vol = fake_channel.set_volume.call_args[0]
                self.assertAlmostEqual(l_vol, 0.8, places=5)
                self.assertAlmostEqual(r_vol, 0.0, places=5)
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)


if __name__ == "__main__":
    unittest.main()
