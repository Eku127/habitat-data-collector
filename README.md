# Habitat Data Collector

**Habitat Data Collector** is a standalone simulation application built on top of [Habitat-Sim](https://github.com/facebookresearch/habitat-sim) and [Habitat-Lab](https://github.com/facebookresearch/habitat-lab). It supports scene loading, object insertion/removal, ROS2 output, and data recording. This tool is designed for collecting and testing datasets for robot perception, navigation, and mapping tasks.

---

## 📝 TODO

- [ ] **Write documentation for configuration and dataset format**
  - [ ] Explain the structure and usage of `config/habitat_data_collector.yaml`
  - [ ] Describe expected dataset directory structure (scene, object assets, etc.)

- [ ] **Write usage guide**
  - [ ] Basic usage and how to launch the simulator
  - [ ] Interactions: object picking, placing, and removing
  - [ ] How to record data and where it's saved
  - [ ] How to save and replay a scene setup

- [ ] **Add illustrations**
  - [ ] Add a demo video or animated GIF showing typical usage
  - [ ] Include example screenshots of the simulator running


---

## 📦 Environment Setup

> 🖥️ This setup is tested on **Ubuntu 22.04** with **Python 3.10** env.

### 1. Clone the repository with submodules

```bash
git clone --recurse-submodules https://github.com/Eku127/habitat-data-collector.git
cd habitat-data-collector
```

### 2. Create the Conda environment

```bash
conda env create -f environment.yml
conda activate habitat_data_collector
```

### 3. Build and install Habitat Sim & Lab

This step will take some time as it compiles Habitat-Sim from source.

```bash
bash scripts/install_habitat.sh
```

---

## 🚀 Run the Collector

Run the main simulation from the root directory:

```bash
python -m habitat_data_collector.main
```

By default, it uses the configuration file at: `config/habitat_data_collector.yaml`



### 🚁 ROS2 Integration (Optional)

If you want to receive ROS2 topic outputs or record ROS2 bags:

1. Make sure you have **ROS2 Humble** installed. You can follow the official installation guide:  
   👉 [Install ROS2 Humble (Ubuntu 22.04)](https://docs.ros.org/en/humble/Installation/Ubuntu-Install-Debians.html)

2. Source the ROS2 environment **before** running the collector:

```bash
source /opt/ros/humble/setup.bash  # or source /opt/ros/humble/setup.zsh
```

Once sourced, the simulator will publish data to ROS2 topics and allow you to record them by open ros recording config in `config/habitat_data_collector.yaml`


---

## 📁 Project Structure

```
habitat-data-collector/
├── habitat_data_collector/   # Main application code
│   ├── main.py
│   └── utils/
├── config/                   # YAML configuration files
├── 3rdparty/                 # Git submodules: habitat-sim & habitat-lab
├── environment.yml           # Conda environment spec
└── README.md
```

---

## ⚠️ Notes

- ROS2 Humble must be pre-installed and sourced before running.
- Habitat-Sim and Habitat-Lab are included as Git submodules.
- habitat-sim is compiled and installed using pip with editable mode.
- habitat-lab is installed using `pip install -e .`.
- Configuration is managed using [OmegaConf](https://omegaconf.readthedocs.io/) and [Hydra](https://hydra.cc/).

---

## 🛠️ Developer Info

To customize the scene, output, or ROS settings, modify `config/habitat_data_collector.yaml`. To extend functionality, explore the utilities in `habitat_data_collector/utils`.

---

## 📜 License

MIT License

