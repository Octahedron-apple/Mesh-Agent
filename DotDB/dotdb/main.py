import numpy as np
import pickle
import os

class DataBase:
    def __init__(self, Dimensions, Path):
        self.dimensions = Dimensions
        self.path = Path
        self.DB = []
    def insert(self, point):
        if point.dimensions != self.dimensions:
            raise ValueError("Point dimensions do not match database dimensions")
        self.DB.append(point)
    def save(self):
        with open(self.path, 'wb') as f:
            pickle.dump(self.DB, f)
    def load(self):
        with open(self.path, 'rb') as f:
            self.DB = pickle.load(f)
    def delete(self, text=None):
        if text is None:
            self.DB = []
            if os.path.exists(self.path):
                os.remove(self.path)
        else:
            self.DB = [p for p in self.DB if p.text != text]
    def search(self, point, k):
        if not self.DB:
            return []
        query_vector = np.array(point.embedding)
        query_norm = np.linalg.norm(query_vector)
        db_embeddings = np.array([p.embedding for p in self.DB])
        db_norms = np.linalg.norm(db_embeddings, axis=1)
        similarities = np.zeros(len(self.DB))
        if query_norm != 0:
            valid_norms = db_norms != 0
            dot_products = np.dot(db_embeddings, query_vector)
            similarities[valid_norms] = dot_products[valid_norms] / (query_norm * db_norms[valid_norms])
        top_indices = np.argsort(similarities)[::-1][:k]
        return [(similarities[i], self.DB[i]) for i in top_indices]

class point:
    def __init__(self, text, dimensions, embedding):
        self.text=text
        self.dimensions=dimensions
        self.embedding=embedding


