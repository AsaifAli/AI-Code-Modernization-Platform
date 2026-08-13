"""
Folder structure + goals JSON (folder_structure_with_goals.json) for migrations.

Canonical location matches agent workflow: agent_service/Temp/<user_id>/<migration>/Dest/<migration>/.
Same contract as migration_service FolderStructureService for API parity.
"""
import json
import logging
from pathlib import Path
from typing import Dict, Optional

from fastapi import HTTPException

from app.infrastructure.utils.Constants.agent_event import AgentEventMessages
from app.infrastructure.utils.Constants.app_constants import PathConstants, ServiceConstants
from app.infrastructure.utils.Constants.migration_workflow import MigrationWorkflowStrings

logger = logging.getLogger(__name__)


class FolderStructureGoalsService:
    def _goals_file_path(self, user_id: str, migration_name: str) -> Path:
        return (
            Path(PathConstants.TEMP_DIR).resolve()
            / str(user_id)
            / migration_name
            / MigrationWorkflowStrings.DEST_FOLDER
            / migration_name
            / ServiceConstants.FOLDER_STRUCTURE_WITH_GOALS_FILE
        )

    def _load_json(self, file_path: Path, *, allow_create: bool = True) -> Dict:
        if not file_path.exists():
            if not allow_create:
                return {"name": "root", "children": []}
            file_path.parent.mkdir(parents=True, exist_ok=True)
            empty_data = {"name": "root", "children": []}
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(empty_data, f, indent=2)
            return empty_data
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _save_json(self, file_path: Path, data: Dict) -> None:
        file_path.parent.mkdir(parents=True, exist_ok=True)
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def _find_and_update_goal(
        self,
        node: dict,
        goal_id: str,
        parent_goal_id: Optional[str] = None,
        new_description: Optional[str] = None,
        delete: bool = False,
    ) -> bool:
        gid = str(goal_id) if goal_id is not None else None
        pgid = str(parent_goal_id) if parent_goal_id is not None else None
        if str(node.get("goal_id")) == gid:
            if pgid is not None and str(node.get("parent_goal_id")) != pgid:
                return False
            if delete:
                node.pop("goal_description", None)
            if new_description is not None:
                node["goal_description"] = new_description
            return True
        for child in node.get("children", []):
            if self._find_and_update_goal(
                child,
                goal_id=gid,
                parent_goal_id=pgid,
                new_description=new_description,
                delete=delete,
            ):
                return True
        return False

    def get_folder_structure(self, user_id: str, migration_name: str) -> Dict:
        file_path = self._goals_file_path(user_id, migration_name)
        logger.info("Folder goals path (agent_service): %s", file_path)
        return self._load_json(file_path, allow_create=False)

    def update_goal(
        self,
        user_id: str,
        migration_name: str,
        goal_id: str,
        parent_goal_id: Optional[str] = None,
        new_description: Optional[str] = None,
    ) -> Dict:
        file_path = self._goals_file_path(user_id, migration_name)
        data = self._load_json(file_path)
        updated = self._find_and_update_goal(
            data,
            goal_id=str(goal_id),
            parent_goal_id=parent_goal_id,
            new_description=new_description,
        )
        if not updated:
            raise HTTPException(
                status_code=404,
                detail=AgentEventMessages.GOAL_NOT_FOUND,
            )
        self._save_json(file_path, data)
        return data

    def delete_goal(
        self,
        user_id: str,
        migration_name: str,
        goal_id: Optional[str] = None,
        parent_goal_id: Optional[str] = None,
    ) -> Dict:
        file_path = self._goals_file_path(user_id, migration_name)
        data = self._load_json(file_path)
        if str(data.get("goal_id")) == str(goal_id):
            raise HTTPException(status_code=400, detail="Root folder cannot be deleted")
        deleted = self._delete_node(data, goal_id)
        if not deleted:
            raise HTTPException(status_code=404, detail=AgentEventMessages.GOAL_NOT_FOUND)
        self._save_json(file_path, data)
        return data

    def _delete_node(self, node: dict, goal_id) -> bool:
        children = node.get("children", [])
        for index, child in enumerate(children):
            if str(child.get("goal_id")) == str(goal_id):
                del children[index]
                return True
            if self._delete_node(child, goal_id):
                return True
        return False

    def add_item(
        self,
        user_id: str,
        migration_name: str,
        parent_goal_id: int,
        name: str,
        kind: str,
        goal_description: str,
        original_file_path: Optional[str] = None,
    ) -> Dict:
        file_path = self._goals_file_path(user_id, migration_name)
        data = self._load_json(file_path)
        parent_node = self._find_node_by_goal_id(data, parent_goal_id)
        if not parent_node:
            raise HTTPException(status_code=404, detail="Parent folder not found")
        if parent_node.get("kind") != "folder":
            raise HTTPException(
                status_code=400,
                detail="Cannot add items inside a file. Only folders may contain children.",
            )

        def get_max_goal(node):
            m = int(node.get("goal_id") or 0)
            for c in node.get("children", []):
                m = max(m, get_max_goal(c))
            return m

        new_goal_id = get_max_goal(data) + 1
        new_item = {
            "name": name,
            "kind": kind,
            "goal_id": new_goal_id,
            "parent_goal_id": parent_goal_id,
            "goal_description": goal_description,
            "isCompleted": False,
        }
        if kind == "folder":
            new_item["children"] = []
        else:
            new_item["content"] = None
            new_item["original_file_path"] = original_file_path
        parent_node.setdefault("children", []).append(new_item)
        self._save_json(file_path, data)
        return data

    def _find_node_by_goal_id(self, node: dict, goal_id) -> Optional[dict]:
        if str(node.get("goal_id")) == str(goal_id):
            return node
        for child in node.get("children", []):
            result = self._find_node_by_goal_id(child, goal_id)
            if result:
                return result
        return None
