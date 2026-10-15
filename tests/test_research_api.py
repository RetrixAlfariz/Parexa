"""HTTP contract tests using only Flask; no AI model server or vector engine needed."""
from __future__ import annotations

import io
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src" / "code"))

from flask import Flask  # noqa: E402
from parexa_interface import research_api  # noqa: E402
from parexa_interface.storage.research_store import ResearchStore  # noqa: E402


class ResearchApiTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store_patch = patch.object(
            research_api, "store", ResearchStore(Path(self.temp.name) / "research")
        )
        self.store_patch.start()
        app = Flask(__name__)
        app.config["TESTING"] = True
        app.register_blueprint(research_api.bp)
        self.client = app.test_client()

    def tearDown(self):
        self.store_patch.stop()
        self.temp.cleanup()

    def test_create_archive_verify_download_and_evidence(self):
        project = self.client.post("/api/research/projects",json={"title":"Robotics literature"})
        self.assertEqual(project.status_code,201)
        project_id = project.get_json()["id"]
        raw = b"%PDF-1.4\n% test pdf data\n%%EOF\n"
        upload = self.client.post("/api/research/documents",data={
            "file":(io.BytesIO(raw),"robotics.pdf"),
            "project_id":project_id,
        },content_type="multipart/form-data")
        self.assertEqual(upload.status_code,201,upload.get_data(as_text=True))
        document = upload.get_json()
        self.assertEqual(document["index_status"],"stored")
        self.assertEqual(document["project_id"],project_id)
        check = self.client.get("/api/research/documents/" + document["id"] + "/verify")
        self.assertTrue(check.get_json()["valid"])
        download = self.client.get("/api/research/documents/" + document["id"] + "/download")
        self.assertEqual(download.status_code,200)
        self.assertEqual(download.data,raw)
        self.assertIn("attachment",download.headers.get("Content-Disposition",""))
        evidence = self.client.post("/api/research/evidence",json={
            "project_id":project_id,"document_id":document["id"],
            "claim":"Calibration requires traceability","quote":"test pdf data",
            "page_label":"1"
        })
        self.assertEqual(evidence.status_code,201,evidence.get_data(as_text=True))
        scoped = self.client.get("/api/research/overview?project_id=" + project_id).get_json()
        self.assertEqual(scoped["counts"]["documents"],1)
        self.assertEqual(scoped["counts"]["evidence"],1)
        self.assertEqual(scoped["counts"]["indexed"],0)

    def test_errors_are_explicit_and_non_destructive(self):
        self.assertEqual(self.client.post("/api/research/projects",json=[]).status_code,400)
        self.assertEqual(self.client.post("/api/research/documents",data={}).status_code,400)
        self.assertEqual(self.client.post("/api/research/documents",data={
            "file":(io.BytesIO(b"unsafe"),"run.exe")
        },content_type="multipart/form-data").status_code,400)
        self.assertEqual(self.client.get("/api/research/documents/unknown/download").status_code,404)
        self.assertEqual(self.client.patch("/api/research/tasks/nope",json={"status":"done"}).status_code,404)
        self.assertEqual(self.client.post("/api/research/tasks",json={
            "title":"Do work","status":"fictional"
        }).status_code,400)
        self.assertEqual(self.client.post("/api/research/not_a_resource",json={}).status_code,404)

    def test_notes_and_search(self):
        created = self.client.post("/api/research/notes",json={
            "title":"Baseline report","content":"Use transparent error bars"
        })
        self.assertEqual(created.status_code,201)
        note_id = created.get_json()["id"]
        self.assertEqual(len(self.client.get("/api/research/search?q=Baseline").get_json()["notes"]),1)
        updated = self.client.patch("/api/research/notes/"+note_id,json={"content":"Revised"})
        self.assertEqual(updated.get_json()["content"],"Revised")
        self.assertEqual(self.client.delete("/api/research/notes/"+note_id).status_code,200)
        self.assertEqual(self.client.get("/api/research/notes/"+note_id).status_code,404)
        self.assertEqual(self.client.get("/api/research/system").status_code,200)


if __name__ == "__main__":
    unittest.main()
