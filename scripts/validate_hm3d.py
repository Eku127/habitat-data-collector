#!/usr/bin/env python3

"""Open one HM3D scene and verify navigation and semantic rendering."""

import argparse
import os

os.environ.setdefault("MAGNUM_LOG", "quiet")
os.environ.setdefault("HABITAT_SIM_LOG", "quiet")
import habitat_sim


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("scene_mesh")
    parser.add_argument("dataset_config")
    parser.add_argument("scene_name")
    args = parser.parse_args()

    sim_cfg = habitat_sim.SimulatorConfiguration()
    sim_cfg.scene_id = args.scene_mesh
    sim_cfg.scene_dataset_config_file = args.dataset_config

    sensor = habitat_sim.CameraSensorSpec()
    sensor.uuid = "semantic"
    sensor.sensor_type = habitat_sim.SensorType.SEMANTIC
    sensor.resolution = [64, 64]

    agent_cfg = habitat_sim.agent.AgentConfiguration()
    agent_cfg.sensor_specifications = [sensor]

    with habitat_sim.Simulator(
        habitat_sim.Configuration(sim_cfg, [agent_cfg])
    ) as simulator:
        if not simulator.pathfinder.is_loaded:
            raise RuntimeError("navmesh did not load")
        observations = simulator.get_sensor_observations()
        if observations["semantic"].shape != (64, 64):
            raise RuntimeError("semantic sensor returned an unexpected shape")

    print(
        f"Validated scene {args.scene_name}: "
        "navmesh and semantic sensor loaded"
    )


if __name__ == "__main__":
    main()
