# -*- coding: utf-8 -*-
"""Tests for /v1/cluster API endpoint."""


import random
import uuid

import pytest

from cephlcm.common.models import cluster
from cephlcm.common.models import server
from cephlcm.common.models import user


@pytest.fixture
def normal_user(sudo_user, fake):
    return user.UserModel.make_user(
        str(uuid.uuid4()),
        "qwerty",
        "{0}@example.com".format(uuid.uuid4()),
        str(uuid.uuid4()), [],
        initiator_id=sudo_user.model_id
    )


@pytest.fixture
def mongo_collection(pymongo_connection):
    return pymongo_connection.db.cluster


@pytest.fixture
def clean_cluster_collection(mongo_collection):
    mongo_collection.remove({})


@pytest.fixture
def config(fake, configure_model):
    osds = [create_server(fake) for _ in range(random.randint(1, 10))]
    rgws = [create_server(fake) for _ in range(random.randint(1, 10))]
    mons = [create_server(fake) for _ in range(random.randint(1, 10))] \
        + rgws[:2]
    mds = [create_server(fake) for _ in range(random.randint(1, 10))] \
        + [mons[0]]

    return {
        "osds": osds,
        "rgws": rgws,
        "mons": mons,
        "mds": mds
    }


def create_server(fake):
    name = str(uuid.uuid4())
    username = str(uuid.uuid4())
    fqdn = str(uuid.uuid4())
    ip = fake.ipv4()
    initiator_id = str(uuid.uuid4())

    return server.ServerModel.create(name, username, fqdn, ip,
                                     initiator_id=initiator_id)


def test_api_get_access(sudo_client_v1, client_v1, sudo_user, freeze_time,
                        normal_user):
    response = client_v1.get("/v1/cluster/")
    assert response.status_code == 401
    assert response.json["error"] == "Unauthorized"

    client_v1.login(normal_user.login, "qwerty")
    response = client_v1.get("/v1/cluster/")
    assert response.status_code == 403
    assert response.json["error"] == "Forbidden"

    response = sudo_client_v1.get("/v1/cluster/")
    assert response.status_code == 200


def test_get_cluster(sudo_client_v1, clean_cluster_collection, config,
                     freeze_time):
    initiator_id = str(uuid.uuid4())
    name = str(uuid.uuid4())
    execution_id = str(uuid.uuid4())
    clstr = cluster.ClusterModel.create(name, config, execution_id,
                                        initiator_id)
    freeze_time.return_value += 1
    clstr.save()

    response = sudo_client_v1.get("/v1/cluster/")
    assert response.status_code == 200
    assert response.json["total"] == 1
    assert len(response.json["items"]) == 1

    response_model = response.json["items"][0]
    assert response_model["model"] == cluster.ClusterModel.MODEL_NAME
    assert response_model["id"] == clstr.model_id
    assert response_model["time_updated"] == int(freeze_time.return_value)
    assert response_model["time_deleted"] == 0
    assert response_model["version"] == 3

    response = sudo_client_v1.get(
        "/v1/cluster/{0}/".format(response_model["id"])
    )
    assert response.status_code == 200
    assert response.json == response_model

    response = sudo_client_v1.get(
        "/v1/cluster/{0}/version/".format(response_model["id"])
    )
    assert response.status_code == 200
    assert response.json["total"] == 3
    assert len(response.json["items"]) == 3
    # sorted by version
    assert response.json["items"][0] == response_model

    response = sudo_client_v1.get(
        "/v1/cluster/{0}/version/3/".format(response_model["id"])
    )
    assert response.status_code == 200
    assert response.json == response_model

    response = sudo_client_v1.get(
        "/v1/cluster/{0}/version/20/".format(response_model["id"])
    )
    assert response.status_code == 404


def test_create_new_cluster(sudo_client_v1, normal_user, client_v1):
    request = {"name": str(uuid.uuid4())}

    response = client_v1.post("/v1/cluster/", data=request)
    assert response.status_code == 401

    client_v1.login(normal_user.login, "qwerty")
    response = client_v1.post("/v1/cluster/", data=request)
    assert response.status_code == 403

    response = sudo_client_v1.post("/v1/cluster/", data=request)
    assert response.status_code == 200
    assert response.json["data"] == {
        "name": request["name"],
        "execution_id": None,
        "configuration": {}
    }


def test_create_cluster_same_name(sudo_client_v1):
    request = {"name": str(uuid.uuid4())}
    response = sudo_client_v1.post("/v1/cluster/", data=request)
    response = sudo_client_v1.post("/v1/cluster/", data=request)
    assert response.status_code == 400


def test_update_cluster_onlyname(sudo_client_v1, normal_user, client_v1,
                                 config):
    initiator_id = str(uuid.uuid4())
    name = str(uuid.uuid4())
    execution_id = str(uuid.uuid4())
    clstr = cluster.ClusterModel.create(name, config, execution_id,
                                        initiator_id)

    api_model = clstr.make_api_structure()
    del api_model["data"]["configuration"]["rgws"]
    api_model["data"]["execution_id"] = str(uuid.uuid4())
    api_model["data"]["name"] = str(uuid.uuid4())

    response = client_v1.put(
        "/v1/cluster/{0}/".format(api_model["id"]),
        data=api_model
    )
    assert response.status_code == 401

    client_v1.login(normal_user.login, "qwerty")
    response = client_v1.put(
        "/v1/cluster/{0}/".format(api_model["id"]),
        data=api_model
    )
    assert response.status_code == 403

    response = sudo_client_v1.put(
        "/v1/cluster/{0}/".format(api_model["id"]),
        data=api_model
    )
    assert response.status_code == 200
    assert response.json["data"]["name"] == api_model["data"]["name"]
    assert response.json["data"]["execution_id"] == clstr.execution_id
    assert response.json["data"]["configuration"]["rgws"]


def test_delete_cluster_empty(sudo_client_v1, normal_user, client_v1):
    initiator_id = str(uuid.uuid4())
    name = str(uuid.uuid4())
    execution_id = str(uuid.uuid4())
    clstr = cluster.ClusterModel.create(name, {}, execution_id,
                                        initiator_id)

    response = client_v1.delete("/v1/cluster/{0}/".format(clstr.model_id))
    assert response.status_code == 401

    client_v1.login(normal_user.login, "qwerty")
    response = client_v1.delete("/v1/cluster/{0}/".format(clstr.model_id))
    assert response.status_code == 403

    response = sudo_client_v1.delete("/v1/cluster/{0}/".format(clstr.model_id))
    assert response.status_code == 200


def test_delete_cluster_with_config(sudo_client_v1, config):
    initiator_id = str(uuid.uuid4())
    name = str(uuid.uuid4())
    execution_id = str(uuid.uuid4())
    clstr = cluster.ClusterModel.create(name, config, execution_id,
                                        initiator_id)

    response = sudo_client_v1.delete("/v1/cluster/{0}/".format(clstr.model_id))
    assert response.status_code == 400