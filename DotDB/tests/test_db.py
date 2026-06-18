import pytest
import os
import pickle
import urllib.request
import json
from dotdb.main import DataBase, point

TEST_DATA_PATH = "tests/test_data.pkl"
DB_PATH = "tests/test.db"
MODEL_NAME = "qwen3-embedding:0.6b"

sample_texts = [
    "wet cold ",
    "lava hot",
    "light",
    "snake",
    "rabbit"
]

@pytest.fixture(scope="session")
def test_data():
    if os.path.exists(TEST_DATA_PATH):
        with open(TEST_DATA_PATH, 'rb') as f:
            data = pickle.load(f)
    else:
        data = []
        for text in sample_texts:
            try:
                url = "http://localhost:11434/api/embeddings"
                req_data = json.dumps({
                    "model": MODEL_NAME,
                    "prompt": text
                }).encode("utf-8")
                req = urllib.request.Request(url, data=req_data, headers={"Content-Type": "application/json"})
                with urllib.request.urlopen(req) as response:
                    result = json.loads(response.read().decode("utf-8"))
                    embedding = result["embedding"]
                    data.append((text, embedding))
            except Exception as e:
                pytest.fail(f"Failed to generate embedding with Ollama for text '{text}'. Make sure Ollama is running with model {MODEL_NAME}. Error: {e}")
        
        with open(TEST_DATA_PATH, 'wb') as f:
            pickle.dump(data, f)
            
    return data

@pytest.fixture
def db(test_data):
    dim = len(test_data[0][1])
    database = DataBase(Dimensions=dim, Path=DB_PATH)
    yield database
    database.delete()

def test_insert_and_search(db, test_data):
    dim = db.dimensions
    for text, embedding in test_data:
        p = point(text, dim, embedding)
        db.insert(p)
    
    assert len(db.DB) == len(test_data)
    query_text, query_emb = test_data[0]
    query_point = point("query", dim, query_emb)
    
    results = db.search(query_point, k=len(test_data))
    assert len(results) == len(test_data)
    
    for i in range(len(results) - 1):
        assert results[i][0] >= results[i+1][0]
        
    for score, p in results:
        assert isinstance(score, float)
        assert p.text in [t for t, _ in test_data]
        
    score, p = results[0]
    assert p.text == query_text
    assert score > 0.99

def test_save_and_load(db, test_data):
    dim = db.dimensions
    p1 = point(test_data[0][0], dim, test_data[0][1])
    db.insert(p1)
    db.save()
    
    assert os.path.exists(DB_PATH)
    new_db = DataBase(Dimensions=dim, Path=DB_PATH)
    new_db.load()
    
    assert len(new_db.DB) == 1
    assert new_db.DB[0].text == p1.text
    
    new_db.delete()

def test_delete_specific(db, test_data):
    dim = db.dimensions
    p1 = point(test_data[0][0], dim, test_data[0][1])
    p2 = point(test_data[1][0], dim, test_data[1][1])
    db.insert(p1)
    db.insert(p2)
    db.delete(text=p1.text)
    assert len(db.DB) == 1
    assert db.DB[0].text == p2.text

def test_delete_all(db, test_data):
    dim = db.dimensions
    p1 = point(test_data[0][0], dim, test_data[0][1])
    db.insert(p1)
    db.save()
    db.delete()
    assert len(db.DB) == 0
    assert not os.path.exists(DB_PATH)
