#!/usr/bin/env python3
"""
This migration applies default 'wheel' role.
"""


from cephlcm_common.models import db
from cephlcm_common.models import generic
from cephlcm_common.models import role


generic.configure_models(db.MongoDB())
role.RoleModel.make_role(
    "wheel",
    [
        {"name": k, "permissions": sorted(v)}
        for k, v in role.PermissionSet.KNOWN_PERMISSIONS.items()
    ]
)
