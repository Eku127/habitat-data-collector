"""Main entry point for Habitat Data Collector."""

import hydra
from pathlib import Path
from omegaconf import DictConfig

from .app import Application


@hydra.main(
    version_base=None,
    config_path=str(Path(__file__).parent.parent / "config"),
    config_name="habitat_data_collector.yaml"
)
def main(cfg: DictConfig) -> None:
    """Main function to run the data collector.
    
    Args:
        cfg: Hydra configuration
    """
    app = Application(cfg)
    app.run()


if __name__ == "__main__":
    main()

