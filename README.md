# Drone Simulation

This repository contains the setup and launch instructions for running a **PX4-based drone simulation in Gazebo Sim (Harmonic)** with **ROS 2 Humble**, **MAVROS**, **QGroundControl**, and an **ArUco/AprilTag environment**.

## 1. Prerequisites

The following software is required:

* Ubuntu 22.04 (Jammy)
* ROS 2 Humble
* Gazebo Sim 8.x (Harmonic)
* PX4 Autopilot
* ROS 2 MAVROS
* QGroundControl
* Terminator (recommended)

Make sure ROS 2 Humble is installed and sourced before continuing.

```bash
source /opt/ros/humble/setup.bash
```

---

## 2. Update Ubuntu Packages

Update and upgrade the system packages:

```bash
sudo apt update
sudo apt upgrade -y
```

---

## 3. Install Gazebo and MAVROS

Install the ROS-Gazebo integration packages:

```bash
sudo apt install ros-humble-ros-gz
```

Install MAVROS and MAVROS extras:

```bash
sudo apt install ros-humble-mavros ros-humble-mavros-extras
```

Install GeographicLib tools and the required geoid dataset:

```bash
sudo apt install geographiclib-tools
sudo geographiclib-get-geoids egm96-5
```

The expected output is:

```text
Installed geoid dataset egm96-5 in /usr/share/GeographicLib/geoids
```

---

## 4. Install PX4 Autopilot

Navigate to the PX4 source directory:

```bash
cd ~/drone_ws/src
```

Clone the PX4 Autopilot repository:

```bash
git clone https://github.com/PX4/PX4-Autopilot.git
```

Enter the PX4 directory:

```bash
cd PX4-Autopilot
```

Initialize and update the PX4 submodules:

```bash
git submodule update --init --recursive
```

Run the PX4 Ubuntu setup script:

```bash
./Tools/setup/ubuntu.sh
```

Restart the terminal or reboot Ubuntu after the installation if requested.

Then update the system:

```bash
sudo apt upgrade -y
```

Build PX4:

```bash
make px4_sitl_default
```

---

## 5. Install ROS 2 Gazebo Bridge

Install the ROS 2 Gazebo bridge and image bridge:

```bash
sudo apt update
sudo apt upgrade -y
sudo apt install -y \
    ros-humble-ros-gz-bridge \
    ros-humble-ros-gz-image
```

These packages allow communication between Gazebo Sim and ROS 2.

---

## 6. Install QGroundControl

### 6.1 Enable Serial Port Access

Add your user to the `dialout` group so QGroundControl can communicate with USB devices without requiring root privileges:

```bash
sudo usermod -aG dialout $USER
```

Log out and log back in, or reboot the computer, for the group change to take effect.

### 6.2 Install Required Dependencies

Install the required GStreamer packages:

```bash
sudo apt install gstreamer1.0-plugins-bad \
                 gstreamer1.0-libav \
                 gstreamer1.0-gl -y
```

Install FUSE:

```bash
sudo apt install libfuse2 -y
```

Install additional Qt/XCB dependencies:

```bash
sudo apt install libxcb-xinerama0 \
                 libxkbcommon-x11-0 \
                 libxcb-cursor-dev -y
```

### 6.3 Download QGroundControl

Download **QGroundControl.AppImage** from the QGroundControl releases page:

https://github.com/mavlink/qgroundcontrol/releases/tag/v4.4.5

Place the downloaded AppImage in:

```text
~/drone_ws/src/PX4-Autopilot/
```

Make the AppImage executable:

```bash
cd ~/drone_ws/src/PX4-Autopilot
chmod +x QGroundControl.AppImage
```

Run QGroundControl:

```bash
./QGroundControl.AppImage
```

---

## 7. Copy AprilTag, ArUco, and X500 Depth Models

The repository contains the required simulation files.

### 7.1 Copy `aruco.sdf`

Download `aruco.sdf` from this repository and copy it to:

```text
~/drone_ws/src/PX4-Autopilot/Tools/simulation/gz/worlds/
```

The resulting path should be:

```text
~/drone_ws/src/PX4-Autopilot/Tools/simulation/gz/worlds/aruco.sdf
```

### 7.2 Copy AprilTag Models

Download the following models from this repository:

```text
Apriltag36_11_00000
Apriltag36_11_00001
```

Copy them to:

```text
~/drone_ws/src/PX4-Autopilot/Tools/simulation/gz/models/
```

### 7.3 Copy the X500 Depth Model

Download the:

```text
x500_depth
```

model from this repository and copy it to:

```text
~/drone_ws/src/PX4-Autopilot/Tools/simulation/gz/models/
```

The final models directory should contain the required AprilTag and X500 depth model files.

---

## 8. Install and Build the AprilTag ROS 2 Packages

Download the following packages from this repository:

```text
apriltag_navigation
apriltag_ros
```

Copy them into:

```text
~/drone_ws/src/
```

Install the AprilTag message package:

```bash
sudo apt install ros-humble-apriltag-msgs
```

Navigate to the ROS 2 workspace:

```bash
cd ~/drone_ws
```

Build the workspace:

```bash
colcon build --symlink-install
```

A successful build should produce output similar to:

```text
Summary: 3 packages finished
1 package had stderr output: px4
```

After building, source the workspace:

```bash
source ~/drone_ws/install/setup.bash
```

---

## 9. Install Terminator

Terminator is recommended because the simulation requires multiple terminals.

Install it with:

```bash
sudo apt install terminator
```

Useful Terminator shortcuts:

| Action             | Shortcut           |
| ------------------ | ------------------ |
| Split vertically   | `Ctrl + Shift + E` |
| Split horizontally | `Ctrl + Shift + O` |

---

## 10. Launch the Drone Simulation

The complete simulation requires several terminals.

The recommended startup order is:

1. PX4 + Gazebo
2. QGroundControl
3. MAVROS
4. AprilTag navigation
5. Image viewer

Open each of the following in a separate terminal (or a separate Terminator pane).

### a) Run PX4 + Gazebo

```bash
export __EGL_VENDOR_LIBRARY_FILENAMES=/usr/share/glvnd/egl_vendor.d/10_nvidia.json
export __GLX_VENDOR_LIBRARY_NAME=nvidia
cd ~/drone_ws/src/PX4-Autopilot
PX4_GZ_WORLD=aruco make px4_sitl gz_x500_depth
```

The two `export` lines force Gazebo to render on the NVIDIA GPU instead of the Intel integrated graphics. They must be set in the same shell that launches PX4.

Wait for the `x500_depth_0` model to spawn in the `aruco` world before starting the other terminals.

### b) Run QGroundControl

```bash
cd ~/drone_ws/src/PX4-Autopilot
./QGroundControl.AppImage
```

### c) Run MAVROS

```bash
ros2 run mavros mavros_node --ros-args \
  -p fcu_url:="udp://:14540@localhost:14557" \
  -p tgt_system:=1 \
  -p tgt_component:=1 \
  -r __ns:=/mavros
```

### d) Run AprilTag Navigation

```bash
cd ~/drone_ws
source install/setup.bash
ros2 launch apriltag_navigation apriltag_navigation.launch.py
```

### e) Run the Image Viewer

```bash
ros2 run rqt_image_view rqt_image_view
```

Select the annotated detection topic from the dropdown to confirm tags are being detected.
