#!/usr/bin/env bash
set -e

if [[ -n "${GITLAB_CI:-}" ]]; then
    exec "$@"
fi

if [[ -n "${DEBUG:-}" ]]; then
    set -x
fi

: "${TIMEZONE:=Asia/Seoul}"
: "${GROUP:=user}"
: "${GROUP_ID:=1000}"
: "${USER:=user}"
: "${USER_ID:=1000}"
: "${VIDEO_GROUP_ID:=44}"
: "${ROS_DISTRO:=foxy}"

if [[ -n "${TIMEZONE}" ]]; then
    echo "${TIMEZONE}" >/etc/timezone
    ln -sf /usr/share/zoneinfo/"${TIMEZONE}" /etc/localtime
    dpkg-reconfigure -f noninteractive tzdata || true
fi

if getent group "${GROUP}" >/dev/null 2>&1; then
    echo "Group ${GROUP} exists, skipping group creation..."
else
    groupadd -og "${GROUP_ID}" "${GROUP}"
fi

if getent passwd "${USER}" >/dev/null 2>&1; then
    echo "User ${USER} exists, skipping user creation..."
else
    if getent passwd 1000 >/dev/null 2>&1; then
        username="$(getent passwd 1000 | cut -d: -f1)"
        userdel -r "${username}" || true
    fi

    while getent passwd "${USER_ID}" >/dev/null 2>&1; do
        USER_ID=$((USER_ID + 1))
    done

    useradd -m -u "${USER_ID}" -g "${GROUP_ID}" -d "/home/${USER}" -s /bin/bash "${USER}"
fi

if getent group video >/dev/null 2>&1; then
    echo "Group video exists, skipping video group creation..."
else
    groupadd -og "${VIDEO_GROUP_ID}" video
fi

gpasswd -a "${USER}" video || true
usermod -aG sudo "${USER}" || true

echo "${USER}:123" | chpasswd || true

mkdir -p "/home/${USER}"
chown -R "${USER}:${GROUP}" "/home/${USER}"

shopt -s dotglob
for x in /etc/skel/*; do
    target="/home/${USER}/$(basename "$x")"
    if [[ ! -e "$target" ]]; then
        cp -a "$x" "$target"
        chown -R "${USER}:${GROUP}" "$target"
    fi
done
shopt -u dotglob

cat >/etc/profile.d/ros2_setup.sh <<EOF
if [ -f "/opt/ros/${ROS_DISTRO}/setup.bash" ]; then
    source "/opt/ros/${ROS_DISTRO}/setup.bash"
fi
if [ -f "/ros2_ws/install/setup.bash" ]; then
    source "/ros2_ws/install/setup.bash"
fi
export PATH=/usr/local/zed/bin:\$PATH
export LD_LIBRARY_PATH=/usr/local/zed/lib:/usr/local/zed/lib64:\$LD_LIBRARY_PATH
EOF
chmod +x /etc/profile.d/ros2_setup.sh

if ! grep -q 'source /etc/profile.d/ros2_setup.sh' /etc/bash.bashrc; then
    echo 'source /etc/profile.d/ros2_setup.sh' >> /etc/bash.bashrc
fi

if [[ -z "${SKIP_ADEINIT:-}" ]]; then
    for x in /opt/*; do
        if [[ -x "$x/.adeinit" ]]; then
            echo "Initializing $x"
            sudo -Hu "${USER}" -- bash -lc "$x/.adeinit"
            echo "Initializing $x done"
        fi
    done
fi

echo "Container startup completed."

if [[ -x "/ade_entrypoint" ]]; then
    exec /ade_entrypoint "$@"
else
    exec "$@"
fi
