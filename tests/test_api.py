from __future__ import annotations

from fastapi.testclient import TestClient

from backend.api import app


client = TestClient(app)


def test_root():
    response = client.get("/")

    assert response.status_code == 200
    assert response.json() == {
        "name": "Draft Cave API",
        "status": "running",
    }


def test_health():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
    }


def test_players_endpoint():
    response = client.get("/players")

    assert response.status_code == 200

    data = response.json()

    assert data["player_count"] > 0
    assert data["matched_projection_rows"] >= 0
    assert data["unresolved_rows"] >= 0

    assert (
        data["players_with_projection"]
        + data["players_missing_projection"]
        == data["player_count"]
    )

    assert len(data["players"]) == data["player_count"]

    required_fields = {
        "dk_id",
        "name",
        "position",
        "team",
        "opponent",
        "salary",
        "projection",
    }

    for player in data["players"]:
        assert required_fields.issubset(
            player.keys()
        )


def test_test_optimize_endpoint():
    response = client.get("/test-optimize")

    assert response.status_code == 200

    data = response.json()

    assert data["requested_lineups"] == 5
    assert data["generated_lineups"] == 5
    assert len(data["lineups"]) == 5


def test_optimize_basic_request():
    response = client.post(
        "/optimize",
        json={
            "num_lineups": 3,
            "minimum_uniques": 1,
            "random_seed": 42,
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["requested_lineups"] == 3
    assert data["generated_lineups"] == 3
    assert data["minimum_uniques"] == 1
    assert data["random_seed"] == 42
    assert len(data["lineups"]) == 3


def test_optimize_lineup_serialization():
    response = client.post(
        "/optimize",
        json={
            "num_lineups": 1,
            "minimum_uniques": 1,
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["generated_lineups"] == 1

    lineup = data["lineups"][0]

    assert "total_salary" in lineup
    assert "total_projection" in lineup
    assert "players" in lineup

    assert lineup["total_salary"] <= 50000
    assert lineup["total_projection"] > 0

    expected_slots = {
        "QB",
        "RB1",
        "RB2",
        "WR1",
        "WR2",
        "WR3",
        "TE",
        "FLEX",
        "DST",
    }

    assert set(lineup["players"]) == expected_slots

    required_player_fields = {
        "dk_id",
        "name",
        "team",
        "opponent",
        "position",
        "salary",
        "projection",
    }

    for player in lineup["players"].values():
        assert required_player_fields.issubset(
            player.keys()
        )


def test_optimize_echoes_settings():
    response = client.post(
        "/optimize",
        json={
            "num_lineups": 2,
            "minimum_uniques": 1,
            "min_salary": 45000,
            "randomization_pct": 0.2,
            "random_seed": 99,
            "qb_stack_min": 1,
            "qb_stack_max": 2,
            "require_bringback": True,
            "sim_same_team_pct": 0.2,
            "sim_opponent_pct": 0.07,
            "projection_weight": 1.0,
            "position_player_caps": {
                "QB": 1.0,
            },
            "flex_position_caps": {
                "TE": 1.0,
            },
            "max_offense_vs_opposing_dst": 8,
            "max_qb_with_same_team_dst": 1,
            "max_qb_with_same_team_rb": 1,
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["requested_lineups"] == 2
    assert data["minimum_uniques"] == 1
    assert data["min_salary"] == 45000
    assert data["randomization_pct"] == 0.2
    assert data["random_seed"] == 99
    assert data["qb_stack_min"] == 1
    assert data["qb_stack_max"] == 2
    assert data["require_bringback"] is True
    assert data["sim_same_team_pct"] == 0.2
    assert data["sim_opponent_pct"] == 0.07
    assert data["projection_weight"] == 1.0

    assert data["position_player_caps"] == {
        "QB": 1.0,
    }

    assert data["flex_position_caps"] == {
        "TE": 1.0,
    }

    assert data["max_offense_vs_opposing_dst"] == 8
    assert data["max_qb_with_same_team_dst"] == 1
    assert data["max_qb_with_same_team_rb"] == 1


def test_unknown_player_id_rejected():
    response = client.post(
        "/optimize",
        json={
            "num_lineups": 1,
            "minimum_uniques": 1,
            "lock_players": [0],
        },
    )

    assert response.status_code == 422

    data = response.json()

    assert (
        data["detail"]
        == "Unknown DraftKings player IDs for the current slate: 0"
    )


def test_lock_exclude_conflict_rejected():
    response = client.post(
        "/optimize",
        json={
            "lock_players": [123],
            "exclude_players": [123],
        },
    )

    assert response.status_code == 422

    body = response.text

    assert (
        "Players cannot be both locked and excluded: 123"
        in body
    )


def test_qb_stack_min_greater_than_max_rejected():
    response = client.post(
        "/optimize",
        json={
            "qb_stack_min": 2,
            "qb_stack_max": 1,
        },
    )

    assert response.status_code == 422

    assert (
        "qb_stack_min must be less than or equal to qb_stack_max"
        in response.text
    )


def test_invalid_player_max_exposure_rejected():
    response = client.post(
        "/optimize",
        json={
            "player_max_exposure": {
                "123": 1.1,
            },
        },
    )

    assert response.status_code == 422

    assert (
        "player_max_exposure for 123 must be between 0.0 and 1.0"
        in response.text
    )


def test_player_min_above_max_rejected():
    response = client.post(
        "/optimize",
        json={
            "player_min_exposure": {
                "123": 0.8,
            },
            "player_max_exposure": {
                "123": 0.4,
            },
        },
    )

    assert response.status_code == 422

    assert (
        "player_min_exposure for 123 must be less than or equal to player_max_exposure"
        in response.text
    )


def test_invalid_position_cap_position_rejected():
    response = client.post(
        "/optimize",
        json={
            "position_player_caps": {
                "K": 0.5,
            },
        },
    )

    assert response.status_code == 422

    assert (
        "position_player_caps contains unsupported position: K"
        in response.text
    )


def test_invalid_flex_position_rejected():
    response = client.post(
        "/optimize",
        json={
            "flex_position_caps": {
                "QB": 0.5,
            },
        },
    )

    assert response.status_code == 422

    assert (
        "flex_position_caps contains unsupported position: QB"
        in response.text
    )


def test_randomization_above_one_rejected():
    response = client.post(
        "/optimize",
        json={
            "randomization_pct": 1.1,
        },
    )

    assert response.status_code == 422


def test_negative_random_seed_rejected():
    response = client.post(
        "/optimize",
        json={
            "random_seed": -1,
        },
    )

    assert response.status_code == 422


def test_qb_stack_value_above_eight_rejected():
    response = client.post(
        "/optimize",
        json={
            "qb_stack_max": 9,
        },
    )

    assert response.status_code == 422


def test_advanced_constraint_bounds_rejected():
    response = client.post(
        "/optimize",
        json={
            "max_qb_with_same_team_dst": 2,
        },
    )

    assert response.status_code == 422


def test_num_lineups_zero_rejected():
    response = client.post(
        "/optimize",
        json={
            "num_lineups": 0,
        },
    )

    assert response.status_code == 422


def test_minimum_uniques_zero_rejected():
    response = client.post(
        "/optimize",
        json={
            "minimum_uniques": 0,
        },
    )

    assert response.status_code == 422


def test_min_salary_above_cap_rejected():
    response = client.post(
        "/optimize",
        json={
            "min_salary": 50001,
        },
    )

    assert response.status_code == 422