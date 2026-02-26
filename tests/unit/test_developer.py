from pr_pairing import Developer


class TestDeveloperModel:
    def test_developer_to_dict(self):
        dev = Developer(
            name="Alice",
            can_review=True,
            team="frontend",
            knowledge_level=5,
            reviewers=["Bob", "Charlie"]
        )
        
        d = dev.to_dict()
        
        assert d["name"] == "Alice"
        assert d["can_review"] == True
        assert d["team"] == "frontend"
        assert d["knowledge_level"] == 5
        assert d["reviewers"] == "Bob, Charlie"

    def test_developer_to_dict_with_metadata(self):
        dev = Developer(
            name="Alice",
            can_review=True,
            team="frontend",
            knowledge_level=5,
            reviewers=["Bob"],
            metadata={"email": "alice@example.com"}
        )
        
        d = dev.to_dict()
        
        assert d["name"] == "Alice"
        assert d["email"] == "alice@example.com"
