import unittest
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
from app import tdm_web


class WebConfigApiTests(unittest.TestCase):
    def setUp(self):
        self.client = tdm_web.app.test_client()

    def test_web_config_flow(self):
        # 1. 若開啟認證，匿名存取應回傳 401
        if tdm_web._AUTH_ENABLED:
            anon_res = self.client.get("/api/config")
            self.assertEqual(anon_res.status_code, 401)

            # 模擬使用合法密碼登入
            token = next(iter(tdm_web._AUTH_TOKENS))
            self.client.set_cookie("tdmdo_auth", token)

        # 2. 認證後存取 /api/config
        cfg_res = self.client.get("/api/config")
        self.assertEqual(cfg_res.status_code, 200)
        data = cfg_res.get_json()
        self.assertTrue(data.get("ok"))

        # 驗證包含完整分類結構
        for key in ["env_files", "paths", "auth", "remote", "webdav", "push", "runtime"]:
            self.assertIn(key, data, f"Missing section: {key}")

        # 驗證脫敏安全：不洩露敏感密鑰
        push_info = data["push"]
        self.assertNotIn("1684615309:AA", push_info.get("tg_token_masked", ""))
        if push_info.get("tg_token_configured"):
            self.assertIn("****", push_info["tg_token_masked"])

        # 3. 測試 POST /api/config/reload 熱重載
        reload_res = self.client.post("/api/config/reload")
        self.assertEqual(reload_res.status_code, 200)
        reload_data = reload_res.get_json()
        self.assertTrue(reload_data.get("ok"))
        self.assertIn("config", reload_data)

        # 4. 測試首頁 HTML
        index_res = self.client.get("/")
        self.assertEqual(index_res.status_code, 200)
        html = index_res.data.decode("utf-8")
        self.assertIn("tab-config", html)
        self.assertIn("系統參數", html)


if __name__ == "__main__":
    unittest.main()
