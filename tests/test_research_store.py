"""Dependency-light regression tests for the durable Research OS data layer."""
from __future__ import annotations

import io
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src" / "code"))

from parexa_interface.storage.research_store import ResearchStore  # noqa: E402


class ResearchStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = ResearchStore(Path(self.temp.name) / "research")

    def tearDown(self):
        self.temp.cleanup()

    def test_projects_notes_tasks_and_scope(self):
        first = self.store.project("Ortheon visual research", "Visual reasoning methodology")
        second = self.store.project("Kasta research", "Water systems")
        self.assertEqual(len(self.store.list("projects")), 2)
        note = self.store.create("notes", {
            "title": "Methods", "content": "Baseline and ablation",
            "project_id": first["id"]
        })
        task = self.store.create("tasks", {
            "title": "Reproduce baseline", "priority": "high", "project_id": first["id"]
        })
        self.store.create("tasks", {"title": "Calibrate sensor", "project_id": second["id"]})
        counts = self.store.overview(project_id=first["id"])["counts"]
        self.assertEqual(counts["projects"], 1)
        self.assertEqual(counts["notes"], 1)
        self.assertEqual(counts["open_tasks"], 1)
        self.assertEqual(len(self.store.list("tasks",project_id=first["id"])), 1)
        self.assertEqual(
            self.store.update("tasks",task["id"],{"status":"done"})["status"], "done"
        )
        self.assertEqual(self.store.overview(project_id=first["id"])["counts"]["open_tasks"], 0)
        self.assertEqual(
            self.store.update("notes",note["id"],{"content":"Updated method"})["content"],
            "Updated method"
        )
        self.assertTrue(self.store.delete("notes",note["id"]))
        self.assertFalse(self.store.delete("notes",note["id"]))

    def test_source_preservation_hash_dedup_and_index_status(self):
        project = self.store.project("Asterion source audit")
        raw = b"%PDF-1.7\n1 0 obj\n<< /Type /Catalog >>\nendobj\n%%EOF"
        doc = self.store.archive_stream(io.BytesIO(raw),filename="study.pdf",project_id=project["id"])
        again = self.store.archive_stream(io.BytesIO(raw),filename="study-copy.pdf",project_id=project["id"])
        self.assertNotEqual(doc["id"],again["id"])
        self.assertEqual(doc["sha256"],again["sha256"])
        self.assertEqual(self.store.source_path(doc["id"]).read_bytes(),raw)
        self.assertTrue(self.store.verify(doc["id"])["valid"])
        self.assertEqual(self.store.overview()["counts"]["storage_bytes"],len(raw))
        self.assertEqual(self.store.overview()["counts"]["indexed"],0)
        self.store.mark_indexed(doc["id"],7)
        self.assertEqual(self.store.get("documents",doc["id"])["chunks"],7)
        self.assertEqual(self.store.overview()["counts"]["indexed"],1)
        with self.assertRaises(ValueError):
            self.store.archive_stream(io.BytesIO(b"script"), filename="../../danger.exe")
        with self.assertRaises(ValueError):
            self.store.archive_stream(io.BytesIO(b""),filename="empty.txt")
        with self.assertRaises(ValueError):
            self.store.archive_stream(io.BytesIO(b"x" * 11),filename="too-big.txt",max_bytes=10)

    def test_evidence_references_real_source_and_scope(self):
        first = self.store.project("Project A")
        second = self.store.project("Project B")
        document = self.store.archive_stream(
            io.BytesIO(b"Source text"),filename="paper.txt",project_id=first["id"]
        )
        evidence = self.store.create("evidence", {
            "document_id":document["id"],"project_id":first["id"],
            "claim":"A measurement is given","quote":"Source text","page_label":"2",
        })
        self.assertEqual(evidence["confidence"],"unreviewed")
        with self.assertRaisesRegex(ValueError,"project"):
            self.store.create("evidence",{
                "document_id":document["id"],"project_id":second["id"],
                "claim":"Misfiled claim","quote":"Source text"
            })
        with self.assertRaisesRegex(ValueError,"not found"):
            self.store.create("evidence",{
                "document_id":"fake-id","claim":"Unknown","quote":"Unknown"
            })
        self.assertEqual(len(self.store.list("evidence",project_id=first["id"])),1)

    def test_search_input_and_updates_are_validated(self):
        project = self.store.project("Space and time")
        self.store.create("notes",{"title":"First note","content":"Private details","project_id":project["id"]})
        self.assertEqual(len(self.store.search("First")["notes"]),1)
        self.assertEqual(self.store.search("%")["notes"],[])
        with self.assertRaises(ValueError):
            self.store.create("notes",{"title":"Invalid foreign key","project_id":"missing"})
        with self.assertRaises(ValueError):
            self.store.update("projects",project["id"],{"danger_field":"oops"})
        with self.assertRaises(ValueError):
            self.store.update("projects",project["id"],{"status":"unknown"})
        with self.assertRaises(ValueError):
            self.store.create("experiments",{"title":""})
        self.assertEqual(self.store.update("projects",project["id"],{"status":"paused"})["status"],"paused")


if __name__ == "__main__":
    unittest.main()
