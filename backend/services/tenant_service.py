"""
多租户服务
组织管理、数据隔离、权限范围
"""
from __future__ import annotations

import math
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from database import Organization, Building


def list_organizations(
    db: Session,
    keyword: str = "",
    org_type: str = "",
    page: int = 1,
    page_size: int = 20,
) -> Dict[str, Any]:
    """组织列表（分页）"""
    query = db.query(Organization)
    if keyword:
        like = f"%{keyword}%"
        query = query.filter(
            (Organization.org_code.like(like)) |
            (Organization.org_name.like(like))
        )
    if org_type:
        query = query.filter(Organization.org_type == org_type)

    total = query.count()
    orgs = (
        query.order_by(Organization.id.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": math.ceil(total / page_size) if total > 0 else 0,
        "items": [_org_to_dict(o) for o in orgs],
    }


def get_organization(db: Session, org_id: int) -> Optional[Dict[str, Any]]:
    """获取组织详情"""
    org = db.query(Organization).filter(Organization.id == org_id).first()
    return _org_to_dict(org) if org else None


def create_organization(
    db: Session,
    org_code: str,
    org_name: str,
    parent_id: int = None,
    org_type: str = "company",
    address: str = "",
    contact_name: str = "",
    contact_phone: str = "",
) -> Dict[str, Any]:
    """创建组织"""
    org_code = (org_code or "").strip()
    org_name = (org_name or "").strip()

    if not org_code:
        return {"ok": False, "message": "组织编号不能为空"}
    if not org_name:
        return {"ok": False, "message": "组织名称不能为空"}

    existing = db.query(Organization).filter(Organization.org_code == org_code).first()
    if existing:
        return {"ok": False, "message": f"组织编号 {org_code} 已存在"}

    if parent_id:
        parent = db.query(Organization).filter(Organization.id == parent_id).first()
        if not parent:
            return {"ok": False, "message": "上级组织不存在"}

    org = Organization(
        org_code=org_code,
        org_name=org_name,
        parent_id=parent_id,
        org_type=org_type,
        address=address,
        contact_name=contact_name,
        contact_phone=contact_phone,
    )
    db.add(org)
    db.commit()
    db.refresh(org)
    return {"ok": True, "message": "组织创建成功", "org": _org_to_dict(org)}


def update_organization(
    db: Session,
    org_id: int,
    org_name: str = None,
    parent_id: int = None,
    org_type: str = None,
    address: str = None,
    contact_name: str = None,
    contact_phone: str = None,
    status: str = None,
) -> Dict[str, Any]:
    """更新组织"""
    org = db.query(Organization).filter(Organization.id == org_id).first()
    if not org:
        return {"ok": False, "message": "组织不存在"}

    if org_name is not None:
        org.org_name = org_name.strip()
    if parent_id is not None:
        if parent_id:
            parent = db.query(Organization).filter(Organization.id == parent_id).first()
            if not parent:
                return {"ok": False, "message": "上级组织不存在"}
        org.parent_id = parent_id
    if org_type is not None:
        org.org_type = org_type
    if address is not None:
        org.address = address
    if contact_name is not None:
        org.contact_name = contact_name
    if contact_phone is not None:
        org.contact_phone = contact_phone
    if status is not None:
        org.status = status

    org.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(org)
    return {"ok": True, "message": "组织更新成功", "org": _org_to_dict(org)}


def delete_organization(db: Session, org_id: int) -> Dict[str, Any]:
    """删除组织"""
    org = db.query(Organization).filter(Organization.id == org_id).first()
    if not org:
        return {"ok": False, "message": "组织不存在"}

    child_count = db.query(Organization).filter(Organization.parent_id == org_id).count()
    if child_count > 0:
        return {"ok": False, "message": "该组织下还有子组织，无法删除"}

    building_count = db.query(Building).filter(Building.org_id == org_id).count()
    if building_count > 0:
        return {"ok": False, "message": "该组织下还有建筑，无法删除"}

    db.delete(org)
    db.commit()
    return {"ok": True, "message": "组织删除成功"}


def get_organization_tree(db: Session) -> List[Dict[str, Any]]:
    """获取组织树"""
    orgs = db.query(Organization).order_by(Organization.id.asc()).all()
    org_map = {o.id: _org_to_dict(o) for o in orgs}
    tree = []

    for org in orgs:
        if org.parent_id:
            parent = org_map.get(org.parent_id)
            if parent:
                if "children" not in parent:
                    parent["children"] = []
                parent["children"].append(org_map[org.id])
        else:
            tree.append(org_map[org.id])

    return tree


def get_org_buildings(db: Session, org_id: int) -> List[Dict[str, Any]]:
    """获取组织下的建筑"""
    buildings = db.query(Building).filter(Building.org_id == org_id).all()
    return [_building_to_dict(b) for b in buildings]


def _org_to_dict(org: Organization) -> Dict[str, Any]:
    return {
        "id": org.id,
        "org_code": org.org_code,
        "org_name": org.org_name,
        "parent_id": org.parent_id,
        "org_type": org.org_type,
        "address": org.address,
        "contact_name": org.contact_name,
        "contact_phone": org.contact_phone,
        "status": org.status,
        "created_at": org.created_at.isoformat() if org.created_at else "",
        "updated_at": org.updated_at.isoformat() if org.updated_at else "",
    }


def _building_to_dict(building: Building) -> Dict[str, Any]:
    return {
        "id": building.id,
        "building_code": building.building_code,
        "building_name": building.building_name,
        "building_type": building.building_type,
        "address": building.address,
        "floors": building.floors,
        "area": building.area,
        "risk_score": building.risk_score,
        "risk_level": building.risk_level,
        "org_id": building.org_id,
        "status": building.status,
    }

