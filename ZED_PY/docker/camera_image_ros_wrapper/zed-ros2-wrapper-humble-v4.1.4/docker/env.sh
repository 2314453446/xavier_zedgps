# /etc/profile.d/ade_env.sh

# setup ros2 environment
if [ -n "$ROS_DISTRO" ] && [ -f "/opt/ros/$ROS_DISTRO/install/setup.bash" ]; then
    source "/opt/ros/$ROS_DISTRO/install/setup.bash"
fi

if [ -f "/root/ros2_ws/install/local_setup.bash" ]; then
    source "/root/ros2_ws/install/local_setup.bash"
fi

export RMW_IMPLEMENTATION=${RMW_IMPLEMENTATION:-rmw_cyclonedds_cpp}

# only print in interactive shells
case $- in
    *i*)
        echo "ZED ROS2 Docker Image"
        echo "---------------------"
        echo "ROS distro: $ROS_DISTRO"
        echo "DDS middleware: $RMW_IMPLEMENTATION"
        echo "ROS 2 Workspaces: $COLCON_PREFIX_PATH"
        echo "ROS 2 Domain ID: $ROS_DOMAIN_ID"
        echo "Machine IPs: $ROS_IP"
        echo "---"
        echo "Available ZED packages:"
        ros2 pkg list | grep zed || true
        echo "---------------------"
        ;;
esac