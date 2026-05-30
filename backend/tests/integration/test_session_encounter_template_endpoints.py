from sqlalchemy.orm.attributes import flag_modified

from services.location_graph_service import build_location_graph_from_module


async def _auth_headers(client, sample_user):
    response = await client.post("/auth/login", json={
        "username": sample_user.username,
        "password": "password",
    })
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['token']}"}


async def test_session_encounter_template_can_be_selected(
    client,
    db_session,
    sample_user,
    sample_module,
    sample_session,
):
    parsed = {
        "scenes": [{
            "id": "yard",
            "title": "Training Yard",
            "description": "A construct patrol guards the low walls.",
        }],
        "monsters": [{
            "name": "Clockwork Construct",
            "cr": "1",
            "xp": 200,
            "ac": 14,
            "hp": 22,
        }],
    }
    graph = build_location_graph_from_module(parsed)
    sample_module.parsed_content = parsed
    sample_session.game_state = {
        **(sample_session.game_state or {}),
        "location_graph": graph,
    }
    flag_modified(sample_module, "parsed_content")
    flag_modified(sample_session, "game_state")
    await db_session.commit()
    headers = await _auth_headers(client, sample_user)

    template_id = graph["encounter_templates"][0]["id"]
    response = await client.post(
        f"/game/sessions/{sample_session.id}/encounter-template/select",
        headers=headers,
        json={"template_id": template_id},
    )

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["template"]["id"] == template_id
    assert data["location_graph"]["selected_encounter_template_id"] == template_id
    assert data["location_graph"]["encounter_templates"][0]["selected"] is True


async def test_session_encounter_template_rejects_unknown_template(
    client,
    sample_user,
    sample_session,
):
    headers = await _auth_headers(client, sample_user)

    response = await client.post(
        f"/game/sessions/{sample_session.id}/encounter-template/select",
        headers=headers,
        json={"template_id": "missing"},
    )

    assert response.status_code == 400
