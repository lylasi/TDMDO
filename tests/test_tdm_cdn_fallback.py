import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = PROJECT_ROOT / ".claude" / "skills" / "tdm" / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

import tdm_core  # noqa: E402


class TdmCdnFallbackTests(unittest.TestCase):
    def test_m3u8_candidates_keep_original_and_add_api_domains(self):
        source = (
            "https://vod3.tdm.com.mo/newweb/video/playelist.m3u8"
        )
        domain_response = {
            "code": 0,
            "data": {
                "domains": {
                    "https://vod3.tdm.com.mo": "https://vod5.tdm.com.mo",
                },
                "videoDomain": "https://vod4.tdm.com.mo",
                "sourceVideoDomain": "https://vod3.tdm.com.mo",
            },
        }

        with patch.object(tdm_core, "_api_get", return_value=domain_response):
            candidates = tdm_core._m3u8_candidates(source)

        self.assertEqual(candidates[0], source)
        self.assertIn(
            "https://vod5.tdm.com.mo/newweb/video/playelist.m3u8",
            candidates,
        )
        self.assertIn(
            "https://vod4.tdm.com.mo/newweb/video/playelist.m3u8",
            candidates,
        )
        self.assertEqual(len(candidates), len(set(candidates)))

    def test_download_video_uses_backup_cdn_after_primary_failure(self):
        primary = "https://vod3.tdm.com.mo/video/playelist.m3u8"
        backup = "https://vod5.tdm.com.mo/video/playelist.m3u8"
        attempted_inputs = []
        attempted_outputs = []

        def fake_ffmpeg(command, progress_callback=None):
            input_url = command[command.index("-i") + 1]
            output_path = Path(command[-1])
            attempted_inputs.append(input_url)
            attempted_outputs.append(output_path)
            output_path.write_bytes(
                b"partial" if input_url == primary else b"complete"
            )
            return input_url == backup

        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "1238553_video.mp4"
            with patch.object(tdm_core, "_HAS_FFMPEG", True), patch.object(
                tdm_core, "_HAS_YTDLP", False
            ), patch.object(
                tdm_core,
                "get_video_info",
                return_value={
                    "title": "測試影片",
                    "m3u8": primary,
                    "length": 203.0,
                },
            ), patch.object(
                tdm_core,
                "_m3u8_candidates",
                return_value=[primary, backup],
            ), patch.object(
                tdm_core, "_run_ffmpeg", side_effect=fake_ffmpeg
            ), patch.object(
                tdm_core, "push_to_webdav", return_value=False
            ), patch.object(
                tdm_core, "init_db"
            ), patch.object(
                tdm_core, "record_download"
            ), patch.object(
                tdm_core, "record_video"
            ):
                result = tdm_core.download_video(
                    news_id="1238553",
                    output=str(output_path),
                    overwrite=True,
                )

            self.assertTrue(result["ok"])
            self.assertEqual(attempted_inputs, [primary, backup])
            self.assertTrue(output_path.exists())
            self.assertEqual(output_path.read_bytes(), b"complete")
            self.assertTrue(all(path != output_path for path in attempted_outputs))
            self.assertEqual(
                {path.name for path in Path(temp_dir).iterdir()},
                {output_path.name},
            )

    def test_ffmpeg_attempt_has_network_timeout(self):
        command = []

        def fake_ffmpeg(current_command, progress_callback=None):
            command.extend(current_command)
            return False

        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "video.mp4"
            with patch.object(
                tdm_core,
                "_m3u8_candidates",
                return_value=["https://vod3.tdm.com.mo/video/playelist.m3u8"],
            ), patch.object(
                tdm_core, "_HAS_YTDLP", False
            ), patch.object(
                tdm_core, "_run_ffmpeg", side_effect=fake_ffmpeg
            ):
                success = tdm_core._download_m3u8_with_fallback(
                    "https://vod3.tdm.com.mo/video/playelist.m3u8",
                    str(output_path),
                )

        self.assertFalse(success)
        self.assertIn("-rw_timeout", command)
        self.assertIn("30000000", command)


if __name__ == "__main__":
    unittest.main()
