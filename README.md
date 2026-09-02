# Drone_Simulation

This repository contains the setup and launch instructions for running a PX4-based drone simulation in Gazebo Sim (Harmonic) with ROS 2 Humble, MAVROS, and an ArUco/AprilTag world.

---

## 1. Prerequisites

- Ubuntu 22.04 (Jammy)
- ROS 2 Humble installed and sourced
- Gazebo Sim 8.x (Harmonic)
- mavros
- QGroundControl

---

## 2. Install Required ROS Packages

Update package lists:

```bash
sudo apt update
sudo apt upgrade

```

----
## 3. Install  gazebo and mavros
```bash
sudo apt install ros-humble-ros-gz
sudo apt install ros-humble-mavros ros-humble-mavros-extras
sudo apt install geographiclib-tools
sudo geographiclib-get-geoids egm96-5
```

Output is Installed geoid dataset egm96-5 in /usr/share/GeographicLib/geoids.

```bash
cd ~/drone_ws/src
git clone https://github.com/PX4/PX4-Autopilot.git
cd PX4-Autopilot
git submodule update --init --recursive
./Tools/setup/ubuntu.sh
sudo apt upgrade
make px4_sitl_default
```
----
## 3. Install  ROS2 bridge

```bash
sudo apt update
sudo apt upgrade -y

sudo apt install -y \
ros-humble-ros-gz-bridge \
ros-humble-ros-gz-image

```


----
## 4. Install  QGroundControl

Before installing QGroundControl for the first time. Enable serial-port access  Add your user to the dialout group so you can talk to USB devices without root:



```bash
sudo usermod -aG dialout $USER
```


On the command prompt, enter:

```bash
sudo apt install gstreamer1.0-plugins-bad gstreamer1.0-libav gstreamer1.0-gl -y
sudo apt install libfuse2 -y
sudo apt install libxcb-xinerama0 libxkbcommon-x11-0 libxcb-cursor-dev -y
```
To install QGroundControl:

    Download QGroundControl-x86_64.AppImage: https://d176tv9ibo4jno.cloudfront.net/latest/QGroundControl-x86_64.AppImage

    Make the AppImage executable
```bash
cd Downloads/

chmod +x QGroundControl-x86_64.AppImage
```
    Run QGroundControl Either double-click the AppImage in your file manager or launch it from a terminal:
```bash
./QGroundControl-x86_64.AppImage

```
## 4. Copy AprilTags, aruco.sdf and x500_depth to corresponding directories


Download "aruco.sdf" from this repo and copy it to the following path: "~/drone_ws/src/PX4-Autopilot/Tools/simulation/gz/worlds"




Download "Apriltag36_11_00000", "Apriltag36_11_00001" and "x500_depth" from this repo and copy it to the following path: "~/drone_ws/src/PX4-Autopilot/Tools/simulation/gz/models"



## 5. Copy AprilTag packages and Launch the simulation

Download "apriltag_navigation" and "apriltag_ros" from this repo inside "src" and copy it to the following path: "~/drone_ws/src"


```bash
sudo apt install ros-humble-apriltag-msgs
cd ~/drone_ws
colcon build --symlink-install
```
Output: Summary: 3 packages finished [2min 21s]
  1 package had stderr output: px4

```bash
cd ~/drone_ws/src/PX4-Autopilot
PX4_GZ_WORLD=aruco make px4_sitl gz_x500_depth
```

Run QGround Control

```bash
./QGroundControl-x86_64.AppImage

```

I moved it to "~/drone_ws/src/PX4-Autopilot"
On the terminal of the drone type "commander takeoff" to test that QGroundControl works well. Then type "commander land" to land
To land the drone to its original position if it move to somewhere use this command : "commander mode auto:rtl"





Open a new terminal

```bash
ros2 run mavros mavros_node --ros-args \
  -p fcu_url:="udp://:14540@localhost:14557" \
  -p tgt_system:=1 \
  -p tgt_component:=1 \
  -r __ns:=/mavros
```
Open a new terminal

```bash
cd ~/drone_ws
source install/setup.bash
ros2 launch apriltag_navigation apriltag_navigation.launch.py
```

Open a new terminal for image view

```bash
ros2 run rqt_image_view rqt_image_view 
```

It is recommended to install terminator to open more than one terminal

```bash
sudo apt install terminator
```

To split vertical press "ctrl+shift+e"
To split horizontal press "ctrl+shift+o"

----

## 6. Launch the simulation

a) Launch Drone:

```bash
export __EGL_VENDOR_LIBRARY_FILENAMES=/usr/share/glvnd/egl_vendor.d/10_nvidia.json
export __GLX_VENDOR_LIBRARY_NAME=nvidia
cd ~/drone_ws/src/PX4-Autopilot
PX4_GZ_WORLD=aruco make px4_sitl gz_x500_depth
```

b) Run QGround Control: Open a new terminal

```bash
cd ~/drone_ws/src/PX4-Autopilot
./QGroundControl-x86_64.AppImage

```

c) Run Mavros: Open a new terminal

```bash
ros2 run mavros mavros_node --ros-args \
  -p fcu_url:="udp://:14540@localhost:14557" \
  -p tgt_system:=1 \
  -p tgt_component:=1 \
  -r __ns:=/mavros
```

d) Run AprilTag navigation: Open a new terminal

```bash
cd ~/drone_ws
source install/setup.bash
ros2 launch apriltag_navigation apriltag_navigation.launch.py
```

e) Run image viewer: Open a new terminal for image view

```bash
ros2 run rqt_image_view rqt_image_view 
```
---
## 7. Prerequisites real drone

- Ubuntu 22.04 (Jammy) on rpi4
- ROS 2 Humble installed and sourced rpi4
- realsense camera library on rpi4
- mavros
- ssh installation


---
## 8. Installation of realsense camera library on Raspberry Pi 
use instructions from this link
https://github.com/MazenMTULab/Installation_Realsense-on-RPi4
## 9. Launch the real drone

a) Launch Real drone: Power it onby simply connect the battery.

b) Run Qground control on my mac. connect USB Radio telemtry to my MAC using MAC adaptor.It will automatically connect to the drone.

c) ssh to Raspberry pi: (I tested both my Mac and Raspbeery Pi 4connected to eduroam network)



  To install ssh if not installed:
  ```bash
  sudo apt update
  sudo apt install openssh-server
  sudo systemctl start ssh
  sudo systemctl enable ssh
```
check the raspberry pi IP address: (make hotspot with your phone)-need a portable screen 


On Raspberry Pi
```bash
ifconfig
141.219.293.133
```

On mac
```bash
ssh ubuntu@141.219.293.133

```
password is ubuntu 


All these upcoming step will be running on Raspberry Pi.

for the Raspberry Pi: username is ubuntu and password is ubuntu

d) Run Mavros: Open a new terminal
To check which /dev is the drone exactly, use a Type-C cable and plug it into the drone flight controller, and connect the USB to the Raspberry Pi 4. Then run

```bash
ls /dev/tty* 
```

or 

```bash
sudo dmsg | grep tty
```

```bash
sudo usermod -a -G dialout $USER
source /opt/ros/humble/setup.bash
ros2 run mavros mavros_node --ros-args \
  -p fcu_url:="serial:///dev/ttyACM0:57600" \
  
```

To check that it connected successfully 

```bash
ros2 topic echo /mavros/state
```

You should get connected=true

d) Run AprilTag navigation: Open a new terminal

```bash
cd ~/drone_ws
source install/setup.bash
ros2 launch apriltag_navigation apriltag_navigation.launch.py
```



