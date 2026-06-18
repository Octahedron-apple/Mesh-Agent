# DotDB

DotDB is a lightweight Python library for vector database functionality. It provides a simple way to store, manage, and perform similarity searches on high-dimensional data points.

## Features

* **Vector Storage**: Store multi-dimensional embeddings associated with text data.
* **Similarity Search**: Perform efficient cosine similarity searches to find the most relevant items for a given query vector.
* **Persistence**: Save and load your database to/from disk using Python's `pickle` format.
* **Data Management**: Easily insert, delete specific entries by text, or clear the entire database.

## Installation

You can install DotDB directly from PyPI:

```bash
pip install dotdb

```

## Quick Start

```python
from dotdb.main import DataBase, point

# Initialize the database with vector dimensions
# For example, if your embeddings have 768 dimensions
db = DataBase(Dimensions=768, Path="my_data.db")

# Create a point and insert it
p = point(text="example text", dimensions=768, embedding=[0.1, 0.2, ...])
db.insert(p)

# Save the database
db.save()

# Perform a search (returns top k results)
query_p = point(text="query", dimensions=768, embedding=[0.1, 0.15, ...])
results = db.search(query_p, k=5)

# Delete an entry
db.delete(text="example text")

```

## API Overview

### `DataBase` Class

* `__init__(Dimensions, Path)`: Initializes the database instance.
* `insert(point)`: Adds a new data point to the database.
* `save()`: Serializes the current database state to the specified path.
* `load()`: Loads the database state from the specified path.
* `search(point, k)`: Returns the top `k` most similar points based on cosine similarity.
* `delete(text=None)`: If `text` is provided, removes that point. If `None`, clears the entire database and deletes the file.

### `point` Class

* `__init__(text, dimensions, embedding)`: Represents a data point with associated text and its vector embedding.
