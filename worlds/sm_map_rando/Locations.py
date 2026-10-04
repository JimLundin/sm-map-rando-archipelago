from __future__ import annotations

import json
import pkgutil
from typing import Dict, List, TypedDict

LOCATIONS_START_ID = 86000


class LocationInfo(TypedDict):
    index: int          # index in Map Rando's item location list (and its `item_placement`)
    name: str
    room_id: int
    node_id: int
    room_name: str
    node_name: str
    plm_ptr: int        # ROM (PC) address of the item PLM
    bit_index: int      # vanilla item collected bit index (PLM room argument)


LOCATIONS: List[LocationInfo] = json.loads(pkgutil.get_data(__name__, "data/locations.json").decode("utf-8"))

location_name_to_id: Dict[str, int] = {loc["name"]: LOCATIONS_START_ID + loc["bit_index"] for loc in LOCATIONS}
location_by_room_node: Dict[tuple, LocationInfo] = {(loc["room_id"], loc["node_id"]): loc for loc in LOCATIONS}
