FROM osrf/ros:humble-desktop-full

ENV DEBIAN_FRONTEND=noninteractive
ENV TURTLEBOT3_MODEL=waffle_pi

RUN apt-get update && apt-get install -y --no-install-recommends \
        ros-humble-turtlebot3 \
        ros-humble-turtlebot3-gazebo \
        ros-humble-gazebo-ros-pkgs \
        ros-humble-cv-bridge \
        ros-humble-rqt-image-view \
        python3-opencv \
        python3-matplotlib \
    && rm -rf /var/lib/apt/lists/*

RUN mkdir -p /ws/src && chmod 777 /ws
WORKDIR /ws

COPY beacon_env.sh /opt/beacon_env.sh
COPY entrypoint.sh /opt/entrypoint.sh
RUN chmod +x /opt/beacon_env.sh /opt/entrypoint.sh

ENTRYPOINT ["/opt/entrypoint.sh"]
CMD ["bash"]
