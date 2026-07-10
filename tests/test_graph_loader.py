def test_clear_workbook_batches_deletes_without_optional_match_product(monkeypatch):
    from app.graph import loader

    remaining = {
        "Run": [0],
        "Finding": [0],
        "Cell": [loader.BATCH_SIZE, 1, 0],
        "Sheet": [0],
    }
    calls = []

    def fake_run(query, **params):
        calls.append((query, params))
        if "MATCH (n:" not in query:
            return []
        label = query.split("MATCH (n:", 1)[1].split(" ", 1)[0]
        return [{"deleted": remaining[label].pop(0)}]

    monkeypatch.setattr(loader, "run", fake_run)

    loader.clear_workbook("wb-1")

    queries = [query for query, _ in calls]
    cell_deletes = [query for query in queries if "MATCH (n:Cell" in query]
    assert len(cell_deletes) == 3
    assert all("OPTIONAL MATCH" not in query for query in queries)
    assert all(params["wb"] == "wb-1" for _, params in calls)
