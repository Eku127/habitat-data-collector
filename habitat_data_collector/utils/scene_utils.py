"""Scene utility functions."""

from typing import List, Dict
import numpy as np
import habitat_sim
import magnum as mn


def get_bounding_boxes_for_category(sim: habitat_sim.Simulator, category_name: str) -> List[Dict]:
    """Get bounding boxes for all objects of a given category.
    
    Args:
        sim: Habitat simulator instance
        category_name: Category name to search for
        
    Returns:
        List of bounding box dictionaries with 'Object_ID', 'Category', 'center', 'size'
    """
    scene = sim.semantic_scene
    bounding_boxes = []
    
    for obj in scene.objects:
        if obj is None:
            continue
        
        obj_category_name = obj.category.name() if obj.category else None
        if obj_category_name == category_name:
            aabb_center = obj.aabb.center
            aabb_size = obj.aabb.sizes
            
            bounding_box_info = {
                "Object_ID": obj.id,
                "Category": category_name,
                "center": [aabb_center[0], aabb_center[1], aabb_center[2]],
                "size": [aabb_size[0], aabb_size[1], aabb_size[2]]
            }
            bounding_boxes.append(bounding_box_info)
    
    return bounding_boxes


def draw_bounding_boxes(sim: habitat_sim.Simulator, obj_attr_mgr, bbox_list: List[Dict]):
    """Draw bounding boxes in the scene.
    
    Args:
        sim: Habitat simulator instance
        obj_attr_mgr: Object attribute manager
        bbox_list: List of bounding boxes to draw
    """
    for i, bbox in enumerate(bbox_list):
        center = ensure_vector3(bbox["center"])
        sizes = np.array(bbox["size"]) * 0.5
        
        # Create wireframe cube
        cube_handle = obj_attr_mgr.get_template_handles("cubeWireframe")[0]
        cube_template_cpy = obj_attr_mgr.get_template_by_handle(cube_handle)
        cube_template_cpy.scale = sizes
        cube_template_cpy.is_collidable = False
        
        bbox_handle = f"bbox_{i}"
        obj_attr_mgr.register_template(cube_template_cpy, bbox_handle)
        
        # Add to scene
        bbox_obj = sim.get_rigid_object_manager().add_object_by_template_handle(bbox_handle)
        bbox_obj.translation = center
        bbox_obj.motion_type = habitat_sim.physics.MotionType.STATIC
        
        print(f"Drew bounding box {i} at {center}")


def ensure_vector3(vec) -> mn.Vector3:
    """Ensure input is a magnum Vector3.
    
    Args:
        vec: Input vector (list, numpy array, or Vector3)
        
    Returns:
        Magnum Vector3
    """
    if isinstance(vec, mn.Vector3):
        return vec
    return mn.Vector3(vec)

