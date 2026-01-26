import pytest
from src.domain.user import User, Role, Status

class TestUserModel:
    def test_user_valid_ok(self):
        u = User(id="u1", email="a@b.com", role=Role.USER, status=Status.ACTIVE)
        assert u.id == "u1"
        assert u.email == "a@b.com"
        assert u.role is Role.USER
        assert u.status is Status.ACTIVE

    @pytest.mark.parametrize("bad", ["", "   ", None])
    def test_user_invalid_id_raises(self, bad):
        with pytest.raises(ValueError) as e:
            User(id=bad, email="a@b.com", role=Role.USER, status=Status.ACTIVE)
        assert "User.id must be non-empty" in str(e.value)

    @pytest.mark.parametrize("bad", ["a", "a@", "@b.com", "a@b", "a b@c.com", "not-an-email"])
    def test_user_invalid_email_raises(self, bad):
        with pytest.raises(ValueError) as e:
            User(id="u1", email=bad, role=Role.USER, status=Status.ACTIVE)
        assert "invalid email" in str(e.value)

    def test_role_must_be_role_enum(self):
        with pytest.raises(ValueError) as e:
            User(id="u1", email="a@b.com", role="USER", status=Status.ACTIVE)
        assert "role must be Role enum" in str(e.value)

    def test_status_must_be_status_enum(self):
        with pytest.raises(ValueError) as e:
            User(id="u1", email="a@b.com", role=Role.USER, status="ACTIVE")
        assert "status must be Status enum" in str(e.value)