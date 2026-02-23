import csv
import json
import os
import tempfile
from pathlib import Path

import pytest


@pytest.fixture
def basic_csv_content():
    return """name,can_review
Alice,true
Bob,true
Charlie,true
Dana,true"""


@pytest.fixture
def csv_with_teams_content():
    return """name,can_review,team
Alice,true,frontend
Bob,true,frontend
Charlie,true,backend
Dana,true,backend"""


@pytest.fixture
def csv_with_knowledge_content():
    return """name,can_review,knowledge_level
Alice,true,5
Bob,true,1
Charlie,true,3
Dana,true,4"""


@pytest.fixture
def csv_full_content():
    return """name,can_review,team,knowledge_level
Alice,true,frontend,5
Bob,true,frontend,2
Charlie,true,backend,4
Dana,true,backend,1
Eve,true,,3
Frank,false,frontend,5"""


@pytest.fixture
def empty_history():
    return {"pairs": {}, "last_run": None}


@pytest.fixture
def sample_history():
    return {
        "pairs": {
            "Alice": {"Bob": 2, "Charlie": 1},
            "Bob": {"Alice": 2, "Dana": 1}
        },
        "last_run": "2026-02-22T10:00:00Z"
    }


@pytest.fixture
def temp_csv(request, basic_csv_content):
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
        f.write(basic_csv_content)
        temp_path = f.name

    yield temp_path

    if os.path.exists(temp_path):
        os.unlink(temp_path)


@pytest.fixture
def temp_csv_teams(request, csv_with_teams_content):
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
        f.write(csv_with_teams_content)
        temp_path = f.name

    yield temp_path

    if os.path.exists(temp_path):
        os.unlink(temp_path)


@pytest.fixture
def temp_csv_full(request, csv_full_content):
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
        f.write(csv_full_content)
        temp_path = f.name

    yield temp_path

    if os.path.exists(temp_path):
        os.unlink(temp_path)


@pytest.fixture
def temp_history(request, empty_history):
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(empty_history, f)
        temp_path = f.name

    yield temp_path

    if os.path.exists(temp_path):
        os.unlink(temp_path)


@pytest.fixture
def temp_csv_with_reviewers(request, basic_csv_content):
    content = """name,can_review,reviewers
Alice,true,Bob, Charlie
Bob,true,Alice
Charlie,true,Dana
Dana,true,"""

    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
        f.write(content)
        temp_path = f.name

    yield temp_path

    if os.path.exists(temp_path):
        os.unlink(temp_path)
