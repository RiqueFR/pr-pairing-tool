import csv
import tempfile

import pytest

from pr_pairing import load_csv, save_csv, load_developers, save_developers, Developer


class TestCSVFunctions:
    def test_load_csv_basic(self, basic_csv_content):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            f.write(basic_csv_content)
            temp_path = f.name

        try:
            rows = load_csv(temp_path)
            
            assert len(rows) == 4
            assert rows[0]["name"] == "Alice"
            assert rows[0]["can_review"] == "true"
        finally:
            import os
            os.unlink(temp_path)

    def test_load_csv_missing_optional_columns(self):
        content = "name,can_review\nAlice,true"
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            f.write(content)
            temp_path = f.name

        try:
            rows = load_csv(temp_path)
            
            assert len(rows) == 1
            assert "team" not in rows[0]
            assert "knowledge_level" not in rows[0]
        finally:
            import os
            os.unlink(temp_path)

    def test_save_csv_adds_reviewers_column(self, temp_csv):
        rows = load_csv(temp_csv)
        
        for row in rows:
            row["reviewers"] = "test"
        
        fieldnames = list(rows[0].keys())
        
        save_csv(temp_csv, rows, fieldnames)
        
        with open(temp_csv, 'r') as f:
            reader = csv.DictReader(f)
            saved_rows = list(reader)
        
        assert "reviewers" in saved_rows[0]


class TestLoadDevelopers:
    def test_load_developers_basic(self):
        content = "name,can_review,team,knowledge_level\nAlice,true,frontend,5\nBob,true,backend,3"
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            f.write(content)
            temp_path = f.name

        try:
            developers = load_developers(temp_path)
            
            assert len(developers) == 2
            assert developers[0].name == "Alice"
            assert developers[0].can_review == True
            assert developers[0].team == "frontend"
            assert developers[0].knowledge_level == 5
            assert developers[1].name == "Bob"
            assert developers[1].knowledge_level == 3
        finally:
            import os
            os.unlink(temp_path)

    def test_load_developers_normalizes_can_review(self):
        content = "name,can_review\nAlice,True\nBob,false\nCharlie,yes"
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            f.write(content)
            temp_path = f.name

        try:
            developers = load_developers(temp_path)
            
            assert developers[0].can_review == True
            assert developers[1].can_review == False
            assert developers[2].can_review == True
        finally:
            import os
            os.unlink(temp_path)

    def test_load_developers_parses_knowledge_level(self):
        content = "name,can_review,knowledge_level\nAlice,3\nBob,invalid\nCharlie,"
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            f.write(content)
            temp_path = f.name

        try:
            developers = load_developers(temp_path)
            
            assert developers[0].knowledge_level == 3
            assert developers[1].knowledge_level == 3
            assert developers[2].knowledge_level == 3
        finally:
            import os
            os.unlink(temp_path)


class TestSaveDevelopers:
    def test_save_developers(self):
        developers = [
            Developer(name="Alice", can_review=True, team="frontend", knowledge_level=5, reviewers=["Bob"]),
            Developer(name="Bob", can_review=True, team="backend", knowledge_level=3, reviewers=[]),
        ]
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            f.write("name,can_review,team,knowledge_level\n")
            temp_path = f.name

        try:
            save_developers(temp_path, developers)
            
            devs = load_developers(temp_path)
            assert len(devs) == 2
            assert devs[0].reviewers == ["Bob"]
        finally:
            import os
            os.unlink(temp_path)
