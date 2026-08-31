"""Main application class."""

import os
import time
import json
from pathlib import Path
from collections import defaultdict
from omegaconf import DictConfig
import cv2
import habitat_sim

from .core import StateManager, EventDispatcher, EventType
from .core.simulator_service import SimulatorService
from .handlers import InputHandler, RecordingHandler, NavigationHandler, ObjectHandler
from .services import DataSaver, Visualizer
from .utils.config_factory import ConfigFactory
from .config.settings import DEFAULT_FPS
from .authoring import (
    AnchorInfo,
    layout_output_path,
    validate_authoring_layout,
)


class Application:
    """Main application class orchestrating all components."""

    def __init__(self, cfg: DictConfig):
        """Initialize application.
        
        Args:
            cfg: Hydra configuration
        """
        self.cfg = cfg
        
        # Setup output directory. Authoring uses a stable scene directory so
        # support metadata and named layout slots stay together.
        authoring_cfg = cfg.get("authoring")
        authoring_enabled = bool(
            authoring_cfg and authoring_cfg.get("enabled", False)
        )
        if authoring_enabled:
            layout_type = str(authoring_cfg.layout_type)
            raw_index = authoring_cfg.get("layout_index")
            layout_index = None if raw_index is None else int(raw_index)
            layout_output_path(
                Path(authoring_cfg.output_root),
                str(cfg.scene_name),
                layout_type,
                layout_index,
            )
            if layout_type == "static" and cfg.load_from_config:
                raise ValueError("Static authoring must start from the raw scene.")
            if layout_type != "static" and not cfg.load_from_config:
                raise ValueError(
                    "Dynamic authoring must load the authored static config."
                )
            scene_dir = Path(authoring_cfg.output_root) / str(cfg.scene_name)
            print(
                f"Authoring {layout_type} layout for scene {cfg.scene_name}..."
            )
        else:
            os.makedirs(cfg.output_path, exist_ok=True)
            dataset_dir = Path(cfg.output_path) / cfg.dataset_name
            scene_id = 1
            while True:
                scene_dir = dataset_dir / f"{cfg.scene_name}_{scene_id}"
                if not scene_dir.exists():
                    break
                scene_id += 1
            print(
                f"Collecting data for scene {cfg.scene_name} "
                f"in dataset {cfg.dataset_name}..."
            )
        print(f"Data will be saved at {scene_dir}")
        scene_dir.mkdir(parents=True, exist_ok=True)
        
        self.scene_dir = scene_dir
        
        # Initialize core components
        self.state_manager = StateManager()
        self.state_manager.configure_authoring(authoring_cfg)
        self.event_dispatcher = EventDispatcher()
        
        # Create simulator
        os.environ["MAGNUM_LOG"] = "quiet"
        os.environ["HABITAT_SIM_LOG"] = "quiet"
        
        habitat_config = ConfigFactory.create_simulator_config(cfg)
        sim = habitat_sim.Simulator(habitat_config)
        self.simulator = SimulatorService(sim, cfg)
        
        print("Scene loaded")
        print(f"House has {len(self.simulator.scene.levels)} levels, "
              f"{len(self.simulator.scene.regions)} regions, "
              f"{len(self.simulator.scene.objects)} objects")
        
        # Save scene information
        self._save_scene_info()
        
        # Initialize services
        self.data_saver = DataSaver(cfg, scene_dir)
        self.visualizer = Visualizer(self.simulator)
        
        # Save camera intrinsics
        fx, fy, cx, cy, width, height = self.simulator.get_camera_intrinsics("color_sensor")
        self.data_saver.save_camera_intrinsics(fx, fy, cx, cy, width, height)
        
        # Initialize handlers
        self.input_handler = InputHandler(
            self.state_manager,
            self.simulator,
            self.event_dispatcher
        )
        
        self.recording_handler = RecordingHandler(
            self.state_manager,
            self.simulator,
            self.event_dispatcher
        )
        
        self.navigation_handler = NavigationHandler(
            self.state_manager,
            self.simulator,
            self.event_dispatcher
        )
        
        self.object_handler = ObjectHandler(
            self.state_manager,
            self.simulator,
            self.event_dispatcher,
            recording_handler=self.recording_handler
        )
        
        # Subscribe to system events
        self.event_dispatcher.subscribe(EventType.SYSTEM_STOP, self._handle_stop)
        self.event_dispatcher.subscribe(EventType.SYSTEM_SAVE_CONFIG, self._handle_save_config)
        self.event_dispatcher.subscribe(EventType.UI_TOGGLE_MAP, self._handle_toggle_map)
        self.event_dispatcher.subscribe(EventType.UI_TOGGLE_HELP, self._handle_toggle_help)
        
        # Subscribe to action events for simulator
        self.event_dispatcher.subscribe(EventType.ACTION_MOVE, self._handle_sim_action)
        self.event_dispatcher.subscribe(EventType.ACTION_TURN, self._handle_sim_action)
        self.event_dispatcher.subscribe(EventType.ACTION_LOOK, self._handle_sim_action)
        
        # Setup objects
        self._setup_objects()
        
        # Setup placeable bounding boxes
        self._setup_placeable_bboxes()
        
        # Set random initial position
        self.simulator.set_random_agent_position()
        
        # Frame rate control
        self.target_fps = cfg.get("frame_rate", DEFAULT_FPS)
        self.frame_interval = 1.0 / self.target_fps
        
        # Initialize ROS if enabled
        self.ros_adapter = None
        if cfg.get("use_ros", False):
            try:
                from .adapters.ros_adapter import ROSAdapter
                self.ros_adapter = ROSAdapter(cfg)
                print("ROS adapter initialized")
            except ImportError:
                print("ROS not available, continuing without ROS support")
    
    def run(self):
        """Main application loop."""
        last_time = time.time()
        
        while self.state_manager.app.running:
            # Frame rate control
            elapsed_time = time.time() - last_time
            sleep_time = self.frame_interval - elapsed_time
            if sleep_time > 0:
                time.sleep(sleep_time)
            
            last_time = time.time()
            
            # Physics step
            self.simulator.step_physics(self.frame_interval)
            
            # Update handlers
            self.object_handler.update()
            self.navigation_handler.update()
            
            # Handle input
            input_processed = self.input_handler.poll()
            
            # If recording in timestamp mode and no action, record idle frame
            if (self.state_manager.app.recording and 
                self.cfg.get("save_mode", "timestamp") == "timestamp" and
                not input_processed):
                self.recording_handler.handle_no_action(time.time())
            
            # Get observations
            observations = self.simulator.get_observations()
            
            # Publish to ROS if enabled
            if self.ros_adapter:
                self.ros_adapter.publish_data(self.simulator, observations)
                
                # Check for navigation commands from ROS
                global_path = self.ros_adapter.get_global_path()
                if global_path is not None:
                    if global_path != self.state_manager.navigation.previous_global_path:
                        print(f"Received global path: {len(global_path)} points")
                        self.state_manager.navigation.previous_global_path = global_path
                        # Trigger navigation
                        from .core.event_dispatcher import Event
                        self.event_dispatcher.dispatch(Event(
                            event_type=EventType.NAVIGATION_START,
                            timestamp=time.time()
                        ))
            
            # Prepare topdown map if needed
            topdown_map_img = None
            if self.state_manager.app.show_map:
                object_positions = [
                    obj.translation 
                    for obj in self.state_manager.objects.all_rigid_objects
                ]
                topdown_map_img = self.visualizer.prepare_topdown_map(
                    self.state_manager,
                    object_positions
                )
            
            # Render
            self.visualizer.render(
                observations,
                self.state_manager,
                topdown_map_img
            )
        
        # Cleanup
        self._cleanup()
    
    def _handle_sim_action(self, event):
        """Handle simulator action."""
        from .core.event_dispatcher import ActionEvent
        if isinstance(event, ActionEvent) and event.action:
            self.simulator.step(event.action)
            print(f"Action: {event.action} at {event.timestamp}")
    
    def _handle_stop(self, event):
        """Handle stop event."""
        cv2.destroyAllWindows()
        self.state_manager.stop()
    
    def _handle_save_config(self, event):
        """Handle save config event."""
        authoring = self.state_manager.authoring
        if authoring.enabled:
            result = validate_authoring_layout(
                targets=authoring.targets,
                object_semantic_ids=[
                    int(obj.semantic_id)
                    for obj in self.state_manager.objects.all_rigid_objects
                ],
                anchors=authoring.anchors,
                layout_type=authoring.layout_type,
                baseline_anchors=authoring.baseline_anchors,
                baseline_semantic_ids=authoring.baseline_semantic_ids,
                relocated_semantic_ids=authoring.relocated_semantic_ids,
                minimum_placed=authoring.minimum_placed,
            )
            authoring.last_status = result.message
            authoring.last_status_ok = result.valid
            if not result.valid:
                print(f"Authoring save blocked: {result.message}")
                return
        try:
            saved_path = self.data_saver.save_scene_config(
                self.state_manager.objects.id_handle_dict,
                self.state_manager.objects.all_rigid_objects,
                authoring_state=authoring if authoring.enabled else None,
            )
        except (FileExistsError, OSError, ValueError) as exc:
            if authoring.enabled:
                authoring.last_status = str(exc)
                authoring.last_status_ok = False
            print(f"Configuration was not saved: {exc}")
            return
        if authoring.enabled:
            authoring.last_status = f"Saved {saved_path.name}"
            authoring.last_status_ok = True
    
    def _handle_toggle_map(self, event):
        """Handle map toggle."""
        self.state_manager.toggle_map()
    
    def _handle_toggle_help(self, event):
        """Handle help toggle."""
        self.state_manager.toggle_help()
    
    def _setup_objects(self):
        """Setup object templates."""
        id_handle_dict = self.simulator.register_object_templates()
        self.state_manager.objects.id_handle_dict = id_handle_dict
        self.cfg.id_handle_dict = id_handle_dict
        
        # Load objects from config if specified
        if self.cfg.load_from_config:
            if self.state_manager.authoring.enabled:
                scene_objects, metadata = self.simulator.load_objects_from_config(
                    id_handle_dict,
                    include_metadata=True,
                )
                anchors = {
                    int(semantic_id): AnchorInfo.from_mapping(anchor)
                    for semantic_id, anchor in metadata.items()
                }
                self.state_manager.authoring.anchors = dict(anchors)
                self.state_manager.authoring.baseline_anchors = dict(anchors)
                self.state_manager.authoring.baseline_semantic_ids = {
                    int(obj.semantic_id) for obj in scene_objects
                }
                baseline_result = validate_authoring_layout(
                    targets=self.state_manager.authoring.targets,
                    object_semantic_ids=[
                        int(obj.semantic_id) for obj in scene_objects
                    ],
                    anchors=anchors,
                    layout_type="static",
                    minimum_placed=self.state_manager.authoring.minimum_placed,
                )
                if not baseline_result.valid:
                    raise ValueError(
                        "Invalid authored static baseline: "
                        + baseline_result.message
                    )
            else:
                scene_objects = self.simulator.load_objects_from_config(
                    id_handle_dict
                )
            self.state_manager.objects.all_rigid_objects.extend(scene_objects)
    
    def _setup_placeable_bboxes(self):
        """Setup placeable bounding boxes."""
        from .utils.scene_utils import get_bounding_boxes_for_category
        
        all_bboxes = []
        for category in self.cfg.placable_categories:
            category_bboxes = get_bounding_boxes_for_category(
                self.simulator.sim,
                category
            )
            all_bboxes.extend(category_bboxes)
        
        self.state_manager.objects.all_bboxes_for_place = all_bboxes
        print(f"Found {len(all_bboxes)} placeable locations")
        
        # Optionally visualize bboxes
        if self.cfg.get("show_placable_categories", False):
            from .utils.scene_utils import draw_bounding_boxes
            obj_attr_mgr = self.simulator.get_object_template_manager()
            draw_bounding_boxes(self.simulator.sim, obj_attr_mgr, all_bboxes)
    
    def _save_scene_info(self):
        """Save scene object information."""
        scene = self.simulator.scene
        
        class_bbox = defaultdict(list)
        class_count = defaultdict(int)
        
        for region in scene.regions:
            for obj in region.objects:
                category_name = obj.category.name() if obj.category else "unknown"
                
                bbox = {
                    'center': obj.aabb.center.tolist(),
                    'sizes': obj.aabb.sizes.tolist()
                }
                
                class_bbox[category_name].append(bbox)
                class_count[category_name] += 1
        
        sorted_class_count = sorted(class_count.items(), key=lambda x: x[1], reverse=True)
        
        # Save files
        class_bbox_file = self.scene_dir / "class_bbox.json"
        class_num_file = self.scene_dir / "class_num.json"
        
        with open(class_bbox_file, 'w') as f:
            json.dump(dict(class_bbox), f, indent=4)
        
        with open(class_num_file, 'w') as f:
            json.dump(sorted_class_count, f, indent=4)
        
        print(f"Saved scene info to {self.scene_dir}")
    
    def _cleanup(self):
        """Cleanup and save data."""
        print("Cleaning up...")
        
        # Print recorded actions
        for action in self.state_manager.recording.all_actions:
            if action.action is not None:
                print(action)
        
        # Replay and save if we have recordings
        if len(self.state_manager.recording.all_actions) > 0:
            print("Replaying and saving data...")
            
            # Create new simulator for replay
            habitat_config = ConfigFactory.create_simulator_config(self.cfg)
            replay_sim = habitat_sim.Simulator(habitat_config)
            replay_sim_service = SimulatorService(replay_sim, self.cfg)
            
            # Register templates
            replay_sim_service.register_object_templates()
            
            # Replay and save
            self.data_saver.replay_and_save(
                replay_sim_service,
                self.state_manager.recording.all_actions,
                self.state_manager.recording.init_state,
                self.state_manager.recording.init_time
            )
            
            replay_sim.close()
        
        # Close main simulator
        self.simulator.sim.close()
        
        # Shutdown ROS if enabled
        if self.ros_adapter:
            self.ros_adapter.shutdown()
        
        print("Application closed")
